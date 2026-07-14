import os
from telebot import TeleBot

# Получаем токен из настроек сервера (для безопасности)
TOKEN = os.environ.get("BOT_TOKEN")
bot = TeleBot(TOKEN)

# База данных в оперативной памяти для хранения исходных текстов сообщений
# Ключ: business_message_id, Значение: текст сообщения
messages_db = {}

print("Бот успешно запущен и слушает бизнес-события...")

# 1. Перехватываем входящие сообщения через Telegram Business
@bot.business_message_handler(func=lambda message: True)
def handle_business_message(message):
    if message.text:
        # Сохраняем текст сообщения по его ID
        messages_db[message.business_message_id] = message.text
        # Ограничиваем размер памяти (храним последние 5000 сообщений)
        if len(messages_db) > 5000:
            first_key = next(iter(messages_db))
            messages_db.pop(first_key)

# 2. Перехватываем ИЗМЕНЕНИЕ сообщений
@bot.edited_business_message_handler(func=lambda message: True)
def handle_edited_business_message(message):
    msg_id = message.business_message_id
    chat_id = message.chat.id
    user = message.from_user.username or message.from_user.first_name
    
    # Проверяем, есть ли у нас старый текст этого сообщения
    old_text = messages_db.get(msg_id, "[Нет данных в памяти бота]")
    new_text = message.text

    if old_text != new_text:
        report = (
            f"✏️ **Сообщение изменено!**\n"
            f"👤 От кого: @{user}\n"
            f"⬅️ Было: {old_text}\n"
            f"➡️ Стало: {new_text}"
        )
        # Бот отправляет уведомление лично ТЕБЕ (твоему аккаунту)
        bot.send_message(message.business_connection_id, report)
        # Обновляем текст в памяти
        messages_db[msg_id] = new_text

# 3. Перехватываем УДАЛЕНИЕ сообщений
@bot.deleted_business_messages_handler(func=lambda messages: True)
def handle_deleted_business_messages(messages):
    chat_id = messages.chat.id
    
    for msg in messages.messages:
        msg_id = msg.message_id
        # Ищем удаленный текст в нашей базе данных
        if msg_id in messages_db:
            deleted_text = messages_db[msg_id]
            report = (
                f"🗑 **Сообщение УДАЛЕНО!**\n"
                f"📝 Текст: {deleted_text}"
            )
            bot.send_message(messages.business_connection_id, report)
            # Удаляем из памяти, чтобы не занимать место
            messages_db.pop(msg_id)

# Запуск веб-сервера «пустышки», чтобы Render не закрывал приложение
from flask import Flask
app = Flask(__name__)
@app.route('/')
def home(): return "Бот активен"

if __name__ == "__main__":
    # Запуск бота параллельно
    import threading
    threading.Thread(target=lambda: bot.infinity_polling(allowed_updates=["business_message", "edited_business_message", "deleted_business_messages"])).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
