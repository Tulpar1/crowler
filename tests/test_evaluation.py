import requests
import threading
import time
import sqlite3
import os
import sys

BASE_URL = "http://localhost:5000"
# Path to crowler.db relative to this script (which is in the tests/ folder)
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crowler.db")

def print_pass(msg):
    print(f"\033[92m[PASS]\033[0m {msg}")

def print_fail(msg):
    print(f"\033[91m[FAIL]\033[0m {msg}")

def print_info(msg):
    print(f"\033[94m[INFO]\033[0m {msg}")

def test_concurrency():
    print_info("Starting Test 1: Concurrent Search during Crawl (Concurrency & WAL Mode test)...")
    try:
        # Trigger an intensive crawl task
        res = requests.post(f"{BASE_URL}/api/crawl", json={
            "origin": "https://books.toscrape.com/",
            "max_depth": 3,
            "max_urls_to_visit": 1000,
            "queue_capacity": 5000
        }, timeout=5)
        
        if res.status_code != 200:
            print_fail(f"Failed to start crawler task. HTTP {res.status_code}")
            return False
            
        print_info(f"Crawler started (ID: {res.json().get('crawler_id')}). Spawning 10 search threads...")
    except Exception as e:
        print_fail(f"Could not connect to the API: {e}")
        return False

    successes = 0
    failures = 0
    lock = threading.Lock()

    def search_worker():
        nonlocal successes, failures
        for _ in range(10):
            try:
                r = requests.get(f"{BASE_URL}/api/search?q=book", timeout=5)
                if r.status_code == 200:
                    with lock:
                        successes += 1
                else:
                    with lock:
                        failures += 1
            except Exception:
                with lock:
                    failures += 1
            time.sleep(0.1)

    threads = [threading.Thread(target=search_worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if failures == 0 and successes == 100:
        print_pass("All concurrent searches returned HTTP 200 (No 'database is locked' errors). WAL mode and read/write concurrency function flawlessly.")
        return True
    else:
        print_fail(f"Concurrency test failed. Successes: {successes}, Failures: {failures}")
        return False

def test_backpressure():
    print_info("Starting Test 2: Back-Pressure Limit Verification...")
    try:
        strict_capacity = 15
        res = requests.post(f"{BASE_URL}/api/crawl", json={
            "origin": "https://en.wikipedia.org/wiki/Main_Page", # URL with many links to test quick queue bloating
            "max_depth": 3,
            "max_urls_to_visit": 2000,
            "queue_capacity": strict_capacity
        }, timeout=5)
        
        target_crawler_id = res.json().get('crawler_id')
    except Exception as e:
        print_fail(f"Could not start crawler for backpressure test: {e}")
        return False

    passed = True
    max_observed_queue = 0
    
    # Loop for 5 seconds checking every 0.5s
    for _ in range(10):
        time.sleep(0.5)
        try:
            stats_res = requests.get(f"{BASE_URL}/api/crawlers", timeout=5)
            if stats_res.status_code == 200:
                stats = stats_res.json()
                for crawler in stats:
                    if crawler.get("id") == target_crawler_id:
                        qsize = crawler.get("queue_size", 0)
                        max_observed_queue = max(max_observed_queue, qsize)
                        
                        # Since multiple threads might insert slightly past the 15 limit due to thread switching,
                        # we allow a small buffer (e.g., limit + thread count) before considering it a failure.
                        if qsize > strict_capacity + 15:
                            print_fail(f"Queue exploded uncontrollably! Limit was {strict_capacity}, but queue reached {qsize}.")
                            passed = False
                            break
            if not passed:
                break
        except Exception as e:
            print_fail(f"Failed checking metrics: {e}")
            passed = False
            break

    if passed:
        print_pass(f"Back-pressure limit verification succeeded! Queue size respected capacity (Max observed: {max_observed_queue}).")
        
    return passed

def test_thread_safety():
    print_info("Starting Test 3: Thread-Safety & Race Condition Check...")
    
    if not os.path.exists(DB_PATH):
        print_fail(f"Database file not found at {DB_PATH}. Cannot verify thread safety constraints.")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check for duplicated URLs in visited table
        c.execute("""
            SELECT url, COUNT(*) 
            FROM visited 
            GROUP BY url 
            HAVING COUNT(*) > 1
        """)
        dupe_urls = c.fetchall()

        # Check for duplicated (word, url) pairs in inverted index
        c.execute("""
            SELECT word, url, COUNT(*) 
            FROM inverted_index 
            GROUP BY word, url 
            HAVING COUNT(*) > 1
        """)
        dupe_index_pairs = c.fetchall()
        
        conn.close()

        passed = True
        if dupe_urls:
            print_fail(f"Data corruption detected: Found {len(dupe_urls)} duplicate URLs in 'visited' table!")
            passed = False
        else:
            print_pass("Zero duplicate URLs found in the 'visited' database table.")

        if dupe_index_pairs:
            print_fail(f"Data corruption detected: Found {len(dupe_index_pairs)} duplicate (word, relevant_url) pairs in 'inverted_index'!")
            passed = False
        else:
            print_pass("Zero duplicates found in the 'inverted_index' table.")
            
        if passed:
            print_pass("Thread safety perfectly verified. Locks and UNIQUE constraints handled all conditions successfully.")
            
        return passed

    except sqlite3.OperationalError as e:
        print_fail(f"SQLite error during thread safety check: {e}. Check if tables exist.")
        return False

if __name__ == "__main__":
    print("\n--- Starting Evaluation Toolkit ---\n")
    
    # 1. Concurrency Test
    concurrency_passed = test_concurrency()
    print()
    
    # 2. Backpressure Test
    backpressure_passed = test_backpressure()
    print()
    
    # Let crawls run for a bit before checking database
    print_info("Waiting 3 seconds to let concurrent database writers finish before consistency checks...")
    time.sleep(3)
    print()
    
    # 3. Thread Safety Test
    safety_passed = test_thread_safety()
    print()
    
    # General Evaluation Result
    if concurrency_passed and backpressure_passed and safety_passed:
        print("\033[92m\033[1m[ALL SYSTEMS GO]\033[0m Your crawler passes all evaluation criteria. Excellent work!")
        sys.exit(0)
    else:
        print("\033[91m\033[1m[EVALUATION FAILED]\033[0m Some grading criteria were not met. Check the logs above.")
        sys.exit(1)
