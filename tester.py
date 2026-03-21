import urllib.request
import urllib.parse
import json
import time

BASE_URL = "http://127.0.0.0:5000"
BASE_URL = "http://localhost:5000"

def post_json(endpoint, data):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, method="POST")
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, data=json.dumps(data).encode('utf-8')) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return {"error": str(e)}

def get_json(endpoint):
    url = f"{BASE_URL}{endpoint}"
    try:
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    print("=== Crowler API Tester ===")
    
    # 1. Start Crawl
    print("\n[1] Starting Crawl on http://example.com (Depth: 2)...")
    res = post_json("/api/crawl", {"origin": "http://example.com", "max_depth": 2})
    print(res)

    # 2. Poll metrics
    print("\n[2] Polling Metrics for 4 seconds...")
    for _ in range(4):
        time.sleep(1)
        metrics = get_json("/api/metrics")
        print(f"  -> Metrics: {metrics}")

    # 3. Test State Control (Pause)
    print("\n[3] Pausing Crawler...")
    print(post_json("/api/state", {"action": "pause"}))
    time.sleep(2)
    print("  -> Metrics (Paused):", get_json("/api/metrics"))

    # 4. Test State Control (Resume)
    print("\n[4] Resuming Crawler...")
    print(post_json("/api/state", {"action": "resume"}))
    time.sleep(2)

    # 5. Search Engine Test
    search_term = "domain"
    print(f"\n[5] Searching for '{search_term}'...")
    search_res = get_json(f"/api/search?q={search_term}")
    results = search_res.get('results', [])
    print(f"  -> Found {len(results)} matches.")
    for res in results[:3]:  # Show top 3
        print(f"     * {res['url']} (Score: {res['score']})")

    # 6. Stop Crawler
    print("\n[6] Stopping Crawler...")
    print(post_json("/api/state", {"action": "stop"}))
    print("Done!")
