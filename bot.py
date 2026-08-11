import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)
from gemini import ask_gemini, reset_chat
from sheets import save_client, get_booked_times

load_dotenv()
logging.basicConfig(level=logging.INFO)

# ============================================================
# CONFIG — всё, что меняется под нового клиента, ТОЛЬКО ЗДЕСЬ.
# Ниже этого блока логику трогать не нужно.
# ============================================================
CONFIG = {
    "salon_name": "Bellezza",
    "address": "ул. Гоголя, 38 (цокольный этаж), г. Новосибирск",
    "phone": "+7 (913) 007-58-59",
    "hours": (
        "Ежедневно: 9:00 - 22:00"
    ),
    # Услуги: название -> цена. Порядок сохраняется, кнопки строятся автоматически.
    "services": {
        "Глубокое бикини (шугаринг)": "1200 руб",
        "Классическое бикини (воск)": "900 руб",
        "Ноги полностью (шугаринг)": "1950 руб",
        "Стрижка женская": "1000 руб",
        "Окрашивание (корни)": "2000 руб",
        "Кавитация": "800 руб",
        "Наращивание ресниц": "уточнить у мастера",
    },
    # Даты и время для записи — тоже кнопками.
    "dates": ["Сегодня", "Завтра", "Послезавтра"],
    "times": ["10:00", "12:00", "14:00", "16:00", "18:00", "20:00"],
    # Откуда клиент узнал о салоне — кнопки на шаге записи.
    "sources": ["2ГИС", "Яндекс.Карты", "Проходил мимо", "Посоветовали", "Акция"],
    # ID владельца в Telegram — сюда падают заявки.
    "owner_id": 1782965914,
}
# ============================================================


# Состояния диалога записи
SERVICE, DATE, TIME, SOURCE, NAME, PHONE = range(6)

# Слова, по которым клиент в любой момент выходит из записи в меню
CANCEL_WORDS = ["передумал", "отмена", "отменить", "назад", "меню", "стоп", "❌ отмена"]

user_data_temp = {}


def resolve_date(date_text: str) -> str:
    """'Сегодня' -> '10.08.2026'. В таблице храним календарную дату,
    иначе вчерашнее 'Завтра' и сегодняшнее 'Сегодня' не различить."""
    offsets = {"Сегодня": 0, "Завтра": 1, "Послезавтра": 2}
    days = offsets.get(date_text, 0)
    return (datetime.now() + timedelta(days=days)).strftime("%d.%m.%Y")


def available_times(date_text: str):
    """Свободные слоты: убираем прошедшие (для сегодня) и уже занятые."""
    times = CONFIG["times"]

    # 1. Отсекаем прошедшее время, если запись на сегодня
    if date_text == "Сегодня":
        now = datetime.now()
        times = [
            t for t in times
            if tuple(map(int, t.split(":"))) > (now.hour, now.minute)
        ]

    # 2. Убираем занятые слоты по данным таблицы
    booked = get_booked_times(resolve_date(date_text))
    return [t for t in times if t not in booked]


def main_menu_markup():
    keyboard = [
        ["💅 Услуги и цены", "🕐 Время работы"],
        ["📍 Адрес", "✍️ Записаться"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def buttons_markup(items, per_row=2, add_cancel=True):
    """Строит клавиатуру из списка строк по per_row в ряд + кнопка отмены."""
    rows = [items[i:i + per_row] for i in range(0, len(items), per_row)]
    if add_cancel:
        rows.append(["❌ Отмена"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


def is_cancel(text: str) -> bool:
    return any(w in text.lower() for w in CANCEL_WORDS)


async def back_to_menu(update: Update, message: str):
    await update.message.reply_text(message, reply_markup=main_menu_markup())
    return ConversationHandler.END


# ------------------- Команды и справочные кнопки -------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reset_chat(user.id)
    user_data_temp.pop(user.id, None)
    await update.message.reply_text(
        f"Добрый день, {user.first_name}! 👋\n"
        f"Я администратор студии красоты *{CONFIG['salon_name']}*.\n"
        "Чем могу помочь?",
        parse_mode="Markdown",
        reply_markup=main_menu_markup(),
    )
    return ConversationHandler.END


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Справочные кнопки и свободный чат. Запись сюда НЕ входит (у неё свой entry_point)."""
    user = update.effective_user
    text = update.message.text.lower()

    if "услуги" in text or "цены" in text:
        lines = "\n".join(f"- {name}: {price}" for name, price in CONFIG["services"].items())
        await update.message.reply_text(
            f"💅 Наши услуги и цены (популярное):\n\n{lines}\n\n"
            "Это часть услуг — полный прайс уточните у администратора 😊"
        )
        return

    if "время" in text or "работы" in text or "часы" in text:
        await update.message.reply_text(f"🕐 Время работы нашей студии:\n\n{CONFIG['hours']}")
        return

    if "адрес" in text:
        await update.message.reply_text(f"📍 Наш адрес: {CONFIG['address']}.\n\nЖдём вас!")
        return

    # Всё остальное — свободный чат через AI
    await update.message.chat.send_action("typing")
    response = ask_gemini(user.id, update.message.text)
    await update.message.reply_text(response)


# ------------------- Диалог записи: 5 шагов -------------------

async def booking_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data_temp[user.id] = {}
    services = list(CONFIG["services"].keys())
    await update.message.reply_text(
        "Отлично! Давайте оформим запись 📝\n\n"
        "Выберите услугу:",
        reply_markup=buttons_markup(services, per_row=2),
    )
    return SERVICE


async def get_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if is_cancel(text):
        user_data_temp.pop(update.effective_user.id, None)
        return await back_to_menu(update, "Хорошо, запись отменена. Если что — я здесь! 😊")

    # Принимаем только реальную услугу из списка
    if text not in CONFIG["services"]:
        services = list(CONFIG["services"].keys())
        await update.message.reply_text(
            "Пожалуйста, выберите услугу кнопкой ниже 👇",
            reply_markup=buttons_markup(services, per_row=2),
        )
        return SERVICE

    user_data_temp[update.effective_user.id]["service"] = text
    await update.message.reply_text(
        f"Записываю на «{text}». Выберите дату:",
        reply_markup=buttons_markup(CONFIG["dates"], per_row=3),
    )
    return DATE


async def get_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if is_cancel(text):
        user_data_temp.pop(update.effective_user.id, None)
        return await back_to_menu(update, "Хорошо, запись отменена. Если что — я здесь! 😊")

    if text not in CONFIG["dates"]:
        await update.message.reply_text(
            "Пожалуйста, выберите дату кнопкой 👇",
            reply_markup=buttons_markup(CONFIG["dates"], per_row=3),
        )
        return DATE

    user_data_temp[update.effective_user.id]["date"] = text

    await update.message.chat.send_action("typing")   # читаем таблицу, это пара секунд
    times = available_times(text)

    if not times:
        await update.message.reply_text(
            f"На «{text}» свободных окон уже нет 😔\n"
            "Выберите, пожалуйста, другую дату:",
            reply_markup=buttons_markup(CONFIG["dates"], per_row=3),
        )
        return DATE

    await update.message.reply_text(
        "Выберите удобное время:",
        reply_markup=buttons_markup(times, per_row=3),
    )
    return TIME


async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if is_cancel(text):
        user_data_temp.pop(update.effective_user.id, None)
        return await back_to_menu(update, "Хорошо, запись отменена. Если что — я здесь! 😊")

    date_text = user_data_temp.get(update.effective_user.id, {}).get("date", "")
    times = available_times(date_text)

    if text not in times:
        # Либо нажал не ту кнопку, либо слот заняли, пока он думал
        if not times:
            await update.message.reply_text(
                "Похоже, все окна на эту дату только что разобрали 😔\n"
                "Выберите другую дату:",
                reply_markup=buttons_markup(CONFIG["dates"], per_row=3),
            )
            return DATE
        await update.message.reply_text(
            "Это время уже занято. Выберите, пожалуйста, из свободных 👇",
            reply_markup=buttons_markup(times, per_row=3),
        )
        return TIME

    user_data_temp[update.effective_user.id]["time"] = text
    await update.message.reply_text(
        "Подскажите, откуда вы о нас узнали?",
        reply_markup=buttons_markup(CONFIG["sources"], per_row=2),
    )
    return SOURCE


async def get_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if is_cancel(text):
        user_data_temp.pop(update.effective_user.id, None)
        return await back_to_menu(update, "Хорошо, запись отменена. Если что — я здесь! 😊")

    if text not in CONFIG["sources"]:
        await update.message.reply_text(
            "Выберите, пожалуйста, кнопкой 👇",
            reply_markup=buttons_markup(CONFIG["sources"], per_row=2),
        )
        return SOURCE

    user_data_temp[update.effective_user.id]["source"] = text
    await update.message.reply_text(
        "Спасибо! Как вас зовут?",
        reply_markup=buttons_markup([], add_cancel=True),  # только кнопка отмены
    )
    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if is_cancel(text):
        user_data_temp.pop(update.effective_user.id, None)
        return await back_to_menu(update, "Хорошо, запись отменена. Если что — я здесь! 😊")

    user_data_temp[update.effective_user.id]["name"] = text
    keyboard = [
        [KeyboardButton("📱 Отправить мой номер", request_contact=True)],
        ["❌ Отмена"],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        f"Приятно познакомиться, {text}! 😊\n\n"
        "Теперь укажите ваш номер телефона (или нажмите кнопку ниже):",
        reply_markup=reply_markup,
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        text = update.message.text
        if is_cancel(text):
            user_data_temp.pop(user.id, None)
            return await back_to_menu(update, "Хорошо, запись отменена. Если что — я здесь! 😊")
        phone = text

    data = user_data_temp.get(user.id, {})
    name = data.get("name", "Неизвестно")
    service = data.get("service", "—")
    date = data.get("date", "—")
    time = data.get("time", "—")
    source = data.get("source", "—")
    username = f"@{user.username}" if user.username else ""

    # В таблицу пишем календарную дату — по ней считаем занятость
    real_date = resolve_date(date)

    saved = save_client(name, phone, username, service, real_date, time, source)

    # Уведомление владельцу в Telegram
    await notify_owner(context, name, phone, service, date, real_date, time, username, source)

    if saved:
        await update.message.reply_text(
            f"✅ Готово! Вы записаны:\n\n"
            f"💅 {service}\n"
            f"📅 {date}, {time}\n"
            f"👤 {name}\n\n"
            "Мы свяжемся с вами для подтверждения. Если появятся вопросы — спрашивайте! 😊",
            reply_markup=main_menu_markup(),
        )
    else:
        await update.message.reply_text(
            f"Запись принята! Для связи с нами позвоните: {CONFIG['phone']}",
            reply_markup=main_menu_markup(),
        )

    user_data_temp.pop(user.id, None)
    reset_chat(user.id)
    return ConversationHandler.END


async def notify_owner(context, name, phone, service, date, real_date, time, username, source="—"):
    """Отправляет готовую заявку владельцу в Telegram."""
    try:
        text = (
            "🔔 *Новая запись!*\n\n"
            f"👤 Имя: {name}\n"
            f"📞 Телефон: {phone}\n"
            f"💅 Услуга: {service}\n"
            f"📅 Дата: {date} ({real_date})\n"
            f"🕐 Время: {time}\n"
            f"📊 Источник: {source}\n"
        )
        if username:
            text += f"💬 Telegram: {username}\n"
        await context.bot.send_message(
            chat_id=CONFIG["owner_id"], text=text, parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Не удалось отправить уведомление владельцу: {e}")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data_temp.pop(update.effective_user.id, None)
    return await back_to_menu(update, "Хорошо, если нужна помощь — спрашивайте!")


def main():
    app = Application.builder().token(os.getenv("BOT_TOKEN")).build()

    booking_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(r"(?i)запис"), booking_start),
        ],
        states={
            SERVICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_service)],
            DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            SOURCE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_source)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [
                MessageHandler(filters.CONTACT, get_phone),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
        per_user=True,
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(booking_conv)
    # Справочные кнопки и свободный чат — вне диалога записи
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Бот запущен...")
    app.run_polling(drop_pending_updates=True, timeout=30)


if __name__ == "__main__":
    main()
