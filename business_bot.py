import os
import time
import threading
import telebot
from telebot import TeleBot, types
from flask import Flask

# Включаем логирование в консоль Render
import logging
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")
bot = TeleBot(TOKEN)

# ТВОЙ ЛИЧНЫЙ TELEGRAM ID
MY_TELEGRAM_ID = 1551104336

# Директория для временного сохранения медиафайлов
DOWNLOAD_DIR = "downloads"
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

# База данных сообщений в памяти (ID -> Данные)
messages_db = {}

# ==========================================
# 1. ОБЫЧНЫЕ КОМАНДЫ (Для теста в ЛС)
# ==========================================

@bot.message_handler(commands=['start', 'status'])
def send_welcome(message):
    status_text = (
        "🟢 Бизнес-бот (Стабильная медиа-версия) успешно работает!\n\n"
        f"📦 Сообщений в памяти: {len(messages_db)}\n"
        f"👤 Твой ID: {message.from_user.id}\n"
        "📡 Запущен из файла: business_bot.py"
    )
    bot.reply_to(message, status_text)

@bot.message_handler(func=lambda message: message.chat.type == "private")
def echo_all(message):
    bot.reply_to(message, f"Получил сообщение в ЛС: '{message.text}'")

# ==========================================
# 2. ХРАНЕНИЕ МЕДИА И ТЕКСТА
# ==========================================

def save_message_to_db(msg_id, content_type, text=None, file_id=None):
    """Сохранение данных в память"""
    if text or file_id:
        messages_db[msg_id] = {
            'type': content_type,
            'text': text,
            'file_id': file_id,
            'time': time.time()
        }
        print(f"📥 [Бизнес] Сохранено ({content_type}) {msg_id}: '{text or '[Медиа]'}'")
    
# Ловим все типы контента: текст, фото, видео, голосовые, документы
@bot.business_message_handler(content_types=['text', 'photo', 'video', 'voice', 'document'])
def handle_all_business_messages(message):
    msg_id = getattr(message, 'business_message_id', None) or message.message_id
    
    # 1. Если это текст
    if message.content_type == 'text':
        save_message_to_db(msg_id, 'text', text=message.text)
        
    # 2. Если это фото
    elif message.content_type == 'photo':
        file_id = message.photo[-1].file_id
        save_message_to_db(msg_id, 'photo', text=message.caption, file_id=file_id)
        
    # 3. Если это видео
    elif message.content_type == 'video':
        save_message_to_db(msg_id, 'video', text=message.caption, file_id=message.video.file_id)
        
    # 4. Если это голосовое
    elif message.content_type == 'voice':
        save_message_to_db(msg_id, 'voice', file_id=message.voice.file_id)
        
    # 5. Если это документ
    elif message.content_type == 'document':
        save_message_to_db(msg_id, 'document', text=message.caption, file_id=message.document.file_id)

# ==========================================
# 3. ОТСЛЕЖИВАНИЕ ИЗМЕНЕНИЙ И УДАЛЕНИЙ
# ==========================================

# Ловим изменения сообщений
@bot.edited_business_message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_edited_business_message(message):
    msg_id = getattr(message, 'business_message_id', None) or message.message_id
    user = message.from_user.username or message.from_user.first_name
    
    # Ищем старые данные
    old_data = messages_db.get(msg_id)
    old_text = old_data['text'] if old_data and old_data.get('text') else "[Нет текста в памяти]"
    
    # Получаем измененный текст (или подпись под медиафайлом)
    new_text = message.text or message.caption
    
    if new_text and old_text != new_text:
        report = (
            "✏️ Сообщение изменено!\n"
            f"👤 От кого: @{user}\n"
            f"⬅️ Было: {old_text}\n"
            f"➡️ Стало: {new_text}"
        )
        try:
            # Отправляем БЕЗ parse_mode, чтобы спецсимволы не ломали бота
            bot.send_message(MY_TELEGRAM_ID, report)
            print(f"✅ Отчет об изменении {msg_id} отправлен!")
        except Exception as e:
            print(f"❌ Ошибка отправки изменения: {e}")
        
        # Обновляем в памяти
        if msg_id in messages_db:
            messages_db[msg_id]['text'] = new_text
        else:
            messages_db[msg_id] = {'type': 'text', 'text': new_text, 'file_id': None, 'time': time.time()}

# Ловим удаление сообщений
@bot.deleted_business_messages_handler(func=lambda deleted_messages: True)
def handle_deleted_business_messages(deleted_messages):
    msg_ids = getattr(deleted_messages, 'message_ids', [])
    print(f"🗑 [Бизнес] Событие удаления сообщений: {msg_ids}")
    
    for msg_id in msg_ids:
        if msg_id in messages_db:
            msg_data = messages_db[msg_id]
            content_type = msg_data['type']
            file_id = msg_data['file_id']
            caption = msg_data['text'] or ""
            
            # А. Текст
            if content_type == 'text':
                report = f"🗑 Сообщение УДАЛЕНО!\n📝 Текст: {msg_data['text']}"
                try:
                    bot.send_message(MY_TELEGRAM_ID, report)
                except Exception as e:
                    print(f"❌ Ошибка отправки удаления текста: {e}")
                
            # Б. Фото
            elif content_type == 'photo':
                report_caption = f"🗑 Удалено ФОТО!\n📝 Описание: {caption}"
                try:
                    bot.send_photo(MY_TELEGRAM_ID, file_id, caption=report_caption)
                except Exception as e:
                    bot.send_message(MY_TELEGRAM_ID, f"🗑 Удалено ФОТО, но не удалось отправить файл. Описание: {caption}")
                    
            # В. Видео
            elif content_type == 'video':
                report_caption = f"🗑 Удалено ВИДЕО!\n📝 Описание: {caption}"
                try:
                    bot.send_video(MY_TELEGRAM_ID, file_id, caption=report_caption)
                except Exception:
                    bot.send_message(MY_TELEGRAM_ID, report_caption)

            # Г. Голосовое
            elif content_type == 'voice':
                try:
                    bot.send_voice(MY_TELEGRAM_ID, file_id, caption="🗑 Удалено ГОЛОСОВОЕ!")
                except Exception:
                    bot.send_message(MY_TELEGRAM_ID, "🗑 Удалено ГОЛОСОВОЕ сообщение (файл недоступен)")

            messages_db.pop(msg_id)
        else:
            print(f"⚠️ Сообщение {msg_id} удалено, но его данных не было в нашей памяти")

# ==========================================
# 4. ВЕБ-СЕРВЕР И СТАРТ
# ==========================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Медиа-бот Архивариус активен"

def start_polling():
    while True:
        try:
            print("🧹 Очищаем вебхуки...")
            bot.remove_webhook()
            time.sleep(1)
            
            print("🚀 Запуск infinity_polling...")
            bot.infinity_polling(
                timeout=20, 
                long_polling_timeout=10,
                allowed_updates=["message", "business_message", "edited_business_message", "deleted_business_messages"]
            )
        except Exception as e:
            print(f"⚠️ Ошибка пуллинга: {e}. Перезапуск через 5 сек...")
            time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=start_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
