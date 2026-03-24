import sqlite3
import threading
import os
from contextlib import contextmanager

db_lock = threading.Lock()
# Base directory of the project
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, 'data', 'storage')
os.makedirs(DB_DIR, exist_ok=True)
DB_FILE = os.path.join(DB_DIR, 'crowler.db')

import time
last_backup_time = 0
is_backing_up = False
backup_lock = threading.Lock()

def backup_db_to_raw():
    global last_backup_time, is_backing_up
    with backup_lock:
        if is_backing_up or (time.time() - last_backup_time < 10):
            return
        is_backing_up = True
        last_backup_time = time.time()

    def task():
        global is_backing_up
        try:
            conn = sqlite3.connect(DB_FILE, timeout=30)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT word, url, origin_url, depth, frequency FROM inverted_index")
            rows = cursor.fetchall()
            conn.close()

            from collections import defaultdict
            files = defaultdict(list)
            for row in rows:
                word = row['word'].strip()
                if not word:
                    continue
                letter = word[0].lower()
                if not letter.isalnum():
                    continue
                files[letter].append(f"{word} {row['url']} {row['origin_url']} {row['depth']} {row['frequency']}")

            for letter, lines in files.items():
                file_path = os.path.join(DB_DIR, f"{letter}.data")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(sorted(lines)) + "\n")
        except Exception as e:
            print("Error generating .data files:", e)
        finally:
            with backup_lock:
                is_backing_up = False

    threading.Thread(target=task, daemon=True).start()

def get_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

@contextmanager
def get_cursor():
    with db_lock:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            yield cursor
            conn.commit()
            backup_db_to_raw()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

def init_db():
    with get_cursor() as cursor:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS queue_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                crawler_id TEXT NOT NULL,
                url TEXT NOT NULL,
                origin_url TEXT NOT NULL,
                depth INTEGER NOT NULL,
                status TEXT NOT NULL,
                UNIQUE(crawler_id, url)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS visited_v2 (
                crawler_id TEXT NOT NULL,
                url_hash TEXT NOT NULL,
                url TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (crawler_id, url_hash)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inverted_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                url TEXT NOT NULL,
                origin_url TEXT NOT NULL,
                depth INTEGER NOT NULL,
                frequency INTEGER NOT NULL,
                context_snippet TEXT,
                UNIQUE(word, url)
            )
        ''')
        try:
            cursor.execute('ALTER TABLE inverted_index ADD COLUMN context_snippet TEXT;')
        except:
            pass
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crawlers (
                id TEXT PRIMARY KEY,
                origin_url TEXT NOT NULL,
                max_depth INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_word ON inverted_index(word);')
        
        # Dead crawler cleanup on boot
        cursor.execute("UPDATE crawlers SET status = 'Stopped' WHERE status IN ('Running', 'Paused')")

def add_to_queue(crawler_id, url, origin_url, depth, status='pending'):
    with get_cursor() as cursor:
        cursor.execute(
            "INSERT OR IGNORE INTO queue_v2 (crawler_id, url, origin_url, depth, status) VALUES (?, ?, ?, ?, ?)",
            (crawler_id, url, origin_url, depth, status)
        )

def get_pending_urls(crawler_id, limit=10):
    with get_cursor() as cursor:
        cursor.execute(
            "SELECT * FROM queue_v2 WHERE crawler_id = ? AND status = 'pending' LIMIT ?",
            (crawler_id, limit)
        )
        return [dict(row) for row in cursor.fetchall()]

def mark_url_status(url_id, status):
    with get_cursor() as cursor:
        cursor.execute("UPDATE queue_v2 SET status = ? WHERE id = ?", (status, url_id))

def is_visited(crawler_id, url_hash):
    with get_cursor() as cursor:
        cursor.execute("SELECT 1 FROM visited_v2 WHERE crawler_id = ? AND url_hash = ?", (crawler_id, url_hash))
        return cursor.fetchone() is not None

def mark_visited(crawler_id, url_hash, url):
    with get_cursor() as cursor:
        cursor.execute(
            "INSERT OR IGNORE INTO visited_v2 (crawler_id, url_hash, url) VALUES (?, ?, ?)",
            (crawler_id, url_hash, url)
        )

def add_index(word, url, origin_url, depth, frequency, context_snippet):
    with get_cursor() as cursor:
        cursor.execute(
            "INSERT OR REPLACE INTO inverted_index (word, url, origin_url, depth, frequency, context_snippet) VALUES (?, ?, ?, ?, ?, ?)",
            (word, url, origin_url, depth, frequency, context_snippet)
        )

def add_indexes(records):
    """Batch insert indexes to save massive DB lock overhead"""
    if not records: return
    with get_cursor() as cursor:
        cursor.executemany(
            "INSERT OR REPLACE INTO inverted_index (word, url, origin_url, depth, frequency, context_snippet) VALUES (?, ?, ?, ?, ?, ?)",
            records
        )

def search_index(word):
    with get_cursor() as cursor:
        cursor.execute('''
            SELECT url, origin_url, depth, MAX(frequency) as frequency, context_snippet,
                   MAX(((frequency * 10) - (depth * 2))) as score
            FROM inverted_index
            WHERE word = ?
            GROUP BY url
            ORDER BY score DESC
            LIMIT 50
        ''', (word.lower(),))
        return [dict(row) for row in cursor.fetchall()]

def get_global_metrics():
    with get_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM inverted_index")
        total_words_in_db = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM visited_v2")
        total_visited_urls = cursor.fetchone()[0]
        return total_words_in_db, total_visited_urls

def create_crawler(crawler_id, origin_url, max_depth, status, created_at):
    with get_cursor() as cursor:
        cursor.execute(
            "INSERT INTO crawlers (id, origin_url, max_depth, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (crawler_id, origin_url, max_depth, status, created_at)
        )

def update_crawler_status(crawler_id, status):
    with get_cursor() as cursor:
        cursor.execute("UPDATE crawlers SET status = ? WHERE id = ?", (status, crawler_id))

def get_all_crawlers():
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT c.*, (SELECT COUNT(*) FROM visited_v2 v WHERE v.crawler_id = c.id) as visited_count
            FROM crawlers c
            ORDER BY c.created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]

def get_graph_data():
    with get_cursor() as cursor:
        # We need nodes and edges for recent visits
        # get urls and their origin URLs. For an edge, we need origin_url -> url
        cursor.execute("""
            SELECT url, origin_url 
            FROM queue_v2 
            WHERE status != 'pending' 
            ORDER BY id DESC 
            LIMIT 500
        """)
        rows = cursor.fetchall()

        nodes_set = set()
        edges = []
        # Origin URLs are those who initiated a crawl
        cursor.execute("SELECT origin_url FROM crawlers")
        origins = {r['origin_url'] for r in cursor.fetchall()}
        
        for r in rows:
            url = r['url']
            origin = r['origin_url']
            nodes_set.add(url)
            nodes_set.add(origin)
            if origin != url:
                edges.append({"from": origin, "to": url})

        nodes = []
        for n in nodes_set:
            label = n.split('//')[-1][:30] if len(n.split('//')[-1]) > 5 else n[:30]
            is_root = n in origins
            nodes.append({"id": n, "label": label, "isRoot": is_root})
            
        return {"nodes": nodes, "edges": edges}

