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
# 2. УЛУЧШЕННОЕ ХРАНЕНИЕ МЕДИА
# ==========================================

def save_message_to_db(msg_id, content_type, text=None, file_id=None):
    """Универсальная функция сохранения данных в память"""
    if text or file_id:
        messages_db[msg_id] = {
            'type': content_type,
            'text': text,
            'file_id': file_id,
            'time': time.time()
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
        file_id = message.photo[-1].file_id
        save_message_to_db(msg_id, 'photo', text=message.caption, file_id=file_id)
        
    # 3. Если это video
    elif message.content_type == 'video':
        save_message_to_db(msg_id, 'video', text=message.caption, file_id=message.video.file_id)
        
    # 4. Если это voice
    elif message.content_type == 'voice':
        save_message_to_db(msg_id, 'voice', file_id=message.voice.file_id)
        
    # 5. Если это document
    elif message.content_type == 'document':
        save_message_to_db(msg_id, 'document', text=message.caption, file_id=message.document.file_id)

# ==========================================
# 3. УЛУЧШЕННОЕ УВЕДОМЛЕНИЕ ОБ ИЗМЕНЕНИИ И УДАЛЕНИИ
# ==========================================

# Ловим изменение бизнес-сообщений (любых типов)
@bot.edited_business_message_handler(content_types=['text', 'photo', 'video', 'document'])
def handle_edited_business_message(message):
    msg_id = getattr(message, 'business_message_id', None) or message.message_id
    user = message.from_user.username or message.from_user.first_name
    
    # Пытаемся достать старый текст из памяти
    old_data = messages_db.get(msg_id)
    old_text = old_data['text'] if old_data and old_data.get('text') else "[Нет текста в памяти]"
    
    # Достаем новый измененный текст (или описание медиафайла)
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
            print(f"✅ Отчет об изменении {msg_id} отправлен в ЛС!")
        except Exception as e:
            print(f"❌ Ошибка отправки изменения в ЛС: {e}")
        
        # Обновляем текст в нашей памяти
        if msg_id in messages_db:
            messages_db[msg_id]['text'] = new_text
        else:
            messages_db[msg_id] = {'type': 'text', 'text': new_text, 'file_id': None, 'time': time.time()}

# Ловим удаление
@bot.deleted_business_messages_handler(func=lambda deleted_messages: True)
def handle_deleted_business_messages(deleted_messages):
    msg_ids = getattr(deleted_messages, 'message
