import uuid
import logging
import requests
from yookassa import Configuration, Payment
from yookassa.domain.notification import WebhookNotification
from user_manager import add_tokens

logger = logging.getLogger(__name__)
# глобальная ссылка на бота (будет установлена из navigator_bot.py)
bot_instance = None
class YooKassaClient:
    def __init__(self, shop_id, secret_key, return_url):
        Configuration.configure(shop_id, secret_key)
        self.return_url = return_url

    def create_payment(self, amount: int, description: str, user_id: int, metadata: dict = None) -> dict:
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
        session = requests.Session()
        session.timeout = (10, 30)
        try:
            logger.info(f"Calling Payment.create with idempotence_key={idempotence_key}")
            payment = Payment.create({
                "amount": {"value": f"{amount}.00", "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": self.return_url},
                "capture": True,
                "description": description,
                "metadata": metadata
            }, idempotence_key)
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
        logger.info(f"Webhook received: {request_json}")
        try:
            notification = WebhookNotification(request_json)
            logger.info(f"Notification event: {notification.event}")
            if notification.event == 'payment.succeeded':
                payment = notification.object
                logger.info(f"Payment succeeded: id={payment.id}, metadata={payment.metadata}")
                metadata = payment.metadata
                user_id = metadata.get('user_id')
                amount = metadata.get('amount')
                if not user_id or not amount:
                    logger.error("Missing user_id or amount in metadata")
                    return False

                # Определяем, подписка это или обычное пополнение
                if metadata.get('type') == 'subscription':
                    tokens = int(metadata.get('tokens', 0))
                    sub_key = metadata.get('sub_key')
                    # Начисляем токены
                    add_tokens(int(user_id), tokens, f"Подписка {sub_key}")
                    logger.info(f"Subscription tokens added: user {user_id}, tokens {tokens}")
                    if user_id:
                        try:
                            bot_instance.send_message(
                                user_id=int(user_id),
                                text=f"✅ Оплата прошла успешно!\nВам начислено {tokens} токенов. Подписка активна до {subscription_end.strftime('%d.%m.%Y')}."
                            )
                            logger.info(f"Notification sent to user {user_id}")
                        except Exception as e:
                            logger.error(f"Failed to send notification: {e}")

                    # Устанавливаем дату окончания подписки (30 дней)
                    from datetime import datetime, timedelta
                    from user_manager import update_subscription_end
                    subscription_end = datetime.now() + timedelta(days=30)
                    update_subscription_end(int(user_id), subscription_end)
                    logger.info(f"Subscription end set to {subscription_end} for user {user_id}")

                    # Отправляем уведомление пользователю (здесь нужен доступ к bot)
                    # Пока оставим комментарий, реализуем позже
                else:
                    # Обычное пополнение (если будет)
                    add_tokens(int(user_id), int(amount), f"Оплата ЮKassa (платёж {payment.id})")
                    logger.info(f"Tokens added: user {user_id}, amount {amount}")

                return True
            return False
        except Exception as e:
            logger.error(f"Notification error: {e}", exc_info=True)
            return False
