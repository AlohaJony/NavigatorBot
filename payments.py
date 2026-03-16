import uuid
import logging
import requests
from yookassa import Configuration, Payment
from yookassa.domain.notification import WebhookNotification
from user_manager import add_tokens

logger = logging.getLogger(__name__)

class YooKassaClient:
    def __init__(self, shop_id, secret_key, return_url):
        Configuration.configure(shop_id, secret_key)
        self.return_url = return_url
        # Создаём сессию с таймаутами (10 секунд на соединение, 30 на чтение)
        self.session = requests.Session()
        self.session.timeout = (10, 30)
        # Устанавливаем эту сессию глобально для библиотеки yookassa

    def create_payment(self, amount: int, description: str, user_id: int, metadata: dict = None) -> dict:
        idempotence_key = str(uuid.uuid4())
        if metadata is None:
            metadata = {}
        metadata['user_id'] = user_id
        metadata['amount'] = amount

        try:
            logger.info(f"Calling Payment.create with idempotence_key={idempotence_key}")
            payment = Payment.create({
                "amount": {"value": f"{amount}.00", "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": self.return_url},
                "capture": True,
                "description": description,
                "metadata": metadata
            }, idempotence_key)
            logger.info(f"Payment created: id={payment.id}, url={payment.confirmation.confirmation_url}")
            return {
                "confirmation_url": payment.confirmation.confirmation_url,
                "payment_id": payment.id
            }
        except requests.exceptions.Timeout:
            logger.error("Payment creation timeout")
            raise Exception("Превышено время ожидания ответа от платёжной системы")
        except Exception as e:
            logger.error(f"Payment creation failed: {e}", exc_info=True)
            raise

    def handle_notification(self, request_json: dict) -> bool:
        try:
            notification = WebhookNotification(request_json)
            if notification.event == 'payment.succeeded':
                payment = notification.object
                metadata = payment.metadata
                user_id = metadata.get('user_id')
                amount = metadata.get('amount')
                if not user_id or not amount:
                    logger.error("Missing user_id or amount in metadata")
                    return False
                if metadata.get('type') == 'subscription':
                    tokens = int(metadata.get('tokens', 0))
                    sub_key = metadata.get('sub_key')
                    add_tokens(int(user_id), tokens, f"Подписка {sub_key}")
                    from datetime import datetime, timedelta
                    from user_manager import update_subscription_end
                    subscription_end = datetime.now() + timedelta(days=30)
                    update_subscription_end(int(user_id), subscription_end)
                    # Здесь можно отправить уведомление пользователю (если есть доступ к bot)
                else:
                    add_tokens(int(user_id), int(amount), f"Оплата ЮKassa (платёж {payment.id})")
                return True
            return False
        except Exception as e:
            logger.error(f"Notification error: {e}", exc_info=True)
            return False
