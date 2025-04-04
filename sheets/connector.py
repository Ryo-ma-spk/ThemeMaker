# bot/sheets/connector.py
import os
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
KEY_PATH = "/bot-key.json"
# KEY_PATH = os.getenv("BOT_KEY_PATH", "/bot-key.json")  # ← 環境変数がなければ /bot-key.json を使う

creds = Credentials.from_service_account_file(KEY_PATH, scopes=SCOPES)
gc = gspread.authorize(creds)

# シートを開く
spreadsheet = gc.open("ThemeMaker")
reminder_sheet = spreadsheet.worksheet("Reminder")
theme_sheet = spreadsheet.worksheet("Theme")