import os
from dotenv import load_dotenv

load_dotenv()

CONVERTER_BOT_TOKEN = os.getenv('CONVERTER_BOT_TOKEN')
DATABASE_URL = os.getenv('DATABASE_URL')
NAVIGATOR_BOT_LINK = os.getenv('NAVIGATOR_BOT_LINK', 'https://max.ru/navigator')
