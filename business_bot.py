import os
import time
import threading
import telebot
from telebot import TeleBot
from flask import Flask

# Включаем логирование в консоль Render
import logging
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

TOKEN = os.environ.get("BOT_TOKEN")
bot = TeleBot(TOKEN)

# База данных сообщений в памяти
messages_db = {}

# ==========================================
# 1. ОБЫЧНЫЕ КОМАНДЫ (Для теста в ЛС)
# ==========================================

@bot.message_handler(commands=['start', 'status'])
def send_welcome(message):
    status_text = (
        "🟢 Новый бизнес-бот успешно работает!\n\n"
        f"📦 Сообщений в памяти: {len(messages_db)}\n"
        f"👤 Твой ID: {message.from_user.id}\n"
        "📡 Запущен из файла: business_bot.py"
    )
    # Убрали parse_mode, чтобы не было ошибок разметки
    bot.reply_to(message, status_text)

@bot.message_handler(func=lambda message: message.chat.type == "private")
def echo_all(message):
    bot.reply_to(message, f"Получил сообщение в ЛС: '{message.text}'")

# ==========================================
# 2. ФУНКЦИИ TELEGRAM BUSINESS
# ==========================================

# Сохраняем новые сообщения
@bot.business_message_handler(func=lambda message: True)
def handle_business_message(message):
    if message.text:
        msg_id = getattr(message, 'business_message_id', message.message_id)
        messages_db[msg_id] = message.text
        print(f"📥 [Бизнес] Сохранено: {message.text}")

# Отслеживаем изменения
@bot.edited_business_message_handler(func=lambda message: True)
def handle_edited_business_message(message):
    msg_id = getattr(message, 'business_message_id', message.message_id)
    user = message.from_user.username or message.from_user.first_name
    
    old_text = messages_db.get(msg_id, "[Нет данных в памяти]")
    new_text = message.text

    if old_text != new_text:
        report = (
            "✏️ Сообщение изменено!\n"
            f"👤 От кого: @{user}\n"
            f"⬅️ Было: {old_text}\n"
            f"➡️ Стало: {new_text}"
        )
        try:
            bot.send_message(message.business_connection_id, report)
        except Exception as e:
            print(f"❌ Ошибка отправки изменения: {e}")
        messages_db[msg_id] = new_text

# Отслеживаем удаления
@bot.deleted_business_messages_handler(func=lambda deleted_messages: True)
def handle_deleted_business_messages(deleted_messages):
    msg_ids = getattr(deleted_messages, 'message_ids', [])
    
    for msg_id in msg_ids:
        if msg_id in messages_db:
            deleted_text = messages_db[msg_id]
            report = (
                "🗑 Сообщение УДАЛЕНО!\n"
                f"📝 Текст: {deleted_text}"
            )
            try:
                bot.send_message(deleted_messages.business_connection_id, report)
                print(f"✅ Отчет об удалении отправлен!")
            except Exception as e:
                print(f"❌ Ошибка отправки удаления: {e}")
            messages_db.pop(msg_id)

# ==========================================
# 3. ВЕБ-СЕРВЕР И СТАРТ
# ==========================================

app = Flask(__name__)

@app.route('/')
def home():
    return "Бизнес-бот активен"

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
