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
            "📍 Наш адрес: ул. Ленина, 45, г. Новосибирск.\n\n"
            "Ждём вас!"
        )
        return ConversationHandler.END

    await update.message.chat.send_action("typing")
    response = ask_gemini(user.id, text)
    await update.message.reply_text(response)
    return ConversationHandler.END