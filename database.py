import sqlite3
import threading
from contextlib import contextmanager

db_lock = threading.Lock()
DB_FILE = 'crowler.db'

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
                status TEXT NOT NULL
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

def add_to_queue(crawler_id, url, origin_url, depth, status='pending'):
    with get_cursor() as cursor:
        cursor.execute(
            "INSERT INTO queue_v2 (crawler_id, url, origin_url, depth, status) VALUES (?, ?, ?, ?, ?)",
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

def search_index(word):
    with get_cursor() as cursor:
        cursor.execute('''
            SELECT url, origin_url, depth, context_snippet,
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

