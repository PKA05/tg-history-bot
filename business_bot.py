import os
import time
import threading
import sqlite3
import telebot
from telebot import TeleBot, types
from flask import Flask
from datetime import datetime, timezone, timedelta

# Настройка логирования
import logging
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")
bot = TeleBot(TOKEN)

# ВАШ TELEGRAM ID
MY_TELEGRAM_ID = 1551104336
MY_TELEGRAM_ID = 7952667847

DB_FILE = "messages.db"

# ==========================================
# ВРЕМЯ И ДАТА (Tashkent UTC+5)
# ==========================================
def get_tashkent_now():
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=5)

# ==========================================
# АНАЛИЗ ЭМОЦИЙ И ТОНАЛЬНОСТИ
# ==========================================
def analyze_emotion(text):
    if not text:
        return "😐 Нейтральный"
    
    text_lower = text.lower()
    
    romance_words = ["милая", "милый", "целую", "скучаю", "красивая", "люблю", "родная", "родной", "сердце", "обнимаю", "😘", "❤️", "🥰", "😍"]
    secret_words = ["удали", "секрет", "никто не должен знать", "не говори", "сотри", "позже скажу", "🤫", "🔒", "👀"]
    angry_words = ["бесишь", "отвали", "задолбал", "надоело", "хватит", "😡", "🤬", "👿"]
    
    if any(word in text_lower for word in romance_words):
        return "💖 Романтика / Флирт"
    elif any(word in text_lower for word in secret_words):
        return "🤫 Скрытность / Тайны"
    elif any(word in text_lower for word in angry_words):
        return "😡 Раздражение / Агрессия"
    
    return "😐 Нейтральный"

# ==========================================
# БАЗА ДАННЫХ (SQLite с изоляцией по chat_id)
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Составной первичный ключ (msg_id + chat_id) предотвращает путаницу между разными собеседниками
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            msg_id INTEGER,
            chat_id INTEGER,
            content_type TEXT,
            text TEXT,
            file_id TEXT,
            sender_name TEXT,
            chat_title TEXT,
            date_str TEXT,     
            time_str TEXT,     
            timestamp REAL,
            PRIMARY KEY (msg_id, chat_id)
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ [DB] База данных успешно инициализирована!")

init_db()

def save_to_db(msg_id, chat_id, content_type, text=None, file_id=None, sender_name="Неизвестно", chat_title="Личный чат"):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        now_tashkent = get_tashkent_now()
        today_date = now_tashkent.strftime("%Y-%m-%d")
        time_str = now_tashkent.strftime("%H:%M:%S")
        now_ts = time.time()
        
        cursor.execute('''
            INSERT OR REPLACE INTO messages (msg_id, chat_id, content_type, text, file_id, sender_name, chat_title, date_str, time_str, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (msg_id, chat_id, content_type, text, file_id, sender_name, chat_title, today_date, time_str, now_ts))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"❌ [DB] Ошибка сохранения: {e}")

def get_from_db(msg_id, chat_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT content_type, text, file_id, sender_name, chat_title, time_str FROM messages WHERE msg_id = ? AND chat_id = ?', (msg_id, chat_id))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                'type': row[0], 
                'text': row[1], 
                'file_id': row[2],
                'sender_name': row[3] or "Неизвестно",
                'chat_title': row[4] or "Личный чат",
                'time_str': row[5] or "--:--:--"
            }
    except Exception as e:
        print(f"❌ [DB] Ошибка чтения: {e}")
    return None

def get_sender_and_chat_info(message):
    sender_name = "Неизвестно"
    if message.from_user:
        first = message.from_user.first_name or ""
        last = message.from_user.last_name or ""
        username = f" (@{message.from_user.username})" if message.from_user.username else ""
        sender_name = f"{first} {last}{username}".strip()
        
    chat_id = message.chat.id
    if message.chat.type == "private":
        chat_title = sender_name
    else:
        chat_title = message.chat.title or f"Чат {chat_id}"
        
    return chat_id, sender_name, chat_title

# ==========================================
# КОМАНДЫ И МЕНЮ ЧАТОВ
# ==========================================

@bot.message_handler(commands=['start', 'help', 'status'])
def send_welcome(message):
    if message.from_user.id != MY_TELEGRAM_ID:
        return
        
    status_text = (
        "🟢 **Архивариус (Многопользовательский режим)**\n\n"
        "📜 **Доступные команды:**\n"
        "👥 /history — Выбрать диалог и посмотреть его историю\n"
        "📊 /stats — Статистика сообщений и диалогов\n"
        "🗑 /clear_my_history — Очистить всю базу\n"
    )
    bot.reply_to(message, status_text, parse_mode="Markdown")

# Отображение списка УНИКАЛЬНЫХ чатов
@bot.message_handler(commands=['history'])
def show_chats_list(message):
    if message.from_user.id != MY_TELEGRAM_ID:
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Группируем строго по chat_id
        cursor.execute('''
            SELECT chat_id, chat_title, COUNT(msg_id) as msg_count 
            FROM messages 
            GROUP BY chat_id 
            ORDER BY MAX(timestamp) DESC
        ''')
        chats = cursor.fetchall()
        conn.close()

        if not chats:
            bot.send_message(MY_TELEGRAM_ID, "🤷‍♂️ В базе пока нет сохранённых чатов.")
            return

        markup = types.InlineKeyboardMarkup()
        for chat_id, chat_title, count in chats:
            # Используем двоеточие как разделитель (безопасно для отрицательных chat_id)
            btn_text = f"👤 {chat_title} ({count} сообщ.)"
            markup.add(types.InlineKeyboardButton(text=btn_text, callback_data=f"chat:{chat_id}"))

        bot.send_message(MY_TELEGRAM_ID, "📥 **Выберите собеседника для просмотра истории:**", reply_markup=markup, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(MY_TELEGRAM_ID, f"❌ Ошибка загрузки списка чатов: {e}")

# Показ истории ТОЛЬКО для выбранного chat_id
@bot.callback_query_handler(func=lambda call: call.data.startswith("chat:"))
def show_single_chat_history(call):
    if call.from_user.id != MY_TELEGRAM_ID:
        return

    target_chat_id = int(call.data.split(":")[1])

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Выборка строго по целевому chat_id
        cursor.execute('''
            SELECT msg_id, content_type, text, file_id, sender_name, chat_title, time_str, date_str 
            FROM messages 
            WHERE chat_id = ? 
            ORDER BY timestamp DESC LIMIT 30
        ''', (target_chat_id,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            bot.answer_callback_query(call.id, "История этого чата пуста.")
            return

        bot.answer_callback_query(call.id)
        chat_name = rows[0][5]

        report = f"💬 **История диалога: {chat_name}**\n\n"
        for idx, msg in enumerate(reversed(rows), 1):
            msg_id, c_type, text, file_id, sender, chat, msg_time, msg_date = msg
            text_preview = text if text else f"[{c_type.upper()} файл]"
            emo_status = analyze_emotion(text)

            report += (
                f"{idx}. 📅 {msg_date} 🕒 {msg_time} | {emo_status}\n"
                f"👤 От: {sender}\n"
                f"📝 {text_preview}\n"
                f"-------------------------\n\n"
            )

            if len(report) > 3500:
                bot.send_message(MY_TELEGRAM_ID, report, parse_mode="Markdown")
                report = ""

        if report:
            bot.send_message(MY_TELEGRAM_ID, report, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(MY_TELEGRAM_ID, f"❌ Ошибка вывода истории: {e}")

@bot.message_handler(commands=['stats'])
def show_statistics(message):
    if message.from_user.id != MY_TELEGRAM_ID:
        return
        
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM messages")
        total_msgs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT chat_id) FROM messages")
        total_chats = cursor.fetchone()[0]
        conn.close()
        
        stats_msg = (
            f"📊 **Статистика архива:**\n\n"
            f"💬 Активных диалогов: `{total_chats}`\n"
            f"🗄 Всего сообщений в базе: `{total_msgs}`\n"
        )
        bot.send_message(MY_TELEGRAM_ID, stats_msg, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(MY_TELEGRAM_ID, f"❌ Ошибка статистики: {e}")

@bot.message_handler(commands=['clear_my_history'])
def clear_history_db(message):
    if message.from_user.id != MY_TELEGRAM_ID:
        return
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS messages")
        conn.commit()
        conn.close()
        init_db()
        bot.send_message(MY_TELEGRAM_ID, "🗑 **База данных очищена.**", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(MY_TELEGRAM_ID, f"❌ Ошибка очистки: {e}")

# ==========================================
# ОБРАБОТКА ВХОДЯЩИХ БИЗНЕС-СООБЩЕНИЙ
# ==========================================

@bot.business_message_handler(content_types=['text', 'photo', 'video', 'voice', 'document', 'video_note'])
def handle_all_business_messages(message):
    msg_id = message.message_id
    chat_id, sender_name, chat_title = get_sender_and_chat_info(message)
    
    if message.content_type == 'text':
        save_to_db(msg_id, chat_id, 'text', text=message.text, sender_name=sender_name, chat_title=chat_title)
    elif message.content_type == 'photo':
        file_id = message.photo[-1].file_id
        save_to_db(msg_id, chat_id, 'photo', text=message.caption, file_id=file_id, sender_name=sender_name, chat_title=chat_title)
    elif message.content_type == 'video':
        save_to_db(msg_id, chat_id, 'video', text=message.caption, file_id=message.video.file_id, sender_name=sender_name, chat_title=chat_title)
    elif message.content_type == 'voice':
        save_to_db(msg_id, chat_id, 'voice', file_id=message.voice.file_id, sender_name=sender_name, chat_title=chat_title)
    elif message.content_type == 'document':
        save_to_db(msg_id, chat_id, 'document', text=message.caption, file_id=message.document.file_id, sender_name=sender_name, chat_title=chat_title)
    elif message.content_type == 'video_note':
        save_to_db(msg_id, chat_id, 'video_note', file_id=message.video_note.file_id, sender_name=sender_name, chat_title=chat_title)

# ==========================================
# РЕДАКТИРОВАНИЕ И УДАЛЕНИЕ
# ==========================================

@bot.edited_business_message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_edited_business_message(message):
    msg_id = message.message_id
    chat_id, sender_name, chat_title = get_sender_and_chat_info(message)
    
    old_data = get_from_db(msg_id, chat_id)
    old_text = old_data['text'] if old_data and old_data.get('text') else "[Нет текста]"
    new_text = message.text or message.caption
    
    if new_text and old_text != new_text:
        emo_was = analyze_emotion(old_text)
        emo_now = analyze_emotion(new_text)
        
        report = (
            "✏️ **Сообщение ИЗМЕНЕНО!**\n"
            f"💬 Чат: {chat_title}\n"
            f"👤 Автор: {sender_name}\n"
            f"⬅️ Было ({emo_was}): {old_text}\n"
            f"➡️ Стало ({emo_now}): {new_text}"
        )
        try:
            bot.send_message(MY_TELEGRAM_ID, report)
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления: {e}")
        
        save_to_db(msg_id, chat_id, old_data['type'] if old_data else 'text', text=new_text, sender_name=sender_name, chat_title=chat_title)

@bot.deleted_business_messages_handler(func=lambda deleted_messages: True)
def handle_deleted_business_messages(deleted_messages):
    msg_ids = getattr(deleted_messages, 'message_ids', [])
    chat_id = getattr(deleted_messages.chat, 'id', None) if getattr(deleted_messages, 'chat', None) else None

    if not chat_id:
        return

    for msg_id in msg_ids:
        msg_data = get_from_db(msg_id, chat_id)
        
        if msg_data:
            content_type = msg_data['type']
            file_id = msg_data['file_id']
            caption = msg_data['text'] or ""
            sender = msg_data['sender_name']
            chat = msg_data['chat_title']
            emo = analyze_emotion(caption)
            
            if content_type == 'text':
                report = (
                    f"🗑 **Сообщение УДАЛЕНО!** ({emo})\n"
                    f"💬 Чат: {chat}\n"
                    f"👤 Автор: {sender}\n"
                    f"📝 Текст: {msg_data['text']}"
                )
                bot.send_message(MY_TELEGRAM_ID, report)
            elif content_type == 'photo':
                report_caption = f"🗑 Удалено ФОТО!\n💬 Чат: {chat}\n👤 От: {sender}\n📝 Описание: {caption}"
                try: bot.send_photo(MY_TELEGRAM_ID, file_id, caption=report_caption)
                except Exception: bot.send_message(MY_TELEGRAM_ID, report_caption)
            elif content_type == 'video':
                report_caption = f"🗑 Удалено ВИДЕО!\n💬 Чат: {chat}\n👤 От: {sender}\n📝 Описание: {caption}"
                try: bot.send_video(MY_TELEGRAM_ID, file_id, caption=report_caption)
                except Exception: bot.send_message(MY_TELEGRAM_ID, report_caption)
            elif content_type == 'voice':
                try: bot.send_voice(MY_TELEGRAM_ID, file_id, caption=f"🗑 Удалено ГОЛОСОВОЕ!\n💬 Чат: {chat}\n👤 От: {sender}")
                except Exception: bot.send_message(MY_TELEGRAM_ID, f"🗑 Удалено ГОЛОСОВОЕ!\n💬 Чат: {chat}")
            elif content_type == 'video_note':
                try:
                    bot.send_video_note(MY_TELEGRAM_ID, file_id)
                    bot.send_message(MY_TELEGRAM_ID, f"🗑 Удалено ВИДЕОСООБЩЕНИЕ (кругляшок)!\n💬 Чат: {chat}")
                except Exception:
                    bot.send_message(MY_TELEGRAM_ID, f"🗑 Удалено ВИДЕОСООБЩЕНИЕ!\n💬 Чат: {chat}")

# ==========================================
# ВЕБ-СЕРВЕР Flask
# ==========================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Архивариус активен и работает"

def start_polling():
    while True:
        try:
            bot.remove_webhook()
            time.sleep(1)
            bot.infinity_polling(
                timeout=20, 
                long_polling_timeout=10,
                allowed_updates=["message", "business_message", "edited_business_message", "deleted_business_messages"]
            )
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=start_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
