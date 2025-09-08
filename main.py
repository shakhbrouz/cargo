import os
import logging
from flask import Flask, request, jsonify
import telebot
import sqlite3
from datetime import datetime
import threading

# Logging sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Bot sozlamalari (Environment Variables dan)
BOT_TOKEN = os.environ.get('7782454356:AAET7vyNmwrdExSdm-ykw49lq0wQzzXIObIs')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
ADMIN_IDS = [151222479,]

if os.environ.get('ADMIN_IDS'):
    try:
        ADMIN_IDS = [int(x.strip()) for x in os.environ.get('ADMIN_IDS').split(',')]
    except:
        ADMIN_IDS = []

# Bot yaratish
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

def init_db():
    """Ma'lumotlar bazasini yaratish"""
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # Guruhlar jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER UNIQUE,
            title TEXT,
            added_date TEXT
        )
    ''')
    
    # Yuk e'lonlari jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cargo_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            from_city TEXT,
            to_city TEXT,
            cargo_type TEXT,
            weight TEXT,
            price TEXT,
            phone TEXT,
            description TEXT,
            post_date TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")

# Flask routes
@app.route('/')
def home():
    """Bot holati sahifasi"""
    return {
        "status": "Bot ishlayapti",
        "bot_configured": bool(BOT_TOKEN),
        "webhook_url": WEBHOOK_URL,
        "admin_count": len(ADMIN_IDS),
        "timestamp": datetime.now().isoformat()
    }

@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram webhook handler"""
    if not bot:
        return jsonify({'error': 'Bot not configured'})
    
    try:
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return jsonify({'status': 'ok'})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'error': str(e)})

@app.route('/set_webhook')
def set_webhook():
    """Webhook URL ni o'rnatish"""
    if not bot or not WEBHOOK_URL:
        return jsonify({'error': 'Bot yoki webhook URL sozlanmagan'})
    
    try:
        webhook_url = f"{WEBHOOK_URL}/webhook"
        result = bot.set_webhook(url=webhook_url)
        
        if result:
            return jsonify({
                'status': 'success', 
                'webhook_url': webhook_url,
                'message': 'Webhook muvaffaqiyatli o\'rnatildi'
            })
        else:
            return jsonify({'error': 'Webhook o\'rnatishda xatolik'})
            
    except Exception as e:
        logger.error(f"Set webhook error: {e}")
        return jsonify({'error': str(e)})

@app.route('/stats')
def stats():
    """Bot statistikasi"""
    try:
        conn = sqlite3.connect('bot_data.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM groups')
        groups_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM cargo_posts')
        posts_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM cargo_posts WHERE date(post_date) = date("now")')
        today_posts = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'groups_count': groups_count,
            'total_posts': posts_count,
            'today_posts': today_posts,
            'bot_status': 'active' if bot else 'inactive'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)})

# Bot handlers
if bot:
    @bot.message_handler(commands=['start'])
    def start_command(message):
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.row(
            telebot.types.InlineKeyboardButton("Yuk e'lon qilish", callback_data='post_cargo'),
            telebot.types.InlineKeyboardButton("Yuk qidirish", callback_data='search_cargo')
        )
        keyboard.row(
            telebot.types.InlineKeyboardButton("Mening e'lonlarim", callback_data='my_posts'),
            telebot.types.InlineKeyboardButton("Yordam", callback_data='help')
        )
        
        text = f"""🚛 **Yuk Tashish Botiga Xush Kelibsiz!**

👋 Salom {message.from_user.first_name}!

**Bot imkoniyatlari:**
📦 Yuk e'lonlari joylashtirish
🔍 Yuk qidirish va topish
📢 Avtomatik xabar yuborish

**Buyruqlar:**
/help - Yordam
/search <shahar> - Yuk qidirish

Boshlash uchun tugmani tanlang:"""
        
        bot.send_message(message.chat.id, text, reply_markup=keyboard, parse_mode='Markdown')

    @bot.message_handler(commands=['help'])
    def help_command(message):
        help_text = """📚 **Yordam va Ko'rsatmalar**

**🔹 Asosiy buyruqlar:**
- /start - Botni ishga tushirish
- /search <shahar> - Yuk qidirish
- /help - Bu yordam

**🔹 Admin buyruqlari:**
- /broadcast <xabar> - Barcha guruhlarga xabar
- /stats - Statistika

**📝 Misollar:**
- `/search Toshkent` - Toshkent bo'yicha qidirish
- `/broadcast Yangi e'lonlar!` - Xabar yuborish

**💬 Qo'llab-quvvatlash:** @admin_username"""
        
        bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

    @bot.message_handler(commands=['broadcast'])
    def broadcast_command(message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "❌ Sizda bu buyruqni ishlatish huquqi yo'q!")
            return
        
        parts = message.text.split(' ', 1)
        if len(parts) < 2:
            bot.reply_to(message, 
                "📝 **Format:** `/broadcast <xabar matni>`\n\n"
                "**Misol:** `/broadcast Yangi e'lonlar mavjud!`", 
                parse_mode='Markdown'
            )
            return
        
        broadcast_text = parts[1]
        
        try:
            conn = sqlite3.connect('bot_data.db')
            cursor = conn.cursor()
            cursor.execute('SELECT chat_id, title FROM groups')
            groups = cursor.fetchall()
            conn.close()
            
            if not groups:
                bot.reply_to(message, "❌ Hech qanday guruh topilmadi!")
                return
            
            sent = 0
            failed = 0
            
            status_msg = bot.reply_to(message, "📤 Xabar yuborilmoqda...")
            
            for chat_id, title in groups:
                try:
                    bot.send_message(chat_id, broadcast_text, parse_mode='Markdown')
                    sent += 1
                except Exception as e:
                    failed += 1
                    logger.error(f"Broadcast error for {chat_id}: {e}")
            
            result_text = f"""✅ **Xabar yuborish yakunlandi!**

📊 **Natija:**
- ✅ Yuborildi: {sent}
- ❌ Xatolik: {failed}
- 📋 Jami guruhlar: {len(groups)}"""
            
            bot.edit_message_text(result_text, message.chat.id, status_msg.message_id, parse_mode='Markdown')
            
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik yuz berdi: {str(e)}")

    @bot.message_handler(commands=['search'])
    def search_command(message):
        parts = message.text.split(' ', 1)
        if len(parts) < 2:
            bot.reply_to(message, 
                "🔍 **Yuk qidirish:**\n\n"
                "**Format:** `/search <shahar nomi>`\n\n"
                "**Misollar:**\n"
                "• `/search Toshkent`\n"
                "• `/search Samarqand`", 
                parse_mode='Markdown'
            )
            return
        
        search_term = parts[1].lower()
        
        try:
            conn = sqlite3.connect('bot_data.db')
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM cargo_posts 
                WHERE LOWER(from_city) LIKE ? OR LOWER(to_city) LIKE ?
                ORDER BY id DESC LIMIT 5
            ''', (f'%{search_term}%', f'%{search_term}%'))
            
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                bot.reply_to(message, f"❌ **'{search_term}'** bo'yicha e'lonlar topilmadi.", parse_mode='Markdown')
                return
            
            response = f"🔍 **'{search_term}' bo'yicha {len(results)} ta natija:**\n\n"
            
            for i, row in enumerate(results, 1):
                response += f"**{i}. {row[3]} → {row[4]}**\n"
                response += f"📦 {row[5]} | ⚖️ {row[6]}\n"
                response += f"💰 {row[7]} | 📞 {row[8]}\n"
                response += f"📅 {row[10]}\n➖➖➖\n"
            
            bot.reply_to(message, response, parse_mode='Markdown')
            
        except Exception as e:
            bot.reply_to(message, f"❌ Qidiruvda xatolik: {str(e)}")

    @bot.message_handler(commands=['stats'])
    def stats_command(message):
        if message.from_user.id not in ADMIN_IDS:
            bot.reply_to(message, "❌ Sizda bu huquq yo'q!")
            return
            
        try:
            conn = sqlite3.connect('bot_data.db')
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM groups')
            groups_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM cargo_posts')
            posts_count = cursor.fetchone()[0]
            
            conn.close()
            
            stats_text = f"""📊 **Bot Statistikasi**

👥 **Guruhlar soni:** {groups_count}
📦 **E'lonlar soni:** {posts_count}
🕐 **Vaqt:** {datetime.now().strftime('%Y-%m-%d %H:%M')}"""
            
            bot.reply_to(message, stats_text, parse_mode='Markdown')
            
        except Exception as e:
            bot.reply_to(message, f"❌ Statistika xatoligi: {str(e)}")

    # Guruhga qo'shilganda
    @bot.message_handler(content_types=['new_chat_members'])
    def new_member_handler(message):
        for member in message.new_chat_members:
            if member.id == bot.get_me().id:
                chat_id = message.chat.id
                title = message.chat.title or "Guruh"
                
                try:
                    conn = sqlite3.connect('bot_data.db')
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO groups (chat_id, title, added_date)
                        VALUES (?, ?, ?)
                    ''', (chat_id, title, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    conn.commit()
                    conn.close()
                    
                    welcome = f"""✅ **{title}** guruhiga qo'shildi!

🤖 Men yuk tashish botiman.

**Imkoniyatlar:**
- Yuk e'lonlari joylashtirish
- Avtomatik xabar yuborish
- Qidirish tizimi

**Foydalanish:** /start"""
                    
                    bot.send_message(chat_id, welcome, parse_mode='Markdown')
                    logger.info(f"Bot added to group: {title} ({chat_id})")
                    
                except Exception as e:
                    logger.error(f"Error adding group {chat_id}: {e}")

if __name__ == '__main__':
    init_db()
    
    # Railway automatically sets PORT
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)