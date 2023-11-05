import json
import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

# from exceptions import APIValueException

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACT_TOKEN')
TELEGRAM_TOKEN = os.getenv('TEL_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='a',
    format='%(asctime)s  [%(levelname)s]  %(message)s'
)
logger = logging.getLogger(__name__)
streamHandler = logging.StreamHandler(sys.stdout)
streamHandler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s  [%(levelname)s]  %(message)s')
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)


def send_message(bot, message):
    """Отправляет сообщение в бот."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info(message)
    except telegram.error.TelegramError:
        logger.error('Проблемы отправки сообщений в Telegram')


def get_api_answer(current_timestamp):
    """Делает запрос к API-сервисау."""
    # timestamp = current_timestamp or int(time.time())
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            raise APIValueException(
                f'API недоступен: ошибка {response.status_code}')
        return response.json()
    except json.JSONDecodeError:
        raise APIValueException('Проблема с конвертацией из JSON ответа API')
    except requests.ConnectionError:
        raise ConnectionError('Сервер не доступен')


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Полученный ответ не словарь')
    if 'homeworks' not in response:
        raise KeyError('Нет ключа homeworks')
    if not isinstance(response['homeworks'], list):
        raise TypeError('В ответе нет списка')
    return response.get('homeworks')


def parse_status(homework):
    """Обрабатывает полученную домашнюю работу."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES[homework_status]
    elif homework_name is None:
        raise KeyError('Отсутствует ключ homework_status')
    elif homework_status is None:
        raise KeyError('Отсутствует ключ homework_name')
    else:
        raise KeyError('Неожиданный статус')
    logger.info('Измение статуса домашнего задания получено')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка переменных окружения."""
    tokens = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    counter = 0
    for name in tokens:
        token = globals()[name]
        if not token:
            counter += 1
            logger.critical(f'Не хватает переменной {name}')
    if counter > 0:
        return False
    logger.info('Все переменные окружения получены')
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    old_message = ''

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework_date = check_response(response)
            if len(homework_date) == 0:
                logger.debug('Статус домашней работы не изменился')
            else:
                message = parse_status(homework_date[0])
                send_message(bot, message)
                current_timestamp = response.get('current_date')
            old_message = ''
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if old_message != message:
                send_message(bot, message)
                old_message = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()