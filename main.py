import os
import time
from telebot import TeleBot
from flask import Flask
import threading

TOKEN = os.environ.get("BOT_TOKEN")
bot = TeleBot(TOKEN)

# Локальная база данных в памяти (ID сообщения -> Текст)
messages_db = {}

print("Бот запускается...")

# 1. Ловим новые сообщения через Telegram Business
@bot.business_message_handler(func=lambda message: True)
def handle_business_message(message):
    if message.text:
        # Пытаемся взять уникальный ID бизнес-сообщения
        msg_id = getattr(message, 'business_message_id', message.message_id)
        messages_db[msg_id] = message.text
        # Чистим память, если накопилось больше 5000 сообщений
        if len(messages_db) > 5000:
            messages_db.pop(next(iter(messages_db)))

# 2. Ловим изменение сообщений
@bot.edited_business_message_handler(func=lambda message: True)
def handle_edited_business_message(message):
    msg_id = getattr(message, 'business_message_id', message.message_id)
    user = message.from_user.username or message.from_user.first_name
    
    old_text = messages_db.get(msg_id, "[Нет данных в памяти бота]")
    new_text = message.text

    if old_text != new_text:
        report = (
            f"✏️ **Сообщение изменено!**\n"
            f"👤 От кого: @{user}\n"
            f"⬅️ Было: {old_text}\n"
            f"➡️ Стало: {new_text}"
        )
        try:
            bot.send_message(message.business_connection_id, report)
        except Exception as e:
            print(f"Ошибка отправки: {e}")
        messages_db[msg_id] = new_text

# 3. Ловим удаление сообщений
@bot.deleted_business_messages_handler(func=lambda deleted_messages: True)
def handle_deleted_business_messages(deleted_messages):
    msg_ids = getattr(deleted_messages, 'message_ids', [])
    for msg_id in msg_ids:
        if msg_id in messages_db:
            deleted_text = messages_db[msg_id]
            report = (
                f"🗑 **Сообщение УДАЛЕНО!**\n"
                f"📝 Текст: {deleted_text}"
            )
            try:
                bot.send_message(deleted_messages.business_connection_id, report)
            except Exception as e:
                print(f"Ошибка отправки: {e}")
            messages_db.pop(msg_id)

# Веб-сервер пустышка для Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот активен"

def start_polling():
    # Удаляем вебхуки перед запуском, чтобы не было конфликтов 409
    bot.remove_webhook()
    time.sleep(1)
    print("Бот успешно запущен и слушает бизнес-события...")
    bot.infinity_polling(allowed_updates=["business_message", "edited_business_message", "deleted_business_messages"])

if __name__ == "__main__":
    # Запускаем бота в отдельном потоке
    threading.Thread(target=start_polling, daemon=True).start()
    # Запускаем веб-сервер
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
