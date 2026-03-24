import threading
import queue
import time
import urllib.request
import hashlib
import uuid
import services.database as database
import services.parser as parser
import datetime
import os

MAX_QUEUE_SIZE = 5000
HIT_RATE_DELAY = 0.5
USER_AGENT = 'CrowlerBot/1.0'

class CrawlerJob:
    def __init__(self, crawler_id, origin_url, max_depth, max_urls_to_visit=500, queue_capacity=10000, hit_rate=0.5, num_threads=5):
        self.crawler_id = crawler_id
        self.origin_url = origin_url
        self.max_depth = max_depth
        self.max_urls_to_visit = max_urls_to_visit
        self.queue_capacity = queue_capacity
        self.hit_rate = hit_rate
        self.num_threads = num_threads
        self.memory_queue = queue.Queue(maxsize=self.queue_capacity)
        self.created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.seen_urls = set()
        self.is_running = True
        self.resume_event = threading.Event()
        self.resume_event.set()
        
        self.status = "Running"
        self.visited_count = 0
        self.threads = []
        self.visit_lock = threading.Lock()
        
        # Ensure log file targets the base project dir instead of services/logs
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_dir = os.path.join(base_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, f"crawler_{self.crawler_id}.log")
        self._log(f"Started crawler. Origin: {origin_url}")

        # Start Threads
        prod = threading.Thread(target=self._producer_loop, daemon=True)
        prod.start()
        self.threads.append(prod)
        
        for _ in range(self.num_threads):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            worker.start()
            self.threads.append(worker)

    def _log(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        thread_name = threading.current_thread().name
        log_line = f"[{timestamp}] [{thread_name}] {message}\n"
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception:
            pass

    def _hash_url(self, url):
        return hashlib.md5(url.encode('utf-8')).hexdigest()

    def _producer_loop(self):
        while self.is_running:
            # wait on resume_event. If cleared (paused), blocks for up to 1sec
            if not self.resume_event.wait(timeout=1):
                continue
                
            if self.memory_queue.qsize() > (self.queue_capacity * 0.8):
                self._log(f"Queue near capacity ({self.memory_queue.qsize()}). Producer chilling...")
                time.sleep(1)
                continue

            try:
                pending = database.get_pending_urls(self.crawler_id, limit=50)
                if not pending:
                    time.sleep(2)
                    continue

                for task in pending:
                    database.mark_url_status(task['id'], 'processing')
                    self.memory_queue.put(task)
                self._log(f"Enqueued {len(pending)} pending tasks. MemQueue size: {self.memory_queue.qsize()}")
            except Exception as e:
                self._log(f"Producer error: {e}")
                time.sleep(2)

    def _worker_loop(self):
        while self.is_running:
            if not self.resume_event.wait(timeout=1):
                continue

            try:
                # Unblocks graceful stopping without freezing
                task = self.memory_queue.get(timeout=1)
            except queue.Empty:
                continue

            if self.visited_count >= self.max_urls_to_visit:
                self._log("Max URLs limit reached. Stopping.")
                self.stop()
                continue
                
            url = task['url']
            url_id = task['id']
            depth = task['depth']
            
            self._log(f"Fetching URL: {url} | Depth: {depth}")

            url_hash = self._hash_url(url)
            
            with self.visit_lock:
                if url_hash in self.seen_urls:
                    self._log(f"Skipping already visited URL: {url}")
                    database.mark_url_status(url_id, 'completed')
                    self.memory_queue.task_done()
                    continue
                self.seen_urls.add(url_hash)
                database.mark_visited(self.crawler_id, url_hash, url)
                self.visited_count += 1

            try:
                sleep_duration = self.hit_rate
                while sleep_duration > 0 and self.is_running and self.resume_event.is_set():
                    time.sleep(min(0.2, sleep_duration))
                    sleep_duration -= 0.2

                if not self.is_running or not self.resume_event.is_set():
                    # Put back the task and skip processing
                    database.mark_url_status(url_id, 'pending')
                    self.visited_count -= 1 # Revert count
                    self.seen_urls.remove(url_hash) # Revert cache
                    self.memory_queue.task_done()
                    continue

                req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
                with urllib.request.urlopen(req, timeout=5) as response:
                    html_bytes = response.read()
                links, word_freqs, snippets = parser.parse_html(url, html_bytes)

                self._log(f"Parsed {len(links)} links, {len(word_freqs)} words from {url}")

                records = [(word, url, task['origin_url'], depth, freq, snippets.get(word, '')) for word, freq in word_freqs.items()]
                database.add_indexes(records)

                if depth < self.max_depth:
                    for link in links:
                        link_hash = self._hash_url(link)
                        if not database.is_visited(self.crawler_id, link_hash):
                            database.add_to_queue(self.crawler_id, link, task['origin_url'], depth + 1, 'pending')
                    self._log(f"Added new links to queue.")
                else:
                    self._log(f"Max depth {self.max_depth} reached. Skipped adding links.")

                database.mark_url_status(url_id, 'completed')

            except Exception as e:
                self._log(f"Error fetching URL {url}: {e}")
                database.mark_url_status(url_id, 'completed')
            finally:
                self.memory_queue.task_done()

    def pause(self):
        self._log("Crawler requested Pause")
        self.resume_event.clear()
        self.status = "Paused"
        database.update_crawler_status(self.crawler_id, self.status)

    def resume(self):
        self._log("Crawler requested Resume")
        self.resume_event.set()
        self.status = "Running"
        database.update_crawler_status(self.crawler_id, self.status)

    def stop(self):
        self._log("Crawler requested Stop")
        self.is_running = False
        self.resume_event.set()
        self.status = "Stopped"
        database.update_crawler_status(self.crawler_id, self.status)

class CrawlerManager:
    def __init__(self):
        self.crawlers = {}
        database.init_db()

    def start_new_crawl(self, origin_url, max_depth, max_urls_to_visit=500, queue_capacity=10000, hit_rate=0.5):
        c_id = str(uuid.uuid4())[:8]
        database.add_to_queue(c_id, origin_url, origin_url, 0, 'pending')

        job = CrawlerJob(c_id, origin_url, max_depth, max_urls_to_visit, queue_capacity, hit_rate)
        database.create_crawler(c_id, origin_url, max_depth, job.status, job.created_at)
        self.crawlers[c_id] = job
        return c_id

    def get_stats(self):
        db_crawlers = database.get_all_crawlers()
        stats = []
        for db_c in db_crawlers:
            c_id = db_c['id']
            if c_id in self.crawlers:
                job = self.crawlers[c_id]
                stats.append({
                    'id': c_id,
                    'origin_url': job.origin_url,
                    'depth': job.max_depth,
                    'status': job.status,
                    'visited_count': job.visited_count,
                    'created_at': getattr(job, 'created_at', None)
                })
            else:
                stats.append({
                    'id': c_id,
                    'origin_url': db_c['origin_url'],
                    'depth': db_c['max_depth'],
                    'status': db_c['status'],
                    'visited_count': db_c['visited_count'],
                    'created_at': db_c['created_at']
                })
        
        processed_ids = {s['id'] for s in stats}
        for cid, job in self.crawlers.items():
            if cid not in processed_ids:
                stats.append({
                    'id': cid,
                    'origin_url': job.origin_url,
                    'depth': job.max_depth,
                    'status': job.status,
                    'visited_count': job.visited_count,
                    'created_at': getattr(job, 'created_at', None)
                })

        return stats

    def control(self, crawler_id, action):
        job = self.crawlers.get(crawler_id)
        if not job:
            return False
        
        if action == 'pause': job.pause()
        elif action == 'resume': job.resume()
        elif action == 'stop': job.stop()
        return True

manager = CrawlerManager()
