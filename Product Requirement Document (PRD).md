# Product Requirement Document (PRD)

## 1. Project Overview
**Project Name:** Crowler (Crow + Crawler)
**Mascot & Brand Identity:** A sleek, intelligent Crow. The brand represents smart, efficient, and relentless data gathering.
**Objective:** Build a highly concurrent web crawler and real-time search engine from scratch in a single day. The system must handle recursive indexing, concurrent search queries, and back-pressure management.
**Strict Constraint:** The backend must strictly use Python native libraries (`urllib`, `html.parser`, `threading`, `sqlite3`).No third-party scraping frameworks (like Scrapy) or external databases (like Redis/Postgres) are allowed.

## 2. UI/UX & Frontend Specifications
The web interface must be professional, highly responsive, and strictly **Dark Themed**.
* **Color Palette:** Deep charcoal/black backgrounds (`#121212`, `#1E1E1E`), subtle gray borders, and vibrant accent colors (e.g., neon cyan or sleek purple) for active states and the Crow mascot logo.
* **Layout:** A unified, easy-to-use, single-page dashboard divided into logical sections:
    * **Header:** Features the "Crowler" name and a minimalist crow mascot icon.
    * **Control Panel (Left/Top):** Input fields for `Origin URL` and `Max Depth`. Buttons for "Start Crawl", "Pause", "Resume", and "Stop".
    * **Live Metrics (Center):** Real-time animated counters for "URLs Visited", "Queue Depth", "Active Threads", and "System Status" (Running/Paused/Throttling).
    * **Search Engine (Right/Bottom):** A clean search bar with a real-time results area displaying `(URL, Origin, Depth)` triples.

## 3. Technology Stack & Architecture
* **Backend:** Python 3.8+ & Flask (for API endpoints and serving the UI).
* **Database:** Python's native `sqlite3`. 
    * *Crucial Directive:* The SQLite connection must be initialized with `PRAGMA journal_mode=WAL;`. This Write-Ahead Logging is mandatory to allow the Search Engine to read the database concurrently while the Crowler threads are writing to it.
* **Concurrency:** Python native `threading.Thread`, `threading.Lock`, and `queue.Queue`.
* **Frontend:** HTML5, CSS3, and Vanilla JavaScript (using Fetch API for 1-second interval polling).

## 4. Database Schema & Persistence (The "Resume" Capability)
The system must be fully resilient. If the Flask server crashes or is stopped, the system must not start from scratch. It must resume using the state stored in `crowler.db`.
* **`queue` Table:** * Columns: `id`, `url`, `origin_url`, `depth`, `status` (pending/processing/completed).
    * *Resume Logic:* On boot, the system fetches all URLs where `status='pending'` and populates the in-memory queue.
* **`visited` Table:**
    * Columns: `url_hash` (Primary Key), `url`, `timestamp`.
    * Ensures strict uniqueness; a URL is checked against this table before being added to the queue.
* **`inverted_index` Table:**
    * Columns: `word`, `url`, `origin_url`, `depth`, `frequency`.
    * Indexed heavily on the `word` column to ensure lightning-fast Search API responses.

## 5. Core System Mechanics

### 5.1. The Indexer (Crawler Threads)
* **Initialization:** The user inputs an origin URL and maximum depth `k`.
* **Execution:** The system spins up a thread pool (e.g., 5-10 workers). Workers pull a URL from the thread-safe `queue`, fetch the HTML using `urllib.request`, and parse it using `html.parser`.
* **Discovery:** Found `<a href>` links are validated, absolute URLs are resolved, and if depth < `k`, they are inserted into the `queue` table.

### 5.2. Back-Pressure & Resource Management
* The system must monitor its own queue depth.
* **High-Water Mark:** If the in-memory/DB queue exceeds a defined threshold (e.g., 5000 URLs), the parser threads must pause adding new discovered links and focus solely on processing existing ones.
* **Rate Limiting:** Implement a configurable `HIT_RATE_DELAY` (e.g., 0.5 seconds per request) to avoid IP bans and server overload.

### 5.3. The Search Engine
* **Continuous Availability:** Must remain fully responsive via `GET /api/search` even under heavy crawling load.
* **Relevancy Algorithm:** When a query string is received, calculate a score for each matched URL. 
    * *Score Formula:* `(Frequency of word * 10) - (Crawl Depth * 2)`. Lower depth and higher frequency yield a better ranking.

## 6. API Contract
* `POST /api/crawl`: Payload `{"origin": string, "max_depth": int}`. Initiates or resumes the crawl.
* `POST /api/state`: Payload `{"action": "pause" | "resume" | "stop"}`. Updates global thread state.
* `GET /api/metrics`: Returns JSON containing `queue_size`, `visited_count`, `active_threads`, and `back_pressure_active`.
* `GET /api/search?q={query}`: Returns a JSON array of matched URLs sorted by relevancy.

## 7. Delivery Checklist
* Fully functional local application.
* `readme.md` detailing setup instructions.
* `product_prd.md` (This file).
* `recommendation.md` (A 2-paragraph guide on deploying this to a high-scale production environment).