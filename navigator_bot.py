import logging
import time
import threading
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from config import NAVIGATOR_TOKEN, DOWNLOADER_BOT_LINK, PDF_BOT_LINK, AUDIO_BOT_LINK, TTS_BOT_LINK, IMAGE_BOT_LINK, YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, YOOKASSA_RETURN_URL, WEBHOOK_BASE
from max_client import MaxBotClient
from user_manager import get_or_create_user, get_balance, add_tokens
from payments import YooKassaClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    """
    Создаёт клавиатуру с двумя колонками:
    - Первые пять кнопок: ссылки на ботов (с пометкой в разработке для неготовых)
    - Отдельная строка: кнопки "Мой баланс" и "Пополнить" на всю ширину
    """
    return {
        "type": "inline_keyboard",
        "payload": {
            "buttons": [
                # Первый ряд: два бота
                [
                    {"type": "link", "text": "🎬 Скачать видео", "url": DOWNLOADER_BOT_LINK},
                    {"type": "link", "text": "📄 Конвертер (⚡)", "url": PDF_BOT_LINK}
                ],
                # Второй ряд
                #[
                #    {"type": "link", "text": "🎵 Аудио из видео (в разработке)", "url": AUDIO_BOT_LINK},
                #    {"type": "link", "text": "🗣 Озвучка (в разработке)", "url": TTS_BOT_LINK}
                #],
                # Третий ряд
                #[
                #    {"type": "link", "text": "🎨 Генерация (в разработке)", "url": IMAGE_BOT_LINK},
                #    
                #],
                # Нижняя строка на всю ширину (две кнопки рядом)
                [
                    {"type": "callback", "text": "💎 Подписки", "payload": "subscriptions"}
                    {"type": "callback", "text": "💰 Мой баланс", "payload": "balance"},
                    {"type": "callback", "text": "💳 Пополнить", "payload": "topup_menu"}
                ]
            ]
        }
    }

def topup_keyboard():
    """
    Клавиатура с вариантами пополнения (пакеты токенов в стиле СССР)
    """
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
            # Можно отправить информацию о подписках
            text = (
                "💎 **Подписки (скоро)**\n\n"
                "С подпиской вы получаете доступ ко всем платным функциям!\n"
                "Следите за обновлениями."
            )
            bot.send_message(user_id=user_id, text=text)

        elif payload.startswith('topup_'):
            amount = int(payload.split('_')[1])
            try:
                payment_data = yookassa.create_payment(
                    amount=amount,
                    description=f"Пополнение баланса на {amount} токенов",
                    user_id=user_id
                )
                bot.send_message(
                    user_id=user_id,
                    text=f"💳 Для пополнения на {amount} токенов перейдите по ссылке:\n{payment_data['confirmation_url']}\n\nПосле оплаты баланс будет зачислен автоматически."
                )
            except Exception as e:
                logger.error(f"Payment creation error: {e}")
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
