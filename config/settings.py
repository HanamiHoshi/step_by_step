# config/settings.py
from dotenv import load_dotenv
import os

load_dotenv()  # загружает переменные из .env в os.environ

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Проверка, что токен загрузился
if not BOT_TOKEN:
    raise ValueError("Не найден BOT_TOKEN в .env файле!")