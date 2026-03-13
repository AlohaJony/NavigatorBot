import logging
import time
import threading
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from config import NAVIGATOR_TOKEN, DOWNLOADER_BOT_LINK, PDF_BOT_LINK, AUDIO_BOT_LINK, TTS_BOT_LINK, IMAGE_BOT_LINK, SUPPORT_LINK, YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, YOOKASSA_RETURN_URL, WEBHOOK_BASE
from max_client import MaxBotClient
from user_manager import get_or_create_user, get_balance, add_tokens
from payments import YooKassaClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUBSCRIPTIONS = {
    "sub_base": {"tokens": 30, "price": 99, "name": "Колхозник"},
    "sub_start": {"tokens": 100, "price": 199, "name": "Ударник"},
    "sub_pro": {"tokens": 350, "price": 449, "name": "Стахановец"},
    "sub_premium": {"tokens": 700, "price": 849, "name": "Партийный"},
    "sub_ultra": {"tokens": 1000, "price": 1099, "name": "Генсек"},
}

if not NAVIGATOR_TOKEN:
    raise ValueError("No NAVIGATOR_TOKEN in .env")

bot = MaxBotClient(NAVIGATOR_TOKEN)
BOT_ID = None

# Инициализация ЮKassa
yookassa = YooKassaClient(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, YOOKASSA_RETURN_URL)

# --- Веб-сервер для уведомлений ЮKassa ---
class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        try:
            data = json.loads(post_data)
            if yookassa.handle_notification(data):
                self.send_response(200)
                self.end_headers()
            else:
                self.send_response(400)
                self.end_headers()
        except Exception as e:
            logger.error(f"Webhook error: {e}")
            self.send_response(500)
            self.end_headers()

def run_webhook_server():
    server = HTTPServer(('0.0.0.0', 5000), WebhookHandler)
    logger.info("Webhook server started on port 5000")
    server.serve_forever()

# Запускаем веб-сервер в фоновом потоке
webhook_thread = threading.Thread(target=run_webhook_server, daemon=True)
webhook_thread.start()

def main_menu_keyboard():
    return {
        "type": "inline_keyboard",
        "payload": {
            "buttons": [
                [{"type": "link", "text": "🎬 Скачать видео", "url": DOWNLOADER_BOT_LINK}],
                [{"type": "link", "text": "📄 Конвертер (⚡)", "url": PDF_BOT_LINK}],
                #[{"type": "link", "text": "🎵 Аудио из видео (в разработке)", "url": AUDIO_BOT_LINK}],
                #[{"type": "link", "text": "🗣 Озвучка (в разработке)", "url": TTS_BOT_LINK}],
                #[{"type": "link", "text": "🎨 Генерация (в разработке)", "url": IMAGE_BOT_LINK}],
                [
                    {"type": "callback", "text": "💰 Мой баланс", "payload": "balance"},
                    {"type": "callback", "text": "💎 Подписки", "payload": "subscriptions"}
                ],
                #[
                #    {"type": "link", "text": "🆘 Техподдержка", "url": SUPPORT_LINK}
                #]
            ]
        }
    }

def subscriptions_keyboard():
    return {
        "type": "inline_keyboard",
        "payload": {
            "buttons": [
                [{"type": "callback", "text": "🧑‍🌾 Колхозник (30⚡) 99₽/мес", "payload": "sub_base"}],
                [{"type": "callback", "text": "⚒️ Ударник (100⚡) 199₽/мес", "payload": "sub_start"}],
                [{"type": "callback", "text": "🏭 Стахановец (350⚡) 449₽/мес", "payload": "sub_pro"}],
                [{"type": "callback", "text": "🎖️ Партийный (700⚡) 849₽/мес", "payload": "sub_premium"}],
                [{"type": "callback", "text": "👑 Генсек (1000⚡) 1099₽/мес", "payload": "sub_ultra"}],
                [{"type": "callback", "text": "🔙 Назад", "payload": "back_to_main"}]
            ]
        }
    }
"""
def topup_keyboard():
    return {
        "type": "inline_keyboard",
        "payload": {
            "buttons": [
                [
                    {"type": "callback", "text": "🧑‍🌾 Колхозник (30⚡) 99₽", "payload": "topup_30"},
                    {"type": "callback", "text": "⚒️ Ударник (100⚡) 199₽", "payload": "topup_100"}
                ],
                [
                    {"type": "callback", "text": "🏭 Стахановец (350⚡) 449₽", "payload": "topup_350"},
                    {"type": "callback", "text": "🎖️ Партийный (700⚡) 849₽", "payload": "topup_700"}
                ],
                [
                    {"type": "callback", "text": "👑 Генсек (1000⚡) 1099₽", "payload": "topup_1000"},
                    {"type": "callback", "text": "🔙 Назад", "payload": "back_to_main"}
                ]
            ]
        }
    }
"""
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
        if sender.get('is_bot') and sender.get('user_id') == BOT_ID:
            return

        user_id = sender.get('user_id')
        if not user_id:
            logger.error("No user_id in sender")
            return

        username = sender.get('username')
        first_name = sender.get('first_name')

        get_or_create_user(user_id, username, first_name)

        text = msg.get('body', {}).get('text', '').strip()
        if text == '/start':
            balance = get_balance(user_id)
            welcome = (
                f"👋 Добро пожаловать в семейство ботов СОЮЗ!\n\n"
                f"Ваш баланс: {balance} токенов.\n\n"
                f"Выберите нужного бота ниже:"
            )
            # Прикрепляем картинку
            #image_attachment = {
            #    "type": "image",
            #    "payload": {
            #        "url": "https://i.ibb.co/your-image.jpg"
            #    }
            #}
            bot.send_message(user_id=user_id, text=welcome, attachments=[main_menu_keyboard()])
        else:
            bot.send_message(user_id=user_id, text="Используйте кнопки меню или /start")

    elif update_type == 'message_callback':
        callback = update.get('callback')
        if not callback:
            logger.error("No 'callback' field in update")
            return

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

        elif payload == 'topup_menu':
            bot.send_message(user_id=user_id, text="Выберите пакет токенов:", attachments=[topup_keyboard()])

        elif payload == 'back_to_main':
            bot.send_message(user_id=user_id, text="Главное меню:", attachments=[main_menu_keyboard()])

        elif payload == 'subscriptions':
            bot.send_message(user_id=user_id, text="💎Выберите подписку:", attachments=[subscriptions_keyboard()])
            

        elif payload.startswith('sub_'):
            sub_data = SUBSCRIPTIONS.get(payload)
            if not sub_data:
                bot.send_message(user_id=user_id, text="Неизвестная подписка.")
                return
            try:
                payment_data = yookassa.create_payment(
                    amount=sub_data["price"],
                    description=f"Подписка {sub_data['name']} на месяц",
                    user_id=user_id,
                    metadata={'type': 'subscription', 'sub_key': payload, 'tokens': sub_data["tokens"]}
                )
                bot.send_message(
                    user_id=user_id,
                    text=f"💳 Для оформления подписки «{sub_data['name']}» перейдите по ссылке:\n{payment_data['confirmation_url']}\n\nПосле оплаты токены будут зачислены, а подписка активирована на месяц."
                )
            except Exception as e:
                logger.error(f"Payment error: {e}")
                bot.send_message(user_id=user_id, text="❌ Ошибка при создании платежа. Попробуйте позже.")
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
