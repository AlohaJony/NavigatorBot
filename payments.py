import uuid
import logging
from yookassa import Configuration, Payment
from yookassa.domain.notification import WebhookNotification
from user_manager import add_tokens

logger = logging.getLogger(__name__)

class YooKassaClient:
    def __init__(self, shop_id, secret_key, return_url):
        Configuration.configure(shop_id, secret_key)
        self.return_url = return_url

    def create_payment(self, amount: int, description: str, user_id: int) -> dict:
        """
        Создаёт платёж в ЮKassa.
        amount - сумма в рублях (целое число)
        description - описание (например, "Пополнение баланса")
        user_id - ID пользователя в MAX (будет передано в metadata)
        Возвращает словарь с confirmation_url и payment_id.
        """
        idempotence_key = str(uuid.uuid4())
        payment = Payment.create({
            "amount": {
                "value": f"{amount}.00",
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": self.return_url
            },
            "capture": True,
            "description": description,
            "metadata": {
                "user_id": user_id,
                "amount": amount
            }
        }, idempotence_key)
        return {
            "confirmation_url": payment.confirmation.confirmation_url,
            "payment_id": payment.id
        }

    def handle_notification(self, request_json: dict) -> bool:
        """
        Обрабатывает уведомление от ЮKassa (вебхук).
        Возвращает True, если платёж успешен и обработан.
        """
        try:
            notification = WebhookNotification(request_json)
            if notification.event == 'payment.succeeded':
                payment = notification.object
                metadata = payment.metadata
                user_id = metadata.get('user_id')
                amount = metadata.get('amount')
                if user_id and amount:
                    add_tokens(int(user_id), int(amount), f"Оплата ЮKassa (платёж {payment.id})")
                    logger.info(f"User {user_id} credited with {amount} tokens")
                    return True
            return False
        except Exception as e:
            logger.error(f"Notification error: {e}")
            return False
