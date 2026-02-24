import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота
NAVIGATOR_TOKEN = os.getenv('NAVIGATOR_TOKEN')

# API MAX
MAX_API_BASE = "https://platform-api.max.ru"

# База данных
DATABASE_URL = os.getenv('DATABASE_URL')

# Ссылки на других ботов (замени на реальные ники после их создания)
DOWNLOADER_BOT_LINK = os.getenv('DOWNLOADER_BOT_LINK', 'https://max.ru/downloader')
PDF_BOT_LINK = os.getenv('PDF_BOT_LINK', 'https://max.ru/pdf')
AUDIO_BOT_LINK = os.getenv('AUDIO_BOT_LINK', 'https://max.ru/audio')
TTS_BOT_LINK = os.getenv('TTS_BOT_LINK', 'https://max.ru/tts')
IMAGE_BOT_LINK = os.getenv('IMAGE_BOT_LINK', 'https://max.ru/image')
