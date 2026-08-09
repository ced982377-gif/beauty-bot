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
    """Пишет заявку отдельными колонками."""
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
