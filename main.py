import os
import asyncio
import threading
from aiogram import Bot, Dispatcher, F
from aiogram.types import BusinessMessagesDeleted, Message
from flask import Flask

TOKEN = os.environ.get("BOT_TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

# База данных в оперативной памяти (ID сообщения -> Текст)
messages_db = {}

print("Бот на aiogram успешно запущен и слушает бизнес-события...")

# 1. Ловим новые входящие сообщения
@dp.business_message(F.text)
async def handle_business_message(message: Message):
    msg_id = message.business_message_id or message.message_id
    messages_db[msg_id] = message.text
    if len(messages_db) > 5000:
        messages_db.pop(next(iter(messages_db)))

# 2. Ловим изменение сообщений
@dp.edited_business_message(F.text)
async def handle_edited_business_message(message: Message):
    msg_id = message.business_message_id or message.message_id
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
        await bot.send_message(chat_id=message.business_connection_id, text=report)
        messages_db[msg_id] = new_text

# 3. Ловим удаление сообщений
@dp.deleted_business_messages()
async def handle_deleted_business_messages(deleted_messages: BusinessMessagesDeleted):
    for msg_id in deleted_messages.message_ids:
        if msg_id in messages_db:
            deleted_text = messages_db[msg_id]
            report = (
                f"🗑 **Сообщение УДАЛЕНО!**\n"
                f"📝 Текст: {deleted_text}"
            )
            await bot.send_message(chat_id=deleted_messages.business_connection_id, text=report)
            messages_db.pop(msg_id)

# Веб-сервер пустышка для Render
app = Flask(__name__)
@app.route('/')
def home(): return "Бот активен"

def run_bot():
    asyncio.run(dp.start_polling(bot, allowed_updates=["business_message", "edited_business_message", "deleted_business_messages"]))

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
