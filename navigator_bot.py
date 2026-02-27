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
    """Клавиатура главного меню."""
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
    logger.info(f"Update type: {update_type}")

    if update_type == 'message_created':
        msg = update.get('message')
        if not msg:
            logger.error("No 'message' field in update")
            return

        sender = msg.get('sender', {})
        # Игнорируем свои сообщения
        if sender.get('is_bot') and sender.get('user_id') == BOT_ID:
            return

        # В личных сообщениях получатель — user_id
        user_id = sender.get('user_id')
        if not user_id:
            logger.error("No user_id in sender")
            return

        username = sender.get('username')
        first_name = sender.get('first_name')

        # Регистрируем пользователя в БД
        get_or_create_user(user_id, username, first_name)

        # Текст сообщения
        text = msg.get('body', {}).get('text', '').strip()
        if text == '/start':
            balance = get_balance(user_id)
            welcome = (
                f"👋 Добро пожаловать в семейство ботов MAX!\n\n"
                f"Ваш баланс: {balance} токенов.\n\n"
                f"Выберите нужного бота ниже:"
            )
            bot.send_message(user_id=user_id, text=welcome, attachments=[main_menu_keyboard()])
        else:
            bot.send_message(user_id=user_id, text="Используйте кнопки меню или /start")

    elif update_type == 'message_callback':
        callback = update.get('callback')
        if not callback:
            logger.error("No 'callback' field in update")
            return

        # Получаем user_id из callback
        user_info = callback.get('user')
        if not user_info:
            logger.error("No user in callback")
            return
        user_id = user_info.get('user_id')
        if not user_id:
            logger.error("No user_id in callback")
            return

        payload = callback.get('payload')
        logger.info(f"Callback payload: {payload}")

        if payload == 'balance':
            balance = get_balance(user_id)
            bot.send_message(user_id=user_id, text=f"💰 Ваш баланс: {balance} токенов.")
        elif payload == 'topup':
            # Тестовое пополнение на 100 токенов
            add_tokens(user_id, 100, "Тестовое пополнение")
            bot.send_message(user_id=user_id, text="✅ Тестовое пополнение на 100 токенов выполнено!")
        else:
            bot.send_message(user_id=user_id, text="Неизвестная команда.")
    else:
        logger.warning(f"Unknown update type: {update_type}")

def main():
    global BOT_ID
    logger.info("Starting Navigator Bot...")
    try:
        me = bot.get_me()
        BOT_ID = me['user_id']
        logger.info(f"Bot ID: {BOT_ID}, username: @{me.get('username')}")
    except Exception as e:
        logger.error(f"Failed to get bot info: {e}")
        return

    marker = None
    while True:
        try:
            updates_data = bot.get_updates(marker=marker, timeout=30)
            updates = updates_data.get('updates', [])
            new_marker = updates_data.get('marker')
            if new_marker is not None:
                marker = new_marker
            for upd in updates:
                try:
                    handle_update(upd)
                except Exception as e:
                    logger.error(f"Error handling update: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
