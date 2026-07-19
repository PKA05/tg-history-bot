import os
import time
import threading
import sqlite3
import random
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
    return datetime.utcnow() + timedelta(hours=5)

def get_tashkent_date(days_offset=0):
    tashkent_now = get_tashkent_now()
    target_date = tashkent_now + timedelta(days=days_offset)
    return target_date.strftime("%Y-%m-%d")

# ==========================================
# УМНЫЙ АНАЛИЗ ТОНАЛЬНОСТИ И ЭМОЦИЙ (AI-МАРКЕРЫ)
# ==========================================
def analyze_emotion(text):
    if not text:
        return "😐 Нейтральный"
    
    text_lower = text.lower()
    
    # Маркеры флирта, романтики, нежности
    romance_words = ["милая", "милый", "целую", "скучаю", "красивая", "люблю", "родная", "родной", "сердце", "обнимаю", "встретиться", "прекрасно выглядишь", "😘", "❤️", "🥰", "😍"]
    # Маркеры скрытности, тайн, подозрений
    secret_words = ["удали", "секрет", "никто не должен знать", "не говори", "сотри", "спрячь", "позже скажу", "не здесь", "позвони лучше", "🤫", "🔒", "👀"]
    # Маркеры агрессии, злости
    angry_words = ["бесишь", "отвали", "задолбал", "надоело", "хватит", "😡", "🤬", "👿"]
    
    if any(word in text_lower for word in romance_words):
        return "💖 Романтика / Флирт"
    elif any(word in text_lower for word in secret_words):
        return "🤫 Скрытность / Тайны"
    elif any(word in text_lower for word in angry_words):
        return "😡 Раздражение / Агрессия"
    
    return "😐 Нейтральный"

# ==========================================
# ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ SQLite
# ==========================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT time_str FROM messages LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("DROP TABLE IF EXISTS messages")
        conn.commit()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            msg_id INTEGER PRIMARY KEY,
            content_type TEXT,
            text TEXT,
            file_id TEXT,
            sender_name TEXT,
            chat_title TEXT,
            date_str TEXT,     
            time_str TEXT,     
            timestamp REAL
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ [DB] База данных успешно инициализирована со всеми функциями!")

init_db()

def save_to_db(msg_id, content_type, text=None, file_id=None, sender_name="Неизвестно", chat_title="Личный чат"):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        now_tashkent = get_tashkent_now()
        today_date = now_tashkent.strftime("%Y-%m-%d")
        time_str = now_tashkent.strftime("%H:%M:%S")
        now_ts = time.time()
        
        cursor.execute('''
            INSERT OR REPLACE INTO messages (msg_id, content_type, text, file_id, sender_name, chat_title, date_str, time_str, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (msg_id, content_type, text, file_id, sender_name, chat_title, today_date, time_str, now_ts))
        
        conn.commit()
        conn.close()
        
        # Вывод анализа в консоль сервера
        emotion = analyze_emotion(text)
        print(f"!!! СРАБОТАЛО СОХРАНЕНИЕ !!! 💾 Эмоция: {emotion} | От {sender_name}")
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
# ЛЮБОВНЫЙ АСТРОЛОГИЧЕСКИЙ ДВИЖОК
# ==========================================
def generate_love_astro(name):
    # Генератор предсказания на основе букв имени, чтобы для одного имени результат в этот день был стабильным
    random.seed(len(name) + int(time.strftime("%d%m%Y")))
    
    loyalty = random.randint(40, 100)  # Уровень верности
    secrets_level = random.randint(10, 95)  # Уровень скрытности
    passion = random.randint(50, 100)  # Страсть
    
    status_list = [
        "🌌 Звезды говорят: этот человек сейчас проживает глубокие внутренние трансформации. В мыслях преобладает сильная привязанность, но есть страх открыться полностью.",
        "✨ Луна в Скорпионе предупреждает: между вами кипит мощная эмоциональная связь, но собеседник склонен утаивать мелкие детали, чтобы казаться загадочнее.",
        "🔮 Венера в Раке указывает на невероятную нежность и потребность в защите. Этот человек ищет стабильности и преданности, флирт на стороне его сейчас не интересует.",
        "🪐 Аспект Меркурия намекает: прямо сейчас человек может искусно лавировать между правдой и фантазией. Доверяй, но обращай внимание на интуицию."
    ]
    
    advice_list = [
        "Следи за резкими изменениями в стиле общения — за ними обычно прячутся скрытые эмоции.",
        "Лучший способ узнать правду — поговорить по душам в тихой, уютной обстановке без лишних свидетелей.",
        "Прямо сейчас звёзды советуют проявить чуть больше тепла, это растопит любую скрытность."
    ]
    
    astro_text = (
        f"🔮 **ЛЮБОВНЫЙ КОСМИЧЕСКИЙ СКАНЕР ДЛЯ: {name}**\n\n"
        f"❤️ **Любовная совместимость:** `{random.randint(65, 99)}%`\n"
        f"💎 **Уровень верности & преданности:** `{loyalty}%`\n"
        f"🤫 **Склонность скрывать мысли:** `{secrets_level}%`\n"
        f"🔥 **Градус страсти в отношениях:** `{passion}%`\n\n"
        f"📜 **Анализ чувств и энергетики:**\n{random.choice(status_list)}\n\n"
        f"💡 **Совет от звезд:** {random.choice(advice_list)}"
    )
    return astro_text

# ==========================================
# 1. ОБЫЧНЫЕ И ИНТЕРАКТИВНЫЕ КОМАНДЫ (В ЛС бота)
# ==========================================

@bot.message_handler(commands=['start', 'status', 'help'])
def send_welcome(message):
    if message.from_user.id != MY_TELEGRAM_ID:
        return
        
    status_text = (
        "🟢 **Архивариус V4.0 Любовный Аналитик (Ташкент UTC+5)**\n\n"
        "📜 **Доступные команды:**\n"
        "📅 /history — Посмотреть архив по дням\n"
        "📊 /stats — Статистика базы и преобладающих эмоций\n"
        "🔍 /search <текст> — Быстрый поиск сообщений\n"
        "🔮 /astro <имя> — Сканер любовной совместимости и верности\n"
        "🗑 /clear_my_history — Очистить историю базы\n"
    )
    bot.reply_to(message, status_text, parse_mode="Markdown")

@bot.message_handler(commands=['astro'])
def love_astro_command(message):
    if message.from_user.id != MY_TELEGRAM_ID:
        return
        
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Напиши имя или юзернейм человека после команды. Пример: `/astro Анна`", parse_mode="Markdown")
        return
        
    target_name = args[1]
    astro_report = generate_love_astro(target_name)
    bot.send_message(MY_TELEGRAM_ID, astro_report, parse_mode="Markdown")

@bot.message_handler(commands=['stats'])
def show_statistics(message):
    if message.from_user.id != MY_TELEGRAM_ID:
        return
        
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM messages")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT text FROM messages WHERE text IS NOT NULL")
        all_texts = cursor.fetchall()
        conn.close()
        
        # Считаем преобладающие эмоции по базе данных
        emotions_count = {"💖 Романтика": 0, "🤫 Скрытность": 0, "😡 Раздражение": 0, "😐 Нейтральные": 0}
        for t in all_texts:
            emo = analyze_emotion(t[0])
            if "Романтика" in emo: emotions_count["💖 Романтика"] += 1
            elif "Скрытность" in emo: emotions_count["🤫 Скрытность"] += 1
            elif "Раздражение" in emo: emotions_count["😡 Раздражение"] += 1
            else: emotions_count["😐 Нейтральные"] += 1
            
        stats_msg = (
            f"📊 **Анализ твоей базы данных:**\n\n"
            f"🗄 Всего сохраненных записей: `{total}`\n\n"
            f"📈 **Преобладающий фон переписок (AI-Тональность):**\n"
            f"💖 Романтика/Флирт: `{emotions_count['💖 Романтика']}` шт.\n"
            f"🤫 Тайны/Скрытность: `{emotions_count['🤫 Скрытность']}` шт.\n"
            f"😡 Раздражение/Ссоры: `{emotions_count['😡 Раздражение']}` шт.\n"
            f"😐 Нейтральные фразы: `{emotions_count['😐 Нейтральные']}` шт.\n"
        )
            
        bot.send_message(MY_TELEGRAM_ID, stats_msg, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(MY_TELEGRAM_ID, f"❌ Ошибка сбора статистики: {e}")

@bot.message_handler(commands=['search'])
def search_messages(message):
    if message.from_user.id != MY_TELEGRAM_ID:
        return
        
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, "⚠️ Пример: `/search люблю`", parse_mode="Markdown")
        return
        
    query = args[1]
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT date_str, time_str, sender_name, text FROM messages WHERE text LIKE ? ORDER BY timestamp DESC LIMIT 10", (f"%{query}%",))
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            bot.send_message(MY_TELEGRAM_ID, f"🔍 По запросу `{query}` ничего не найдено.", parse_mode="Markdown")
            return
            
        search_report = f"🔍 **Результаты поиска по слову '{query}':**\n\n"
        for idx, row in enumerate(results, 1):
            date_str, time_str, sender, text = row
            emo_label = analyze_emotion(text)
            search_report += f"{idx}. 📅 {date_str} {time_str} | Эмоция: {emo_label}\n👤 От: {sender}\n📝 Текст: {text}\n\n"
            
        bot.send_message(MY_TELEGRAM_ID, search_report, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(MY_TELEGRAM_ID, f"❌ Ошибка поиска: {e}")

@bot.message_handler(commands=['clear_my_history'])
def clear_history_db(message):
    if message.from_user.id != MY_TELEGRAM_ID:
        return
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages")
        conn.commit()
        conn.close()
        bot.send_message(MY_TELEGRAM_ID, "🗑 **База данных полностью очищена!**")
    except Exception as e:
        bot.send_message(MY_TELEGRAM_ID, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['history'])
def show_history_menu(message):
    if message.from_user.id != MY_TELEGRAM_ID:
        return

    markup = types.InlineKeyboardMarkup()
    today = get_tashkent_date(days_offset=0)
    yesterday = get_tashkent_date(days_offset=-1)
    prev_day = get_tashkent_date(days_offset=-2)

    markup.add(types.InlineKeyboardButton(text=f"📅 Сегодня ({today})", callback_data=f"date_{today}"))
    markup.add(types.InlineKeyboardButton(text=f"📅 Вчера ({yesterday})", callback_data=f"date_{yesterday}"))
    markup.add(types.InlineKeyboardButton(text=f"📅 Позавчера ({prev_day})", callback_data=f"date_{prev_day}"))
    
    bot.send_message(MY_TELEGRAM_ID, "Выбери дату для просмотра архива:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("date_"))
def handle_date_selection(call):
    selected_date = call.data.split("_")[1]
    messages = get_messages_by_date(selected_date)
    
    if not messages:
        bot.answer_callback_query(call.id, "Пусто")
        bot.send_message(MY_TELEGRAM_ID, f"🤷‍♂️ За дату {selected_date} сообщений нет.")
        return
    
    bot.answer_callback_query(call.id, f"Загружаю {len(messages)} шт.")
    
    report = f"📋 Архив переписок за {selected_date}:\n\n"
    for idx, msg in enumerate(messages, 1):
        msg_id, c_type, text, sender, chat, msg_time = msg
        text_preview = text if text else f"[{c_type.upper()} файл]"
        
        # Добавляем в вывод архива автоматический анализ эмоции сообщения
        emo_status = analyze_emotion(text)
        
        report += (
            f"{idx}. 🕒 Время: {msg_time} | Энергетика: {emo_status}\n"
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
# 2. ПЕРЕХВАТ БИЗНЕС-СООБЩЕНИЙ
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
    old_text = old_data['text'] if old_data and old_data.get('text') else "[Нет текста]"
    new_text = message.text or message.caption
    
    if new_text and old_text != new_text:
        emo_was = analyze_emotion(old_text)
        emo_now = analyze_emotion(new_text)
        
        report = (
            "✏️ Сообщение ИЗМЕНЕНО!\n"
            f"👤 От кого: {sender_name}\n"
            f"💬 Где: {chat_title}\n"
            f"⬅️ Было ({emo_was}): {old_text}\n"
            f"➡️ Стало ({emo_now}): {new_text}"
        )
        try:
            bot.send_message(MY_TELEGRAM_ID, report)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
        
        save_to_db(msg_id, old_data['type'] if old_data else 'text', text=new_text, sender_name=sender_name, chat_title=chat_title)

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
            emo = analyze_emotion(caption)
            
            if content_type == 'text':
                report = (
                    f"🗑 Сообщение УДАЛЕНО! (Анализ: {emo})\n"
                    f"👤 От кого: {sender}\n"
                    f"💬 Где: {chat}\n"
                    f"📝 Текст: {msg_data['text']}"
                )
                bot.send_message(MY_TELEGRAM_ID, report)
            elif content_type == 'photo':
                report_caption = f"🗑 Удалено ФОТО! ({emo})\n👤 От кого: {sender}\n💬 Где: {chat}\n📝 Описание: {caption}"
                try: bot.send_photo(MY_TELEGRAM_ID, file_id, caption=report_caption)
                except Exception: bot.send_message(MY_TELEGRAM_ID, f"{report_caption}\n⚠️ Файл недоступен")
            elif content_type == 'video':
                report_caption = f"🗑 Удалено ВИДЕО! ({emo})\n👤 От кого: {sender}\n💬 Где: {chat}\n📝 Описание: {caption}"
                try: bot.send_video(MY_TELEGRAM_ID, file_id, caption=report_caption)
                except Exception: bot.send_message(MY_TELEGRAM_ID, f"{report_caption}\n⚠️ Файл недоступен")
            elif content_type == 'voice':
                try: bot.send_voice(MY_TELEGRAM_ID, file_id, caption=f"🗑 Удалено ГОЛОСОВОЕ!\n👤 От: {sender}\n💬 В чате: {chat}")
                except Exception: bot.send_message(MY_TELEGRAM_ID, f"🗑 Удалено ГОЛОСОВОЕ!\n👤 От: {sender}")
            elif content_type == 'video_note':
                try:
                    bot.send_video_note(MY_TELEGRAM_ID, file_id)
                    bot.send_message(MY_TELEGRAM_ID, f"🗑 Выше удален КРУГЛЯШОК!\n👤 От: {sender}\n💬 Где: {chat}")
                except Exception:
                    bot.send_message(MY_TELEGRAM_ID, f"🗑 Удалено ВИДЕОСООБЩЕНИЕ!\n👤 От: {sender}")

# ==========================================
# 4. ВЕБ-СЕРВЕР И СТАРТ
# ==========================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Любовный Архивариус V4 активен"

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
