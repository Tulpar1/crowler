from flask import Flask, request, jsonify, render_template
import crawler
import os

app = Flask(__name__)

@app.route('/')
def search_page():
    return render_template('search.html')

@app.route('/crawler')
def index():
    return render_template('crawler.html')


@app.route('/api/crawl', methods=['POST'])
def start_crawl():
    data = request.get_json()
    if not data or 'origin' not in data or 'max_depth' not in data:
        return jsonify({"error": "Missing 'origin' or 'max_depth'"}), 400

    origin_url = data['origin']
    max_depth = int(data['max_depth'])
    max_urls_to_visit = int(data.get('max_urls_to_visit', 100))
    queue_capacity = int(data.get('queue_capacity', 5000))

    c_id = crawler.manager.start_new_crawl(origin_url, max_depth, max_urls_to_visit, queue_capacity)
    return jsonify({"status": "success", "crawler_id": c_id}), 200

@app.route('/api/search', methods=['GET'])
def search_engine():
    import database
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({"error": "Missing 'q'"}), 400
    
    results = database.search_index(query)
    return jsonify({"query": query, "count": len(results), "results": results}), 200

@app.route('/api/metrics', methods=['GET'])
def metrics():
    import database
    words, urls = database.get_global_metrics()
    return jsonify({"total_words_in_db": words, "total_visited_urls": urls}), 200

@app.route('/api/crawlers', methods=['GET'])
def get_crawlers():
    return jsonify(crawler.manager.get_stats()), 200

@app.route('/api/state/<crawler_id>', methods=['POST'])
def state_control(crawler_id):
    data = request.get_json()
    if not data or 'action' not in data:
        return jsonify({"error": "Missing 'action'"}), 400
        
    action = data['action']
    success = crawler.manager.control(crawler_id, action)
    if not success:
        return jsonify({"error": f"Crawler {crawler_id} not found"}), 404
        
    return jsonify({"status": "success", "action_taken": action, "crawler_id": crawler_id}), 200

@app.route('/api/logs/<crawler_id>', methods=['GET'])
def get_logs(crawler_id):
    log_file = f"logs/crawler_{crawler_id}.log"
    if not os.path.exists(log_file):
        return jsonify([]), 200
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Return last 50 lines
            return jsonify([line.strip() for line in lines[-50:]]), 200
    except Exception as e:
        return jsonify([f"Error reading logs: {str(e)}"]), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
