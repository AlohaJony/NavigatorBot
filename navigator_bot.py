import logging
import time
import os
from config import NAVIGATOR_TOKEN, DOWNLOADER_BOT_LINK, PDF_BOT_LINK, AUDIO_BOT_LINK, TTS_BOT_LINK, IMAGE_BOT_LINK
from max_client import MaxBotClient
from user_manager import get_or_create_user, get_balance, add_tokens

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not NAVIGATOR_TOKEN:
    raise ValueError("No NAVIGATOR_TOKEN in .env")

bot = MaxBotClient(NAVIGATOR_TOKEN)
BOT_ID = None

def main_menu_keyboard():
    return {
        "type": "inline_keyboard",
        "payload": {
            "buttons": [
                [{"type": "link", "text": "🎬 Скачать видео", "url": DOWNLOADER_BOT_LINK}],
                [{"type": "link", "text": "📄 PDF → Word", "url": PDF_BOT_LINK}],
                [{"type": "link", "text": "🎵 Аудио из видео → текст", "url": AUDIO_BOT_LINK}],
                [{"type": "link", "text": "🗣 Озвучка текста", "url": TTS_BOT_LINK}],
                [{"type": "link", "text": "🎨 Генерация изображений", "url": IMAGE_BOT_LINK}],
                [{"type": "callback", "text": "💰 Мой баланс", "payload": "balance"}],
                [{"type": "callback", "text": "💳 Пополнить (тест)", "payload": "topup"}]
            ]
        }
    }

def handle_update(update):
    global BOT_ID
    update_type = update.get('update_type')
    logger.info(f"Update: {update_type}")

    if update_type == 'message_created':
        msg = update['message']
        if msg['sender'].get('is_bot') and msg['sender'].get('user_id') == BOT_ID:
            return
        chat_id = msg['recipient'].get('chat_id') or msg['recipient'].get('user_id')
        text = msg['body'].get('text', '').strip()
        user_info = msg['sender']
        user_id = user_info['user_id']
        username = user_info.get('username')
        first_name = user_info.get('first_name')

        get_or_create_user(user_id, username, first_name)

        if text == '/start':
            balance = get_balance(user_id)
            welcome = (
                f"👋 Добро пожаловать в семейство ботов MAX!\n\n"
                f"Ваш баланс: {balance} токенов.\n\n"
                f"Выберите нужного бота ниже:"
            )
            bot.send_message(chat_id, welcome, attachments=[main_menu_keyboard()])
        else:
            bot.send_message(chat_id, "Используйте кнопки меню или /start")

    elif update_type == 'message_callback':
        callback = update['callback']
        chat_id = callback['message']['recipient']['chat_id']
        user_id = callback['user']['user_id']
        payload = callback['payload']

        if payload == 'balance':
            balance = get_balance(user_id)
            bot.send_message(chat_id, f"💰 Ваш баланс: {balance} токенов.")
        elif payload == 'topup':
            add_tokens(user_id, 100, "Тестовое пополнение")
            bot.send_message(chat_id, "✅ Тестовое пополнение на 100 токенов выполнено!")
        else:
            bot.send_message(chat_id, "Неизвестная команда.")

def main():
    global BOT_ID
    logger.info("Starting Navigator Bot...")
    me = bot.get_me()
    BOT_ID = me['user_id']
    logger.info(f"Bot ID: {BOT_ID}, username: @{me.get('username')}")

    marker = None
    while True:
        try:
            updates_data = bot.get_updates(marker=marker, timeout=30)
            updates = updates_data.get('updates', [])
            new_marker = updates_data.get('marker')
            if new_marker is not None:
                marker = new_marker
            for upd in updates:
                handle_update(upd)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
