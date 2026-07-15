import os
import time
import threading
import sqlite3
import telebot
from telebot import TeleBot, types
from flask import Flask
from datetime import datetime

# Включаем логирование
import logging
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")
bot = TeleBot(TOKEN)

# ТВОЙ ЛИЧНЫЙ TELEGRAM ID
MY_TELEGRAM_ID = 1551104336

DB_FILE = "messages.db"

# ==========================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ SQLite
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Создаем таблицу для хранения сообщений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            msg_id INTEGER PRIMARY KEY,
            content_type TEXT,
            text TEXT,
            file_id TEXT,
            date_str TEXT, -- Храним дату в формате YYYY-MM-DD
            timestamp REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def save_to_db(msg_id, content_type, text=None, file_id=None):
    """Безопасное сохранение сообщения в базу данных SQLite"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Получаем текущую дату в формате ГГГГ-ММ-ДД
        today_date = datetime.now().strftime("%Y-%m-%d")
        now_ts = time.time()
        
        cursor.execute('''
            INSERT OR REPLACE INTO messages (msg_id, content_type, text, file_id, date_str, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (msg_id, content_type, text, file_id, today_date, now_ts))
        
        conn.commit()
        conn.close()
        print(f"💾 [DB] Успешно сохранено в базу ({content_type}) {msg_id}")
    except Exception as e:
        print(f"❌ [DB] Ошибка сохранения: {e}")

def get_from_db(msg_id):
    """Получение сообщения из базы данных SQLite"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT content_type, text, file_id FROM messages WHERE msg_id = ?', (msg_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {'type': row[0], 'text': row[1], 'file_id': row[2]}
    except Exception as e:
        print(f"❌ [DB] Ошибка чтения: {e}")
    return None

def get_messages_by_date(date_str):
    """Получение списка сообщений за определенную дату"""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT msg_id, content_type, text FROM messages WHERE date_str = ?', (date_str,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"❌ [DB] Ошибка поиска по дате: {e}")
        return []

# ==========================================
# 1. ОБЫЧНЫЕ КОМАНДЫ И ПОИСК ПО ДАТАМ (В ЛС бота)
# ==========================================

@bot.message_handler(commands=['start', 'status'])
def send_welcome(message):
    # Считаем сколько всего сообщений в базе
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM messages')
    total_msgs = cursor.fetchone()[0]
    conn.close()

    status_text = (
        "🟢 Бизнес-бот с вечной памятью SQLite активен!\n\n"
        f"🗄 Всего сообщений в базе: {total_msgs}\n"
        f"👤 Твой ID: {message.from_user.id}\n"
        "📅 Для просмотра архива по датам введи команду: /history"
    )
    bot.reply_to(message, status_text)

# Команда для выбора истории
@bot.message_handler(commands=['history'])
def show_history_menu(message):
    if message.from_user.id != MY_TELEGRAM_ID:
        return

    # Создаем кнопки с быстрыми датами
    markup = types.InlineKeyboardMarkup()
    
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = datetime.fromtimestamp(time.time() - 86400).strftime("%Y-%m-%d")
    prev_day = datetime.fromtimestamp(time.time() - 172800).strftime("%Y-%m-%d")

    markup.add(types.InlineKeyboardButton(text=f"📅 Сегодня ({today})", callback_data=f"date_{today}"))
    markup.add(types.InlineKeyboardButton(text=f"📅 Вчера ({yesterday})", callback_data=f"date_{yesterday}"))
    markup.add(types.InlineKeyboardButton(text=f"📅 Позавчера ({prev_day})", callback_data=f"date_{prev_day}"))
    
    bot.send_message(
        MY_TELEGRAM_ID, 
        "Выбери дату, за которую ты хочешь посмотреть список сохраненных сообщений в базе:", 
        reply_markup=markup
    )

# Обработка нажатия на кнопку даты
@bot.callback_query_handler(func=lambda call: call.data.startswith("date_"))
def handle_date_selection(call):
    selected_date = call.data.split("_")[1]
    messages = get_messages_by_date(selected_date)
    
    if not messages:
        bot.answer_callback_query(call.id, "За эту дату сообщений не найдено.")
        bot.send_message(MY_TELEGRAM_ID, f"🤷‍♂️ В базе нет сохраненных сообщений за дату: {selected_date}")
        return
    
    bot.answer_callback_query(call.id, f"Загружаю {len(messages)} шт.")
    
    report = f"📋 **Архив сообщений за {selected_date}:**\n\n"
    for idx, msg in enumerate(messages, 1):
        msg_id, c_type, text = msg
        text_preview = text if text else f"[{c_type.upper()} файл]"
        report += f"{idx}. ID: `{msg_id}` | Тип: *{c_type}*\n📝 Текст: {text_preview}\n\n"
        
        # Чтобы сообщение не превысило лимит Telegram в 4096 символов
        if len(report) > 3500:
            bot.send_message(MY_TELEGRAM_ID, report, parse_mode="Markdown")
            report = ""
            
    if report:
        bot.send_message(MY_TELEGRAM_ID, report, parse_mode="Markdown")

# ==========================================
# 2. ПЕРЕХВАТ И СОХРАНЕНИЕ БИЗНЕС-СООБЩЕНИЙ
# ==========================================

@bot.business_message_handler(content_types=['text', 'photo', 'video', 'voice', 'document', 'video_note'])
def handle_all_business_messages(message):
    msg_id = getattr(message, 'business_message_id', None) or message.message_id
    
    if message.content_type == 'text':
        save_to_db(msg_id, 'text', text=message.text)
    elif message.content_type == 'photo':
        file_id = message.photo[-1].file_id
        save_to_db(msg_id, 'photo', text=message.caption, file_id=file_id)
    elif message.content_type == 'video':
        save_to_db(msg_id, 'video', text=message.caption, file_id=message.video.file_id)
    elif message.content_type == 'voice':
        save_to_db(msg_id, 'voice', file_id=message.voice.file_id)
    elif message.content_type == 'document':
        save_to_db(msg_id, 'document', text=message.caption, file_id=message.document.file_id)
    elif message.content_type == 'video_note':
        save_to_db(msg_id, 'video_note', file_id=message.video_note.file_id)

# ==========================================
# 3. ОТСЛЕЖИВАНИЕ ИЗМЕНЕНИЙ И УДАЛЕНИЙ
# ==========================================

@bot.edited_business_message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_edited_business_message(message):
    msg_id = getattr(message, 'business_message_id', None) or message.message_id
    user = message.from_user.username or message.from_user.first_name
    
    old_data = get_from_db(msg_id)
    old_text = old_data['text'] if old_data and old_data.get('text') else "[Нет текста в памяти]"
    new_text = message.text or message.caption
    
    if new_text and old_text != new_text:
        report = (
            "✏️ Сообщение изменено!\n"
            f"👤 От кого: @{user}\n"
            f"⬅️ Было: {old_text}\n"
            f"➡️ Стало: {new_text}"
        )
        try:
            bot.send_message(MY_TELEGRAM_ID, report)
        except Exception as e:
            print(f"❌ Ошибка отправки изменения: {e}")
        
        # Обновляем в базе данных
        save_to_db(msg_id, old_data['type'] if old_data else 'text', text=new_text, file_id=old_data['file_id'] if old_data else None)

@bot.deleted_business_messages_handler(func=lambda deleted_messages: True)
def handle_deleted_business_messages(deleted_messages):
    msg_ids = getattr(deleted_messages, 'message_ids', [])
    
    for msg_id in msg_ids:
        msg_data = get_from_db(msg_id)
        if msg_data:
            content_type = msg_data['type']
            file_id = msg_data['file_id']
            caption = msg_data['text'] or ""
            
            if content_type == 'text':
                report = f"🗑 Сообщение УДАЛЕНО!\n📝 Текст: {msg_data['text']}"
                bot.send_message(MY_TELEGRAM_ID, report)
            elif content_type == 'photo':
                report_caption = f"🗑 Удалено ФОТО!\n📝 Описание: {caption}"
                try:
                    bot.send_photo(MY_TELEGRAM_ID, file_id, caption=report_caption)
                except Exception:
                    bot.send_message(MY_TELEGRAM_ID, f"🗑 Удалено ФОТО (файл недоступен). Описание: {caption}")
            elif content_type == 'video':
                report_caption = f"🗑 Удалено ВИДЕО!\n📝 Описание: {caption}"
                try:
                    bot.send_video(MY_TELEGRAM_ID, file_id, caption=report_caption)
                except Exception:
                    bot.send_message(MY_TELEGRAM_ID, report_caption)
            elif content_type == 'voice':
                try:
                    bot.send_voice(MY_TELEGRAM_ID, file_id, caption="🗑 Удалено ГОЛОСОВОЕ!")
                except Exception:
                    bot.send_message(MY_TELEGRAM_ID, "🗑 Удалено ГОЛОСОВОЕ сообщение (файл недоступен)")
            elif content_type == 'video_note':
                try:
                    bot.send_video_note(MY_TELEGRAM_ID, file_id)
                    bot.send_message(MY_TELEGRAM_ID, "🗑 Выше было удалено ВИДЕОСООБЩЕНИЕ (круглышок)!")
                except Exception:
                    bot.send_message(MY_TELEGRAM_ID, "🗑 Удалено ВИДЕОСООБЩЕНИЕ (кругляшок)")
        else:
            print(f"⚠️ Сообщение {msg_id} удалено, но его данных нет в SQLite")

# ==========================================
# 4. ВЕБ-СЕРВЕР И СТАРТ
# ==========================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Медиа-бот Архивариус с БД активен"

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
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=start_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
