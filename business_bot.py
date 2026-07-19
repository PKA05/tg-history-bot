import os
import time
import threading
import sqlite3
import telebot
from telebot import TeleBot, types
from flask import Flask
from datetime import datetime, timedelta

# Включаем logging
import logging
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")
bot = TeleBot(TOKEN)

# ТВОЙ ЛИЧНЫЙ TELEGRAM ID
MY_TELEGRAM_ID = 1551104336

DB_FILE = "messages.db"

# ==========================================
# ТОЧНОЕ ОПРЕДЕЛЕНИЕ ВРЕМЕНИ И ДАТЫ ПО ТАШКЕНТУ (UTC+5)
# ==========================================
def get_tashkent_now():
    """Возвращает текущее datetime-время по часовому поясу Ташкента (UTC+5)"""
    return datetime.utcnow() + timedelta(hours=5)

def get_tashkent_date(days_offset=0):
    """
    Возвращает дату в формате YYYY-MM-DD для часового пояса Ташкента (UTC+5)
    с возможностью сдвига на days_offset дней.
    """
    tashkent_now = get_tashkent_now()
    target_date = tashkent_now + timedelta(days=days_offset)
    return target_date.strftime("%Y-%m-%d")

# ==========================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ SQLite
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # ПРОВЕРКА И АВТО-МИГРАЦИЯ: Если таблица старая (без колонки time_str), мы её пересоздадим
    try:
        cursor.execute("SELECT time_str FROM messages LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("DROP TABLE IF EXISTS messages")
        print("🔄 [DB] Старая таблица удалена для обновления структуры под вывод времени.")
        conn.commit()

    # Создаем таблицу с правильной структурой (9 колонок)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            msg_id INTEGER PRIMARY KEY,
            content_type TEXT,
            text TEXT,
            file_id TEXT,
            sender_name TEXT,
            chat_title TEXT,
            date_str TEXT,     -- Дата отправки (YYYY-MM-DD)
            time_str TEXT,     -- Время отправки (HH:MM:SS)
            timestamp REAL
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ [DB] База данных успешно инициализирована со всеми колонками!")

init_db()

def save_to_db(msg_id, content_type, text=None, file_id=None, sender_name="Неизвестно", chat_title="Личный чат"):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Получаем точную дату и время по Ташкенту
        now_tashkent = get_tashkent_now()
        today_date = now_tashkent.strftime("%Y-%m-%d")
        time_str = now_tashkent.strftime("%H:%M:%S")
        now_ts = time.time()
        
        # Ровно 9 колонок и 9 значений (?)
        cursor.execute('''
            INSERT OR REPLACE INTO messages (msg_id, content_type, text, file_id, sender_name, chat_title, date_str, time_str, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (msg_id, content_type, text, file_id, sender_name, chat_title, today_date, time_str, now_ts))
        
        conn.commit()
        conn.close()
        # Выводим жесткий лог для проверки работы перехвата
        print(f"!!! СРАБОТАЛО СОХРАНЕНИЕ !!! 💾 ({content_type}) от {sender_name} в {time_str} | Дата: {today_date}")
    except Exception as e:
        print(f"❌ [DB] Критическая ошибка сохранения: {e}")

def get_from_db(msg_id):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT content_type, text, file_id, sender_name, chat_title, time_str FROM messages WHERE msg_id = ?', (msg_id,))
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

def get_messages_by_date(date_str):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT msg_id, content_type, text, sender_name, chat_title, time_str FROM messages WHERE date_str = ? ORDER BY timestamp ASC', (date_str,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"❌ [DB] Ошибка поиска по дате: {e}")
        return []

# ==========================================
# Вспомогательная функция для получения инфо об авторе
# ==========================================
def get_sender_and_chat_info(message):
    if message.from_user:
        first_name = message.from_user.first_name or ""
        last_name = message.from_user.last_name or ""
        username = f" (@{message.from_user.username})" if message.from_user.username else ""
        sender_name = f"{first_name} {last_name}{username}".strip()
    else:
        sender_name = "Неизвестный отправитель"
        
    if message.chat:
        if message.chat.type == "private":
            chat_title = "Личная переписка"
        else:
            chat_title = message.chat.title or "Групповой чат"
    else:
        chat_title = "Бизнес-чат"
        
    return sender_name, chat_title

# ==========================================
# 1. ОБЫЧНЫЕ КОМАНДЫ И ПОИСК ПО ДАТАМ (В ЛС бота)
# ==========================================

@bot.message_handler(commands=['start', 'status'])
def send_welcome(message):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM messages')
    total_msgs = cursor.fetchone()[0]
    conn.close()

    status_text = (
        "🟢 Бизнес-бот Архивариус V3.5 (UTC+5 Ташкент) активен!\n\n"
        f"🗄 Всего сообщений в базе: {total_msgs}\n"
        f"👤 Твой ID: {message.from_user.id}\n"
        "📅 Для просмотра архива по датам введи команду: /history"
    )
    bot.reply_to(message, status_text)

@bot.message_handler(commands=['history'])
def show_history_menu(message):
    if message.from_user.id != MY_TELEGRAM_ID:
        return

    markup = types.InlineKeyboardMarkup()
    
    # Считаем точные даты по Ташкенту
    today = get_tashkent_date(days_offset=0)
    yesterday = get_tashkent_date(days_offset=-1)
    prev_day = get_tashkent_date(days_offset=-2)

    markup.add(types.InlineKeyboardButton(text=f"📅 Сегодня ({today})", callback_data=f"date_{today}"))
    markup.add(types.InlineKeyboardButton(text=f"📅 Вчера ({yesterday})", callback_data=f"date_{yesterday}"))
    markup.add(types.InlineKeyboardButton(text=f"📅 Позавчера ({prev_day})", callback_data=f"date_{prev_day}"))
    
    bot.send_message(
        MY_TELEGRAM_ID, 
        "Выбери дату, за которую ты хочешь посмотреть список сохраненных сообщений в базе:", 
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("date_"))
def handle_date_selection(call):
    selected_date = call.data.split("_")[1]
    messages = get_messages_by_date(selected_date)
    
    if not messages:
        bot.answer_callback_query(call.id, "Пусто")
        bot.send_message(MY_TELEGRAM_ID, f"🤷‍♂️ В базе нет сохраненных сообщений за дату: {selected_date}")
        return
    
    bot.answer_callback_query(call.id, f"Загружаю {len(messages)} шт.")
    
    report = f"📋 Архив переписок за {selected_date}:\n\n"
    for idx, msg in enumerate(messages, 1):
        msg_id, c_type, text, sender, chat, msg_time = msg
        text_preview = text if text else f"[{c_type.upper()} файл]"
        
        # Структурированный вывод с точным временем отправки
        report += (
            f"{idx}. 🕒 Время: {msg_time}\n"
            f"💬 Чат: {chat}\n"
            f"👤 Отправитель: {sender}\n"
            f"📝 Текст: {text_preview}\n"
            f"-------------------------\n\n"
        )
        
        if len(report) > 3500:
            bot.send_message(MY_TELEGRAM_ID, report)
            report = ""
            
    if report:
        bot.send_message(MY_TELEGRAM_ID, report)

# ==========================================
# 2. ПЕРЕХВАТ И СОХРАНЕНИЕ БИЗНЕС-СООБЩЕНИЙ
# ==========================================

@bot.business_message_handler(content_types=['text', 'photo', 'video', 'voice', 'document', 'video_note'])
def handle_all_business_messages(message):
    msg_id = getattr(message, 'business_message_id', None) or message.message_id
    sender_name, chat_title = get_sender_and_chat_info(message)
    
    if message.content_type == 'text':
        save_to_db(msg_id, 'text', text=message.text, sender_name=sender_name, chat_title=chat_title)
    elif message.content_type == 'photo':
        file_id = message.photo[-1].file_id
        save_to_db(msg_id, 'photo', text=message.caption, file_id=file_id, sender_name=sender_name, chat_title=chat_title)
    elif message.content_type == 'video':
        save_to_db(msg_id, 'video', text=message.caption, file_id=message.video.file_id, sender_name=sender_name, chat_title=chat_title)
    elif message.content_type == 'voice':
        save_to_db(msg_id, 'voice', file_id=message.voice.file_id, sender_name=sender_name, chat_title=chat_title)
    elif message.content_type == 'document':
        save_to_db(msg_id, 'document', text=message.caption, file_id=message.document.file_id, sender_name=sender_name, chat_title=chat_title)
    elif message.content_type == 'video_note':
        save_to_db(msg_id, 'video_note', file_id=message.video_note.file_id, sender_name=sender_name, chat_title=chat_title)

# ==========================================
# 3. ОТСЛЕЖИВАНИЕ ИЗМЕНЕНИЙ И УДАЛЕНИЙ
# ==========================================

@bot.edited_business_message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_edited_business_message(message):
    msg_id = getattr(message, 'business_message_id', None) or message.message_id
    sender_name, chat_title = get_sender_and_chat_info(message)
    
    old_data = get_from_db(msg_id)
    old_text = old_data['text'] if old_data and old_data.get('text') else "[Нет текста в памяти]"
    new_text = message.text or message.caption
    
    if new_text and old_text != new_text:
        report = (
            "✏️ Сообщение ИЗМЕНЕНО!\n"
            f"👤 От кого: {sender_name}\n"
            f"💬 Где: {chat_title}\n"
            f"⬅️ Было: {old_text}\n"
            f"➡️ Стало: {new_text}"
        )
        try:
            bot.send_message(MY_TELEGRAM_ID, report)
        except Exception as e:
            print(f"❌ Ошибка отправки изменения: {e}")
        
        save_to_db(
            msg_id, 
            old_data['type'] if old_data else 'text', 
            text=new_text, 
            file_id=old_data['file_id'] if old_data else None,
            sender_name=sender_name,
            chat_title=chat_title
        )

@bot.deleted_business_messages_handler(func=lambda deleted_messages: True)
def handle_deleted_business_messages(deleted_messages):
    msg_ids = getattr(deleted_messages, 'message_ids', [])
    
    for msg_id in msg_ids:
        msg_data = get_from_db(msg_id)
        if msg_data:
            content_type = msg_data['type']
            file_id = msg_data['file_id']
            caption = msg_data['text'] or ""
            sender = msg_data['sender_name']
            chat = msg_data['chat_title']
            
            # А. Текст
            if content_type == 'text':
                report = (
                    "🗑 Сообщение УДАЛЕНО!\n"
                    f"👤 От кого: {sender}\n"
                    f"💬 Где: {chat}\n"
                    f"📝 Текст: {msg_data['text']}"
                )
                bot.send_message(MY_TELEGRAM_ID, report)
                
            # Б. Фото
            elif content_type == 'photo':
                report_caption = (
                    "🗑 Удалено ФОТО!\n"
                    f"👤 От кого: {sender}\n"
                    f"💬 Где: {chat}\n"
                    f"📝 Описание: {caption}"
                )
                try:
                    bot.send_photo(MY_TELEGRAM_ID, file_id, caption=report_caption)
                except Exception:
                    bot.send_message(MY_TELEGRAM_ID, f"{report_caption}\n⚠️ (Файл недоступен)")
                    
            # В. Видео
            elif content_type == 'video':
                report_caption = (
                    "🗑 Удалено ВИДЕО!\n"
                    f"👤 От кого: {sender}\n"
                    f"💬 Где: {chat}\n"
                    f"📝 Описание: {caption}"
                )
                try:
                    bot.send_video(MY_TELEGRAM_ID, file_id, caption=report_caption)
                except Exception:
                    bot.send_message(MY_TELEGRAM_ID, f"{report_caption}\n⚠️ (Файл недоступен)")
                    
            # Г. Голосовое
            elif content_type == 'voice':
                try:
                    bot.send_voice(MY_TELEGRAM_ID, file_id, caption=f"🗑 Удалено ГОЛОСОВОЕ!\n👤 От: {sender}\n💬 В чате: {chat}")
                except Exception:
                    bot.send_message(MY_TELEGRAM_ID, f"🗑 Удалено ГОЛОСОВОЕ!\n👤 От: {sender}\n💬 В чате: {chat}\n⚠️ (Файл недоступен)")
                    
            # Д. КРУГЛЯШОК (Видеосообщение)
            elif content_type == 'video_note':
                try:
                    bot.send_video_note(MY_TELEGRAM_ID, file_id)
                    bot.send_message(MY_TELEGRAM_ID, f"🗑 Выше было удалено ВИДЕОСООБЩЕНИЕ (кругляшок)!\n👤 От кого: {sender}\n💬 Где: {chat}")
                except Exception:
                    bot.send_message(MY_TELEGRAM_ID, f"🗑 Удалено ВИДЕОСООБЩЕНИЕ (кругляшок)!\n👤 От кого: {sender}\n💬 Где: {chat}\n⚠️ (Файл недоступен)")
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
