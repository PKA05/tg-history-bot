import os
import time
import threading
from telebot import TeleBot
from flask import Flask

# Инициализация бота
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Переменная BOT_TOKEN не найдена в настройках Render!")
bot = TeleBot(TOKEN)

# Локальная база данных в памяти бота (ID сообщения -> Текст)
messages_db = {}
START_TIME = time.time()

print("🤖 Инициализация бота...")

# ==========================================
# 1. СТАНДАРТНЫЕ КОМАНДЫ (Для теста в ЛС бота)
# ==========================================

@bot.message_handler(commands=['start', 'status'])
def send_status(message):
    uptime = round(time.time() - START_TIME, 1)
    status_text = (
        "🟢 **Бот успешно работает!**\n\n"
        f"⏱ Время работы: {uptime} сек.\n"
        f"📦 Сообщений в памяти: {len(messages_db)}\n"
        f"👤 Твой ID: `{message.from_user.id}`\n"
        f"📡 Пинг до Telegram: работает!"
    )
    print(f"📟 Вызвана команда статуса пользователем {message.from_user.username}")
    bot.reply_to(message, status_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.chat.type == "private")
def echo_all(message):
    # Обычный эхо-ответ в ЛС, чтобы проверить, что бот вообще живой
    print(f"💬 Получено личное сообщение от @{message.from_user.username}: '{message.text}'")
    bot.reply_to(message, f"Получил твое сообщение: '{message.text}'. Я работаю стабильно!")

# ==========================================
# 2. ФУНКЦИИ TELEGRAM BUSINESS (Для работы)
# ==========================================

# А. Ловим новые бизнес-сообщения и сохраняем их в память
@bot.business_message_handler(func=lambda message: True)
def handle_business_message(message):
    if message.text:
        msg_id = getattr(message, 'business_message_id', message.message_id)
        messages_db[msg_id] = message.text
        print(f"📥 [Бизнес] Сохранено новое сообщение (ID: {msg_id}): '{message.text}'")
        
        # Защита от переполнения памяти (храним последние 5000 сообщений)
        if len(messages_db) > 5000:
            messages_db.pop(next(iter(messages_db)))

# Б. Ловим изменение сообщений
@bot.edited_business_message_handler(func=lambda message: True)
def handle_edited_business_message(message):
    msg_id = getattr(message, 'business_message_id', message.message_id)
    user = message.from_user.username or message.from_user.first_name
    
    old_text = messages_db.get(msg_id, "[Данных о сообщении нет в памяти бота]")
    new_text = message.text

    print(f"✏️ [Бизнес] Изменение сообщения @{user} (ID: {msg_id}). Стало: '{new_text}'")

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
            print(f"❌ Ошибка отправки отчета об изменении: {e}")
        messages_db[msg_id] = new_text

# В. Ловим удаление сообщений
@bot.deleted_business_messages_handler(func=lambda deleted_messages: True)
def handle_deleted_business_messages(deleted_messages):
    msg_ids = getattr(deleted_messages, 'message_ids', [])
    print(f"🗑 [Бизнес] Удалены сообщения с ID: {msg_ids}")
    
    for msg_id in msg_ids:
        if msg_id in messages_db:
            deleted_text = messages_db[msg_id]
            report = (
                f"🗑 **Сообщение УДАЛЕНО!**\n"
                f"📝 Текст: {deleted_text}"
            )
            try:
                bot.send_message(deleted_messages.business_connection_id, report)
                print(f"✅ Отчет об удалении отправлен: '{deleted_text}'")
            except Exception as e:
                print(f"❌ Ошибка отправки отчета об удалении: {e}")
            messages_db.pop(msg_id)

# ==========================================
# 3. ВЕБ-СЕРВЕР И СТАРТ
# ==========================================

app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>Бот работает стабильно!</h1>"

def start_polling():
    try:
        bot.remove_webhook()
        time.sleep(1)
        print("🚀 Бот успешно подключился к серверам Telegram и слушает бизнес-события...")
        bot.infinity_polling(allowed_updates=["message", "business_message", "edited_business_message", "deleted_business_messages"])
    except Exception as e:
        print(f"❌ Ошибка при запуске пуллинга: {e}")

if __name__ == "__main__":
    # Запуск бота в фоновом режиме
    threading.Thread(target=start_polling, daemon=True).start()
    # Запуск веб-сервера на порту Render
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
