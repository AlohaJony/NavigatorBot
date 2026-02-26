import logging
import time
import os
import tempfile
from config import CONVERTER_BOT_TOKEN, NAVIGATOR_BOT_LINK
from max_client import MaxBotClient
from user_manager import get_or_create_user, get_balance, deduct_tokens, check_and_use_free_limit, get_price
from file_converter import FileConverter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not CONVERTER_BOT_TOKEN:
    raise ValueError("No CONVERTER_BOT_TOKEN in .env")

bot = MaxBotClient(CONVERTER_BOT_TOKEN)
BOT_ID = None

# Состояния: ожидание выбора формата после загрузки файла
# user_state[chat_id] = {'input_path': path, 'input_ext': ext}
user_state = {}

# Таблица соответствий расширений и возможных целевых форматов
# (упрощённо, можно взять из внешнего файла или даже сделать запрос к API)
# Для начала зададим основные соответствия.
FORMAT_MAP = {
    'png': ['jpg', 'webp', 'bmp', 'tiff'],
    'jpg': ['png', 'webp', 'bmp', 'tiff'],
    'jpeg': ['png', 'webp', 'bmp', 'tiff'],
    'gif': ['mp4', 'webm'],  # анимацию можно в видео
    'mp3': ['wav', 'ogg', 'flac', 'aac'],
    'wav': ['mp3', 'ogg', 'flac'],
    'mp4': ['avi', 'mkv', 'mov', 'webm'],
    'avi': ['mp4', 'mkv', 'webm'],
    'doc': ['pdf', 'docx', 'odt', 'txt'],
    'docx': ['pdf', 'doc', 'odt', 'txt'],
    'pdf': ['docx', 'jpg', 'png'],  # PDF в изображения сложнее, оставим на потом
    'srt': ['vtt', 'ass', 'ssa'],
    # ... можно добавить остальные
}

def get_target_formats(ext):
    return FORMAT_MAP.get(ext, [])

def handle_update(update):
    global BOT_ID
    update_type = update.get('update_type')
    logger.info(f"Update: {update_type}")

    if update_type == 'message_created':
        msg = update['message']
        if msg['sender'].get('is_bot') and msg['sender'].get('user_id') == BOT_ID:
            return
        chat_id = msg['recipient'].get('chat_id') or msg['recipient'].get('user_id')
        user_info = msg['sender']
        user_id = user_info['user_id']
        username = user_info.get('username')
        first_name = user_info.get('first_name')

        get_or_create_user(user_id, username, first_name)

        # Проверяем, есть ли вложения (файлы)
        attachments = msg.get('body', {}).get('attachments', [])
        if attachments:
            # Предполагаем, что первый attachment — файл
            file_att = attachments[0]
            if file_att['type'] in ['file', 'image', 'video', 'audio']:
                # Упрощённо: у нас есть токен файла, но нам нужна прямая ссылка для скачивания.
                # В MAX API можно получить URL для скачивания через метод GET /messages/{messageId},
                # но мы можем использовать token для скачивания через отдельный запрос.
                # Однако для простоты в демо можно пропустить и просто ответить.
                # В реальности нужно скачать файл по URL из attachment.
                # Пока сделаем заглушку, что файл получен.
                file_token = file_att['payload'].get('token')
                if not file_token:
                    bot.send_message(chat_id, "Не удалось получить токен файла.")
                    return
                # Скачиваем файл по токену (нужен метод для скачивания из MAX)
                # Реализуем позже. Пока используем тестовый подход.
                # Вместо этого предложим пользователю выбрать формат.
                # Для теста можно сохранить токен в состоянии.
                bot.send_message(chat_id, "Файл получен. Выберите целевой формат.")
                # Но пока не реализовано скачивание, пропустим.
                # Сейчас просто проигнорируем файлы.
                return

        # Текстовые сообщения
        text = msg.get('body', {}).get('text', '').strip()
        if text == '/start':
            welcome = (
                "👋 Привет! Я бот для конвертации файлов.\n"
                "Отправь мне файл, и я предложу доступные форматы для конвертации.\n"
                "У тебя есть 10 бесплатных конвертаций в день. Далее – за токены."
            )
            bot.send_message(chat_id, welcome)
        else:
            bot.send_message(chat_id, "Отправьте файл для конвертации или /start")

    elif update_type == 'message_callback':
        callback = update['callback']
        chat_id = callback['message']['recipient']['chat_id']
        user_id = callback['user']['user_id']
        payload = callback['payload']

        # Обрабатываем выбор формата
        if payload.startswith('convert_to_'):
            target_format = payload.replace('convert_to_', '')
            if chat_id in user_state:
                input_path = user_state[chat_id].get('input_path')
                if input_path and os.path.exists(input_path):
                    # Проверяем лимиты
                    price = get_price('converter')  # добавим в prices новую запись
                    if check_and_use_free_limit(user_id, 'converter'):
                        # Бесплатно
                        convert_and_send(chat_id, user_id, input_path, target_format)
                    else:
                        balance = get_balance(user_id)
                        if balance >= price:
                            if deduct_tokens(user_id, price, f"Конвертация в {target_format}"):
                                convert_and_send(chat_id, user_id, input_path, target_format)
                            else:
                                bot.send_message(chat_id, "❌ Ошибка списания токенов.")
                        else:
                            keyboard = {
                                "type": "inline_keyboard",
                                "payload": {
                                    "buttons": [[
                                        {"type": "link", "text": "💳 Пополнить баланс", "url": NAVIGATOR_BOT_LINK}
                                    ]]
                                }
                            }
                            bot.send_message(
                                chat_id,
                                f"❌ Недостаточно токенов. Стоимость конвертации: {price} токенов.\nВаш баланс: {balance}",
                                attachments=[keyboard]
                            )
                    # Удаляем состояние
                    del user_state[chat_id]
                else:
                    bot.send_message(chat_id, "Файл не найден. Попробуйте снова.")
            else:
                bot.send_message(chat_id, "Сессия устарела. Отправьте файл заново.")

def convert_and_send(chat_id, user_id, input_path, target_format):
    bot.send_action(chat_id, "typing_on")
    converter = FileConverter()
    try:
        output_path = converter.convert(input_path, target_format)
        # Загружаем результат в MAX
        # Определяем тип контента по расширению выходного файла
        ext = target_format
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff']:
            file_type = 'image'
        elif ext in ['mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a']:
            file_type = 'audio'
        elif ext in ['mp4', 'avi', 'mkv', 'mov', 'webm', 'flv']:
            file_type = 'video'
        else:
            file_type = 'file'

        token = bot.upload_file(output_path, file_type)
        if token:
            attachment = bot.build_attachment(file_type, token)
            caption = f"✅ Конвертация завершена!\nФайл сохранён как .{target_format}"
            bot.send_message(chat_id, caption, attachments=[attachment])
        else:
            bot.send_message(chat_id, "❌ Не удалось загрузить результат.")
    except Exception as e:
        logger.error(f"Conversion error: {e}")
        bot.send_message(chat_id, f"❌ Ошибка при конвертации: {str(e)}")
    finally:
        converter.cleanup()
        # Удаляем исходный временный файл
        try:
            os.remove(input_path)
        except:
            pass

def main():
    global BOT_ID
    logger.info("Starting Converter Bot...")
    me = bot.get_me()
    BOT_ID = me['user_id']
    logger.info(f"Bot ID: {BOT_ID}, username: @{me.get('username')}")

    # Добавим цену для конвертера в таблицу prices (если нет)
    # Это можно сделать через SQL или через скрипт инициализации.
    # Но проще выполнить один раз вручную.
    # Пока оставим комментарий.

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
