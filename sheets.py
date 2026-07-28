import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os

SHEET_ID = os.getenv("SHEET_ID")

def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "credentials.json", scope
    )
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1

def save_client(name: str, phone: str, username: str = ""):
    try:
        sheet = get_sheet()
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        sheet.append_row([now, name, phone, username, "Новая заявка"])
        print(f"✅ Клиент сохранён: {name} | {phone}")
        return True
    except Exception as e:
        print(f"Sheets error: {e}")
        return False