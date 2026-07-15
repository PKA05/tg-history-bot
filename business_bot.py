import os
import time
import threading
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
# Храним структуру: {msg_id: {'type': 'text/photo...', 'text': '...', 'file_id': '...'}}
messages_db = {}

# ==========================================
# 1. ОБЫЧНЫЕ КОМАНДЫ (Для теста в ЛС)
# ==========================================

@bot.message_handler(commands=['start', 'status'])
def send_welcome(message):
    status_text = (
        "🟢 Новый бизнес-бот (МЕДИА-ВЕРСИЯ) успешно работает!\n\n"
        f"📦 Сообщений в памяти: {len(messages_db)}\n"
        f"👤 Твой ID: {message.from_user.id}\n"
        "📡 Запущен из файла: business_bot.py"
    )
    bot.reply_to(message, status_text)

@bot.message_handler(func=lambda message: message.chat.type == "private")
def echo_all(message):
    bot.reply_to(message, f"Получил сообщение в ЛС: '{message.text}'")

# ==========================================
# 2. УЛУЧШЕННОЕ ХРАНЕНИЕ МЕДИА (Новые типы!)
# ==========================================

def save_message_to_db(msg_id, content_type, text=None, file_id=None):
    """Универсальная функция сохранения данных в память"""
    if text or file_id:
        messages_db[msg_id] = {
            'type': content_type,
            'text': text,
            'file_id': file_id,
            'time': time.time() # Время сохранения для очистки
        }
        print(f"📥 [Бизнес] Успешно сохранено ({content_type}) {msg_id}: '{text or '[Медиа]'}'")
    
# Ловим все типы контента: текст, фото, видео, голосовые, документы
@bot.business_message_handler(content_types=['text', 'photo', 'video', 'voice', 'document'])
def handle_all_business_messages(message):
    msg_id = getattr(message, 'business_message_id', None) or message.message_id
    
    # 1. Если это текст
    if message.content_type == 'text':
        save_message_to_db(msg_id, 'text', text=message.text)
        
    # 2. Если это фото
    elif message.content_type == 'photo':
        # Telegram присылает несколько размеров, берем самый большой (последний в списке)
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
# 3. УЛУЧШЕННОЕ УВЕДОМЛЕНИЕ ОБ УДАЛЕНИИ
# ==========================================

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
            
            # А. Если удалили ТЕКСТ
            if content_type == 'text':
                report = f"🗑 Сообщение УДАЛЕНО!\n📝 Текст: {msg_data['text']}"
                bot.send_message(MY_TELEGRAM_ID, report)
                
            # Б. Если удалили ФОТО
            elif content_type == 'photo':
                # Сначала присылаем фото
                report_caption = f"🗑 Удалено ФОТО!\n📝 Описание: {caption}"
                try:
                    bot.send_photo(MY_TELEGRAM_ID, file_id, caption=report_caption)
                    print(f"✅ Удаленное фото {msg_id} переслано в ЛС!")
                except Exception as e:
                    bot.send_message(MY_TELEGRAM_ID, f"🗑 Удалено ФОТО, но не удалось переслать файл: {e}\n📝 Описание: {caption}")
                    
            # В. Если удалили ВИДЕО
            elif content_type == 'video':
                report_caption = f"🗑 Удалено ВИДЕО!\n📝 Описание: {caption}"
                try:
                    bot.send_video(MY_TELEGRAM_ID, file_id, caption=report_caption)
                except Exception:
                    bot.send_message(MY_TELEGRAM_ID, report_caption)

            # Г. Если удалили ГОЛОСОВОЕ
            elif content_type == 'voice':
                try:
                    bot.send_voice(MY_TELEGRAM_ID, file_id, caption="🗑 Удалено ГОЛОСОВОЕ!")
                except Exception:
                    bot.send_message(MY_TELEGRAM_ID, "🗑 Удалено ГОЛОСОВОЕ сообщение (файл недоступен)")

            # Удаляем из памяти, чтобы не засорять
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
