import os
import time
import threading
from telebot import TeleBot
from flask import Flask

TOKEN = os.environ.get("BOT_TOKEN")
bot = TeleBot(TOKEN)

# Локальная память для сообщений
messages_db = {}

print("Бот запускается...")

@bot.business_message_handler(func=lambda message: True)
def handle_business_message(message):
    if message.text:
        msg_id = getattr(message, 'business_message_id', message.message_id)
        messages_db[msg_id] = message.text
        if len(messages_db) > 5000:
            messages_db.pop(next(iter(messages_db)))

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

# Flask-сервер для прохождения проверки Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот активен"

def start_polling():
    bot.remove_webhook()
    time.sleep(1)
    print("Бот успешно запущен и слушает бизнес-события...")
    bot.infinity_polling(allowed_updates=["business_message", "edited_business_message", "deleted_business_messages"])

if __name__ == "__main__":
    threading.Thread(target=start_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
