import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
import json

SHEET_ID = os.getenv("SHEET_ID")


def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds_env = os.getenv("GOOGLE_CREDENTIALS")
    if creds_env:
        creds_dict = json.loads(creds_env)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "credentials.json", scope
        )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1


def save_client(name: str, phone: str, username: str = "",
                service: str = "", date: str = "", time: str = "",
                source: str = ""):
    """Пишет заявку отдельными колонками. date — календарная, вида 10.08.2026."""
    try:
        sheet = get_sheet()
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        sheet.append_row([
            now,        # A — когда пришла заявка
            name,       # B — имя
            phone,      # C — телефон
            username,   # D — telegram
            service,    # E — услуга
            date,       # F — дата записи
            time,       # G — время
            source,     # H — источник
            "Новая заявка",  # I — статус
        ])
        print(f"Клиент сохранён: {name} | {phone} | {source}")
        return True
    except Exception as e:
        print(f"Sheets error: {e}")
        return False


def get_booked_times(date: str):
    """Возвращает список занятых слотов на календарную дату (10.08.2026).

    Отменённые заявки не считаются занятыми — салон может проставить
    в колонке «Статус» слово «Отменена», и окно снова освободится.
    """
    try:
        sheet = get_sheet()
        rows = sheet.get_all_values()

        booked = []
        for row in rows[1:]:                 # пропускаем шапку
            if len(row) < 7:
                continue
            row_date = row[5].strip()        # F — дата записи
            row_time = row[6].strip()        # G — время
            status = row[8].strip().lower() if len(row) > 8 else ""

            if "отмен" in status:
                continue
            if row_date == date and row_time:
                booked.append(row_time)

        return booked
    except Exception as e:
        print(f"Sheets error (booked): {e}")
        return []      # при сбое лучше показать все слоты, чем сорвать запись
