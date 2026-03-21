# 🐦‍⬛ Crowler

A high-performance, multi-threaded web crawling platform and search engine built with Python. Crowler features real-time hacker-style monitoring, an intelligent inverted-index search engine, and a robust concurrency model designed to scale efficiently while protecting against system exhaustion.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![SQLite](https://img.shields.io/badge/SQLite-WAL%20Mode-blue.svg)
![Flask](https://img.shields.io/badge/Framework-Flask-green.svg)
![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen.svg)

---

## 🏗️ Architecture & Algorithms (Deep Dive)

Crowler's core engine is built on advanced computer science principles to ensure speed, accuracy, and reliability.

### Breadth-First Search (BFS) Implementation
The crawler employs a **Breadth-First Search (BFS)** algorithm to traverse the web. Unlike Depth-First Search, BFS ensures that pages are crawled in order of their distance from the seed URL, providing a well-rounded index of relevant content before diving into deep, potentially irrelevant links.
- **Persistent Memory**: The global `visited` and `queue` tables act as the crawler's persistent memory. 
- The `queue` stores discovered URLs waiting to be crawled, ensuring strict FIFO (First-In-First-Out) processing.
- The `visited` table uses a cryptographic hash (or fast indexing) of the URL to ensure $O(1)$ lookups, preventing loops and redundant crawling.

### Inverted Index & Relevancy Engine
When a page is parsed, it isn't just saved as raw HTML. Crowler builds an **Inverted Index**—mapping words to the URLs where they appear. This enables lightning-fast $O(1)$ search lookups.
- **Relevancy Score**: Search results are ranked using a proprietary algorithm:
  $\text{Score} = (\text{Frequency} \times 10) - (\text{Depth} \times 2)$
  This mathematically prioritizes keywords that appear frequently on pages closer to the root URL.

### Concurrency Model & Data Integrity
Crowler leverages a sophisticated **Producer-Consumer pattern** powered by Python's threading library.
- **Thread Safety**: Access to shared resources (like the in-memory URL structures) is guarded via strict `threading.Lock()` implementations to prevent data corruption.
- **SQLite WAL Mode**: To support aggressive concurrent database writes without locking the entire database file, Crowler utilizes **SQLite's Write-Ahead Logging (WAL)**. This allows readers and writers to operate simultaneously, drastically increasing throughput.

---

## 🛡️ System Protection & Back-pressure

To prevent the crawler from going rogue and consuming all available system memory, built-in **Back-pressure** mechanisms are enforced.

- `queue_capacity`: Acts as a hard limit on the maximum number of pending URLs. If the queue hits this ceiling, the parsers automatically pause URL extraction until the workers catch up, maintaining memory equilibrium.
- `max_urls_to_visit`: A strict circuit-breaker that safely terminates the crawling operation once the target number of indexed pages is reached, preventing infinite loops in cyclic web schemas.

---

## 📁 Project Structure

```text
crowler/
├── app.py                      # 🚀 Main Flask API server (Routing & Search API)
├── services/                   # 🏗️ Core crawler engine & business logic
│   ├── crawler.py              #    Multi-threaded BFS crawler implementation
│   ├── database.py             #    SQLite WAL mode database ops & Inverted Index
│   └── parser.py               #    HTML parsing & Tokenization logic
├── templates/                  # 🎨 HTML Views
│   ├── crawler.html            #    Crawler Dashboard & Hacker Terminal UI
│   └── search.html             #    Minimalist Search Engine Interface
├── static/                     # 💅 Frontend Assets
│   ├── css/                    #    Stylesheets (crawler.css, search.css)
│   └── js/                     #    Client-side logic (crawler.js, search.js)
├── tests/                      # 🧪 Automated Test Suite
│   ├── test_evaluation.py      #    Concurrency, Race Conditions & Gauntlet
│   └── tester.py               #    Utility test helpers
├── logs/                       # 📝 Real-time telemetry and runtime logs
├── requirements.txt            # 📦 Python project dependencies
└── README.md                   # 📖 This file
```

---

## 🎮 UI & Features Guide

Crowler isn't just a backend engine; it features a sleek, intuitive frontend interface split into major core experiences.

### 🕸️ Crawler Dashboard
The mission control center where you unleash the bots. Here you define the constraints of your crawl:
- **Seed URL**: The starting node of the web graph. The crawler will branch out from here.
- **Max Depth**: How many clicks away from the seed the crawler is allowed to wander. Setting this conservatively prevents the crawler from exploring irrelevant deep-web rabbit holes.
- **Queue Limits**: Define strict parameters on URL throughput and memory constraints.
- **Concurrency/Threads**: Number of parallel worker bots acting simultaneously. More threads mean higher network saturation and faster indexing.

### 💻 Hacker Terminal (Live Telemetry)
Built directly into the crawler dashboard, this is a real-time polling terminal that streams raw operational logs directly to your browser without page reloads. Watch the multi-threaded engine work with precision.

Color-coded status tags provide immediate visual feedback on the system's state:
- `[FETCHING]`: The worker thread is opening a socket and actively downloading the HTML payload from the target server.
- `[PARSED]`: The HTML has been successfully tokenized, stripped of boilerplate, and injected into the global Inverted Index.
- `[SKIPPING]`: The crawler encountered a previously visited URL, an invalid schema, or a binary file type and bypassed it via $O(1)$ lookup.
- `[THROTTLING]`: Back-pressure is engaged; the worker thread is intentionally sleeping to respect site rate limits or allow the database disk-writes to catch up.
- `[ERROR]`: Non-blocking exceptions (like 404s or connection timeouts) that the threads elegantly step over to continue work.

### 🔍 Search Engine Interface
A lightning-fast, minimalist search interface to query your massive localized index. It provides instantaneous feedback leveraging the persistent Inverted Index.
- **Real-time Querying**: Instant results returning URLs sorted tightly by the computed Relevancy Score mathematics.
- **Google-like Context Snippets**: Search results intuitively include the exact sub-string snippet where your searched keyword was found within the parsed HTML, with the query heavily highlighted for quick visual parsing.
- **Dynamic Pagination**: Easily browse through thousands of matched results without lagging the browser.
- **Easter Egg**: Click the **"I feel like a bird"** button to bypass standard search algorithms and be instantly teleported to a randomly selected, highly-relevant indexed page!

---

## 🧪 Automated Evaluation & Stress Tests (CRITICAL)

Reliability is paramount. The `tests/test_evaluation.py` suite is an absolute gauntlet designed to push Crowler to its breaking point.

### Test 1: Concurrency & WAL
Bombards the SQLite database with simultaneous reads and writes from multiple spawned threads. Proves that WAL mode is correctly configured and prevents `database is locked` exceptions.

### Test 2: Back-pressure Mechanisms
Floods the crawler with a massive mock web graph. Asserts that the queue never exceeds `queue_capacity` and that memory usage remains perfectly flat.

### Test 3: Race Conditions
Forces thread collisions on the `visited` set and `threading.Lock()` blocks. Proves that URLs are processed exactly once and no duplicate records exist in the final database.

**Run the gauntlet yourself:**
```bash
python tests/test_evaluation.py
```
*Watch for the green `[PASS]` indicators to verify absolute system stability.*

---

## 🚀 Setup & Installation

Ready to deploy Crowler? Follow these exact steps.

### 1. Clone & Navigate
Ensure you are in the project root:
```bash
cd crowler
```

### 2. Install Dependencies
Install the required packages strictly from the requirements file to ensure version exactness:
```bash
pip install -r requirements.txt
```

### 3. Initialize the Database
Before running, you can optionally ensure tests pass:
```bash
python tests/test_evaluation.py
```

### 4. Ignite the Server
Boot the main application:
```bash
python app.py
```
The Flask server will bind to `localhost`. Open your browser and navigate to the printed URL to bring the dashboard online.

---

*Built with precision and elegance. 🐦‍⬛*
