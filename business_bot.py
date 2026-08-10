import sqlite3
import telebot
from telebot import types
from datetime import datetime

# ==========================================
# НАСТРОЙКИ
# ==========================================
BOT_TOKEN = "ВАШ_ТОКЕН_БОТА"
ADMIN_ID = 123456789  # Ваш Telegram ID (число)
DB_FILE = "business_bot.db"

bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# БАЗА ДАННЫХ
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Таблица подключенных Business-пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS connections (
            user_id INTEGER PRIMARY KEY,
            user_name TEXT,
            connection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица всех сообщений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER,
            chat_id INTEGER,
            business_connection_id TEXT,
            sender_name TEXT,
            chat_title TEXT,
            content_type TEXT,
            text TEXT,
            timestamp INTEGER,
            PRIMARY KEY (message_id, chat_id)
        )
    ''')
    
    # Таблица правки и удалений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS message_edits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            chat_id INTEGER,
            old_text TEXT,
            edit_timestamp INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ==========================================
# ОБРАБОТКА BUSINESS CONNECTION (ПОДКЛЮЧЕНИЯ)
# ==========================================
@bot.business_connection_handler()
def handle_business_connection(connection: types.BusinessConnection):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if connection.is_enabled:
        user_name = connection.user.first_name
        if connection.user.last_name:
            user_name += f" {connection.user.last_name}"
        if connection.user.username:
            user_name += f" (@{connection.user.username})"
            
        cursor.execute('''
            INSERT OR REPLACE INTO connections (user_id, user_name) 
            VALUES (?, ?)
        ''', (connection.user.id, user_name))
        
        safe_name = telebot.formatting.escape_html(user_name)
        bot.send_message(
            ADMIN_ID, 
            f"✅ <b>Новое Business-подключение!</b>\nПользователь: {safe_name} (ID: <code>{connection.user.id}</code>)",
            parse_mode="HTML"
        )
    else:
        cursor.execute('DELETE FROM connections WHERE user_id = ?', (connection.user.id,))
        bot.send_message(
            ADMIN_ID, 
            f"❌ <b>Пользователь отключил Business:</b> ID <code>{connection.user.id}</code>",
            parse_mode="HTML"
        )
        
    conn.commit()
    conn.close()

# ==========================================
# ОБРАБОТКА ВХОДЯЩИХ/СОХРАНЕННЫХ СООБЩЕНИЙ
# ==========================================
@bot.business_message_handler(func=lambda message: True)
def handle_business_message(message: types.Message):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    sender = message.from_user.first_name if message.from_user else "Неизвестный"
    if message.from_user and message.from_user.last_name:
        sender += f" {message.from_user.last_name}"
        
    chat_title = message.chat.title or message.chat.first_name or "Личный чат"
    text_content = message.text or message.caption or ""
    
    cursor.execute('''
        INSERT OR REPLACE INTO messages 
        (message_id, chat_id, business_connection_id, sender_name, chat_title, content_type, text, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        message.message_id,
        message.chat.id,
        message.business_connection_id,
        sender,
        chat_title,
        message.content_type,
        text_content,
        message.date
    ))
    
    conn.commit()
    conn.close()

# ==========================================
# ОБРАБОТКА РЕДАКТИРОВАНИЯ СООБЩЕНИЙ
# ==========================================
@bot.edited_business_message_handler(func=lambda message: True)
def handle_business_message_edit(message: types.Message):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT text FROM messages WHERE message_id = ? AND chat_id = ?
    ''', (message.message_id, message.chat.id))
    row = cursor.fetchone()
    
    old_text = row[0] if row else "[Текст не найден в базах]"
    new_text = message.text or message.caption or ""
    
    cursor.execute('''
        INSERT INTO message_edits (message_id, chat_id, old_text, edit_timestamp)
        VALUES (?, ?, ?, ?)
    ''', (message.message_id, message.chat.id, old_text, message.edit_date or message.date))
    
    cursor.execute('''
        UPDATE messages SET text = ? WHERE message_id = ? AND chat_id = ?
    ''', (new_text, message.message_id, message.chat.id))
    
    conn.commit()
    conn.close()
    
    sender = message.from_user.first_name if message.from_user else "Неизвестный"
    
    safe_sender = telebot.formatting.escape_html(sender)
    safe_old = telebot.formatting.escape_html(old_text)
    safe_new = telebot.formatting.escape_html(new_text)
    
    notify_text = (
        f"✏️ <b>Сообщение отредактировано!</b>\n"
        f"👤 <b>Отправитель:</b> {safe_sender}\n\n"
        f"❌ <b>Было:</b>\n{safe_old}\n\n"
        f"✅ <b>Стало:</b>\n{safe_new}"
    )
    bot.send_message(ADMIN_ID, notify_text, parse_mode="HTML")

# ==========================================
# ОБРАБОТКА УДАЛЕНИЯ СООБЩЕНИЙ
# ==========================================
@bot.deleted_business_message_handler(func=lambda message: True)
def handle_business_message_delete(message: types.Message):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT sender_name, chat_title, content_type, text, timestamp 
        FROM messages 
        WHERE message_id = ? AND chat_id = ?
    ''', (message.message_id, message.chat.id))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        sender_name, chat_title, content_type, text, timestamp = row
        
        safe_sender = telebot.formatting.escape_html(sender_name)
        safe_chat = telebot.formatting.escape_html(chat_title)
        safe_text = telebot.formatting.escape_html(text) if text else f"[{content_type}]"
        
        notify_text = (
            f"🗑 <b>Удалено сообщение!</b>\n"
            f"👤 <b>От:</b> {safe_sender}\n"
            f"💬 <b>Чат:</b> {safe_chat}\n\n"
            f"📄 <b>Содержимое:</b>\n{safe_text}"
        )
        bot.send_message(ADMIN_ID, notify_text, parse_mode="HTML")

# ==========================================
# КОМАНДЫ ДЛЯ АДМИНИСТРАТОРА (HTML ПАРСИНГ)
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    text = (
        "✨ <b>Что я умею:</b>\n"
        "• Сохраняю удаленные сообщения (текст, фото, видео, голосовые, кругляшки).\n"
        "• Покажу, что было в сообщении ДО редактирования.\n"
        "• Все отчёты приходят только вам в этот чат!"
    )
    bot.reply_to(message, text, parse_mode="HTML")

@bot.message_handler(commands=['stats'])
def admin_stats(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(DISTINCT user_id) FROM connections')
        users_count = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT COUNT(*) FROM messages')
        msg_count = cursor.fetchone()[0] or 0
        
        cursor.execute('SELECT DISTINCT user_id, user_name FROM connections')
        users_list = cursor.fetchall()
        conn.close()

        text = "📊 <b>СТАТИСТИКА БОТА:</b>\n\n"
        text += f"👥 Всего пользователей Business: <b>{users_count}</b>\n"
        text += f"💾 Всего сохраненных сообщений: <b>{msg_count}</b>\n\n"
        text += "📋 <b>Список пользователей:</b>\n"
        
        if users_list:
            for u in users_list:
                name = telebot.formatting.escape_html(u[1]) if u[1] else "Без имени"
                text += f"• {name} (ID: <code>{u[0]}</code>)\n"
        else:
            text += "Пока нет подключенных пользователей.\n"

        bot.reply_to(message, text, parse_mode="HTML")
    except Exception as e:
        print(f"❌ [Stats Error]: {e}")
        bot.reply_to(message, f"❌ Ошибка при получении статистики: {telebot.formatting.escape_html(str(e))}", parse_mode="HTML")

@bot.message_handler(commands=['history'])
def admin_history(message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT chat_id, 
                   COALESCE(chat_title, sender_name, 'Неизвестный чат') as display_name, 
                   COUNT(*) 
            FROM messages 
            GROUP BY chat_id
            ORDER BY timestamp DESC
            LIMIT 20
        ''')
        chats = cursor.fetchall()
        conn.close()

        if not chats:
            bot.reply_to(message, "📭 В базе пока нет сохраненных сообщений.")
            return

        markup = types.InlineKeyboardMarkup()
        for c in chats:
            chat_id, display_name, count = c
            short_name = (display_name[:25] + '..') if len(display_name) > 25 else display_name
            btn_text = f"👤 {short_name} ({count} сообщ.)"
            markup.add(types.InlineKeyboardButton(text=btn_text, callback_data=f"hist_{chat_id}"))

        bot.reply_to(message, "📂 <b>Выберите чат из базы данных для просмотра:</b>", reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        print(f"❌ [History Error]: {e}")
        bot.reply_to(message, f"❌ Ошибка при получении истории: {telebot.formatting.escape_html(str(e))}", parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith('hist_'))
def callback_history_chat(call):
    if call.from_user.id != ADMIN_ID:
        return

    try:
        chat_id = int(call.data.split('_')[1])
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COALESCE(sender_name, 'Неизвестный'), content_type, text, timestamp 
            FROM messages 
            WHERE chat_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 15
        ''', (chat_id,))
        msgs = cursor.fetchall()
        conn.close()

        if not msgs:
            bot.answer_callback_query(call.id, "Сообщений не найдено.")
            return

        text = f"📜 <b>Последние сообщения чата (<code>{chat_id}</code>):</b>\n\n"
        for m in reversed(msgs):
            sender = telebot.formatting.escape_html(m[0])
            c_type = m[1]
            msg_text = telebot.formatting.escape_html(m[2]) if m[2] else f"[{c_type}]"
            ts = m[3]
            dt = datetime.fromtimestamp(ts).strftime('%H:%M:%S') if ts else "--:--:--"
            text += f"[{dt}] <b>{sender}</b>: {msg_text}\n"

        bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"❌ [Callback Error]: {e}")
        bot.answer_callback_query(call.id, "Ошибка при загрузке истории.")

# ==========================================
# ЗАПУСК БОТА
# ==========================================
if __name__ == "__main__":
    print("🚀 Бот запущен и ожидает событий...")
    bot.infinity_polling(allowed_updates=["message", "edited_message", "business_connection", "business_message", "edited_business_message", "deleted_business_message", "callback_query"])
