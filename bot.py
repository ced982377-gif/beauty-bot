import os
import logging
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from gemini import ask_gemini, reset_chat
from sheets import save_client

load_dotenv()
logging.basicConfig(level=logging.INFO)

NAME, PHONE = range(2)
user_data_temp = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reset_chat(user.id)
    keyboard = [
        ["💅 Услуги и цены", "🕐 Время работы"],
        ["📍 Адрес", "✍️ Записаться"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"Добрый день, {user.first_name}! 👋\n"
        "Я администратор салона красоты *Glamour*.\n"
        "Чем могу помочь?",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    booking_keywords = ["записаться", "запись", "хочу записаться", "✍️ записаться"]
    if any(kw in text.lower() for kw in booking_keywords):
        await update.message.reply_text("Отлично! Давайте оформим запись 📝\n\nКак вас зовут?")
        return NAME

    if "услуги" in text.lower() or "цены" in text.lower():
        await update.message.reply_text(
            "💅 Наши услуги и цены:\n\n"
            "- Стрижка женская: от 1500 руб\n"
            "- Стрижка мужская: от 800 руб\n"
            "- Окрашивание волос: от 3000 руб\n"
            "- Маникюр: от 1200 руб\n"
            "- Педикюр: от 1500 руб\n"
            "- Наращивание ресниц: от 2000 руб\n"
            "- Чистка лица: от 2500 руб"
        )
        return ConversationHandler.END

    if "время" in text.lower() or "работы" in text.lower() or "часы" in text.lower():
        await update.message.reply_text(
            "🕐 Время работы нашего салона:\n\n"
            "Пн-Пт: 9:00 - 21:00\n"
            "Сб-Вс: 10:00 - 20:00"
        )
        return ConversationHandler.END

    if "адрес" in text.lower():
        await update.message.reply_text(
            "📍 Наш адрес: ул. Ленина, 45, г. Новосибирск.\n\nЖдём вас!"
        )
        return ConversationHandler.END

    await update.message.chat.send_action("typing")
    response = ask_gemini(user.id, text)
    await update.message.reply_text(response)
    return ConversationHandler.END

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data_temp[update.effective_user.id] = {"name": update.message.text}
    keyboard = [[KeyboardButton("📱 Отправить мой номер", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        f"Приятно познакомиться, {update.message.text}! 😊\n\nТеперь укажите ваш номер телефона:",
        reply_markup=reply_markup
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text
    name = user_data_temp.get(user.id, {}).get("name", "Неизвестно")
    username = f"@{user.username}" if user.username else ""
    saved = save_client(name, phone, username)
    keyboard = [
        ["💅 Услуги и цены", "🕐 Время работы"],
        ["📍 Адрес", "✍️ Записаться"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    if saved:
        await update.message.reply_text(
            "✅ Отлично! Мы свяжемся с вами в ближайшее время для подтверждения записи.\n\n"
            "Если появятся вопросы — спрашивайте! 😊",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "Спасибо! Для связи с нами позвоните: +7 (383) 123-45-67",
            reply_markup=reply_markup
        )
    user_data_temp.pop(user.id, None)
    reset_chat(user.id)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["💅 Услуги и цены", "🕐 Время работы"],
        ["📍 Адрес", "✍️ Записаться"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Хорошо, если нужна помощь — спрашивайте!", reply_markup=reply_markup)
    return ConversationHandler.END

def main():
    app = Application.builder().token(os.getenv("BOT_TOKEN")).build()
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [
                MessageHandler(filters.CONTACT, get_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        allow_reentry=True
    )
    app.add_handler(conv_handler)
    print("🤖 Бот запущен...")
    app.run_polling(drop_pending_updates=True, timeout=30)

if __name__ == "__main__":
    main()