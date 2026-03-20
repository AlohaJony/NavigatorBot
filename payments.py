import uuid
import logging
import requests
from yookassa import Configuration, Payment
from yookassa.domain.notification import WebhookNotification
from user_manager import add_tokens, update_subscription_end, transaction_exists_by_payment
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# глобальная ссылка на бота (устанавливается из navigator_bot.py)
bot_instance = None

class YooKassaClient:
    def __init__(self, shop_id, secret_key, return_url):
        Configuration.configure(shop_id, secret_key)
        self.return_url = return_url

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
        except requests.exceptions.ConnectionError:
            logger.error("Payment creation connection error")
            raise Exception("Ошибка соединения с платёжной системой")
        except Exception as e:
            logger.error(f"Payment creation failed: {e}", exc_info=True)
            raise

    def handle_notification(self, request_json: dict) -> bool:
        global bot_instance
        try:
            notification = WebhookNotification(request_json)
            logger.info(f"Webhook received: event={notification.event}")
            if notification.event == 'payment.succeeded':
                payment = notification.object
                logger.info(f"Payment succeeded: id={payment.id}, metadata={payment.metadata}")

                # Проверка в БД (дубли)
                if transaction_exists_by_payment(payment.id):
                    logger.warning(f"Duplicate payment {payment.id} in DB, skipping")
                    return True

                metadata = payment.metadata
                logger.info(f"Metadata in notification: {metadata}")
                if 'mid_progress' in metadata:
                    logger.info(f"mid_progress = {metadata['mid_progress']}")
                user_id = metadata.get('user_id')
                amount = metadata.get('amount')
                if not user_id or not amount:
                    logger.error("Missing user_id or amount in metadata")
                    return False

                if metadata.get('type') == 'subscription':
                    tokens = int(metadata.get('tokens', 0))
                    sub_key = metadata.get('sub_key')
                    # получаем название подписки (импортируем словарь из navigator_bot)
                    from navigator_bot import SUBSCRIPTIONS
                    sub_name = SUBSCRIPTIONS.get(sub_key, {}).get('name', 'подписке')

                    # Начисляем токены с payment_id
                    add_tokens(int(user_id), tokens, f"Подписка {sub_key} (payment {payment.id})", payment_id=payment.id)

                    # Устанавливаем дату окончания подписки (30 дней)
                    subscription_end = datetime.now() + timedelta(days=30)
                    update_subscription_end(int(user_id), subscription_end)

                    # Удаляем предыдущие сообщения и отправляем уведомление
                    mid_progress = metadata.get('mid_progress')
                    mid_link = metadata.get('mid_link')
                    if bot_instance:
                        if mid_progress:
                            try:
                                logger.info(f"Attempting to delete progress message: {mid_progress}")
                                result = bot_instance.delete_message(message_id=mid_progress, user_id=user_id)
                                logger.info(f"Deleted progress message: {result}")
                            except Exception as e:
                                logger.error(f"Failed to delete progress message: {e}")
                        if mid_link:
                            try:
                                logger.info(f"Attempting to delete link message: {mid_link}")
                                result = bot_instance.delete_message(message_id=mid_link, user_id=user_id)
                                logger.info(f"Deleted link message: {result}")
                            except Exception as e:
                                logger.error(f"Failed to delete link message: {e}")
                        # Отправляем уведомление
                        bot_instance.send_message(
                            user_id=user_id,
                            text=f"✅ Вы приобрели подписку «{sub_name}»! Баланс пополнен на {tokens} токенов."
                        )
                        # Отправляем сообщение с предложением выбрать бота
                        if hasattr(payments, 'main_menu_keyboard'):
                            bot_instance.send_message(
                                user_id=user_id,
                                text="Теперь выберите нужного бота:",
                                attachments=[payments.main_menu_keyboard()]
                            )
                else:
                    # Обычное пополнение (если будет)
                    add_tokens(int(user_id), int(amount), f"Оплата ЮKassa (платёж {payment.id})", payment_id=payment.id)
                return True
            return False
        except Exception as e:
            logger.error(f"Notification error: {e}", exc_info=True)
            return False
