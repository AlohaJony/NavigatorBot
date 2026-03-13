import os
from dotenv import load_dotenv

load_dotenv()

NAVIGATOR_TOKEN = os.getenv('NAVIGATOR_TOKEN')
MAX_API_BASE = "https://platform-api.max.ru"
DATABASE_URL = os.getenv('DATABASE_URL')
SUPPORT_LINK = os.getenv('SUPPORT_LINK')
# Ссылки на других ботов
DOWNLOADER_BOT_LINK = os.getenv('DOWNLOADER_BOT_LINK')
PDF_BOT_LINK = os.getenv('PDF_BOT_LINK')
AUDIO_BOT_LINK = os.getenv('AUDIO_BOT_LINK')
TTS_BOT_LINK = os.getenv('TTS_BOT_LINK')
IMAGE_BOT_LINK = os.getenv('IMAGE_BOT_LINK')

# ЮKassa
YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID')
YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY')
YOOKASSA_RETURN_URL = os.getenv('YOOKASSA_RETURN_URL')
WEBHOOK_BASE = os.getenv('WEBHOOK_BASE')
