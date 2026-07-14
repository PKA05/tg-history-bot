import os
from telebot import TeleBot

TOKEN = os.environ.get("BOT_TOKEN")
bot = TeleBot(TOKEN)

# База данных в оперативной памяти (ID сообщения -> Текст)
messages_db = {}

print("Бот успешно запущен и слушает бизнес-события...")

# 1. Перехватываем входящие сообщения через Telegram Business
@bot.business_message_handler(func=lambda message: True)
def handle_business_message(message):
    if message.text:
        # В актуальной версии используется message.message_id или message.id
        msg_id = getattr(message, 'business_message_id', message.message_id)
        messages_db[msg_id] = message.text
        if len(messages_db) > 5000:
            first_key = next(iter(messages_db))
            messages_db.pop(first_key)

# 2. Перехватываем ИЗМЕНЕНИЕ сообщений
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
        bot.send_message(message.business_connection_id, report)
        messages_db[msg_id] = new_text

# 3. Перехватываем УДАЛЕНИЕ сообщений
@bot.deleted_business_messages_handler(func=lambda deleted_messages: True)
def handle_deleted_business_messages(deleted_messages):
    # В объекте BusinessMessagesDeleted список ID лежит прямо в свойстве message_ids
    msg_ids = getattr(deleted_messages, 'message_ids', [])
    
    for msg_id in msg_ids:
        if msg_id in messages_db:
            deleted_text = messages_db[msg_id]
            report = (
                f"🗑 **Сообщение УДАЛЕНО!**\n"
                f"📝 Текст: {deleted_text}"
            )
            bot.send_message(deleted_messages.business_connection_id, report)
            messages_db.pop(msg_id)

# Запуск веб-сервера пустышки для Render
from flask import Flask
app = Flask(__name__)
@app.route('/')
def home(): return "Бот активен"

if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: bot.infinity_polling(allowed_updates=["business_message", "edited_business_message", "deleted_business_messages"])).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
