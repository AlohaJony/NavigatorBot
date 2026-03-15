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
        logger.info(f"create_payment called with amount={amount}, user_id={user_id}, metadata={metadata}")
        idempotence_key = str(uuid.uuid4())
        if metadata is None:
            metadata = {}
        # обязательно добавляем user_id и amount в metadata для идентификации при вебхуке
        metadata['user_id'] = user_id
        metadata['amount'] = amount
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
        try:
            notification = WebhookNotification(request_json)
            if notification.event == 'payment.succeeded':
                payment = notification.object
                metadata = payment.metadata
                user_id = metadata.get('user_id')
                amount = metadata.get('amount')
                if not user_id or not amount:
                    return False

                if metadata.get('type') == 'subscription':
                    tokens = int(metadata.get('tokens', 0))
                    from datetime import datetime, timedelta
                    # Начисляем токены
                    add_tokens(int(user_id), tokens, f"Подписка {metadata.get('sub_key')}")
                    # Устанавливаем дату окончания подписки
                    from user_manager import update_subscription_end
                    subscription_end = datetime.now() + timedelta(days=30)
                    update_subscription_end(int(user_id), subscription_end)
                    logger.info(f"Subscription activated for user {user_id} until {subscription_end}")
                else:
                    # Обычное пополнение (если осталось)
                    add_tokens(int(user_id), int(amount), f"Оплата ЮKassa (платёж {payment.id})")
                return True
            return False
        except Exception as e:
            logger.error(f"Notification error: {e}")
            return False
