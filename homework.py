"""Бот для получения статуса домашней работы от ЯП."""
import logging
import os
import time
from http import HTTPStatus
from logging import StreamHandler
from urllib.error import HTTPError

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

PRACTICUM_TOKEN = os.getenv('PRACT_TOKEN')
TELEGRAM_TOKEN = os.getenv('TEL_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')
TOKENS = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

TOKEN_ERROR = 'Отсутствует токен {name}'
TOKENS_ERROR = 'Отсутствует токены {no_tokens}'
INFO_API_START = 'Проверка ответа от API...'
API_ERROR_REQUEST = 'Ощибка при запросе:{payload} к API: {error}.'
API_ERROR_CONNECT = 'Ошибка соединения {error}'
API_ERROR_TIME = 'Время ожидания превышено {error}'
API_ERROR_HTTP = 'API не отвечает: {response.status_code}'
INFO_API_CHECK_START = 'Начало проверки ответа сервера'
API_ERROR_DICT = 'response не является словарём'
API_ERROR_KEY = 'Нет ключа: homeworks'
API_ERROR_LIST = 'homeworks не список'
INFO_SEND_MESSAGE = ('Начало отправки сообщения, '
                     'со статусом домашней работы: {message}')
SEND_MESSAGE_ERROR = 'Не удалось отправить сообщение: {error}'
SEND_MESSAGE_DONE = 'Сообщение отправленно!'
SLEEP_MODE = 'Режим ожидания'


class APIError(Exception):
    """Ошибка API."""


def check_tokens():
    """Функция проверки наличия переменных окружения."""
    no_tokens = []
    for name in TOKENS:
        if globals()[name] is None:
            logger.critical(TOKEN_ERROR.format(name=name))
            no_tokens.append(name)
    if no_tokens != []:
        raise SystemError(TOKENS_ERROR.format(no_tokens=no_tokens))

    return True


def get_api_answer(timestamp):
    """Функция делает запрос  API-сервиса."""
    logger.info(INFO_API_START)
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)

    except requests.exceptions.Timeout as error:
        raise requests.exceptions.Timeout(
            API_ERROR_TIME.format(error=error))

    except requests.exceptions.ConnectionError as error:
        raise requests.exceptions.ConnectionError(
            API_ERROR_CONNECT.format(error=error))

    except requests.exceptions.RequestException as error:
        raise ConnectionError(
            API_ERROR_REQUEST.format(payload=payload, error=error))

    if response.status_code != HTTPStatus.OK:
        raise HTTPError(
            API_ERROR_HTTP.format(response.status_code))
    return response.json()


def check_response(response):
    """Проверка ответа API."""
    logger.info(INFO_API_CHECK_START)
    if not isinstance(response, dict):
        logger.error('Тип данных ответа API не является словарём')
        raise TypeError(API_ERROR_DICT)

    if 'homeworks' not in response:
        logger.error('Нет ключа: homeworks')
        raise APIError(API_ERROR_KEY)

    if not isinstance(response.get('homeworks'), list):
        logger.error('homeworks не список')
        raise TypeError(API_ERROR_LIST)

    return response.get('homeworks')


def parse_status(homework):
    """Информация о конкретной домашней работе, статус этой работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework == []:
        return None
    if not homework_name:
        raise KeyError('Домашняя работа не найдена')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('В ответе не верный статус работы')

    verdict = HOMEWORK_VERDICTS[homework_status]

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Функция отправляет сообщение в Telegram чат."""
    try:
        logger.info(INFO_SEND_MESSAGE.format(message=message))
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.TelegramError as error:           # !!!!
        logger.error(SEND_MESSAGE_ERROR.format(error=error))
    else:
        logger.debug(SEND_MESSAGE_DONE)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    empty_message = ''
    while True:
        try:
            response = get_api_answer(timestamp=timestamp)
            timestamp = response['current_date']
            homework = check_response(response)[0]
            message = parse_status(homework)
            if message is not None:
                send_message(bot, message)
            else:
                message = 'Статус работы не изменился'
                send_message(bot, message)

        except Exception as error:
            if error != empty_message:
                message = f'Сбой в работе программы: {error}'
                logging.error(message)
                bot.send_message(TELEGRAM_CHAT_ID, message)
        finally:
            logger.info(SLEEP_MODE)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename=__file__ + '.log',
        encoding="utf-8",
        filemode='a',
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
    )
    handler = StreamHandler()
    logger.addHandler(handler)
    formatter = logging.Formatter(
        '%(asctime)s, %(levelname)s, %(message)s, %(name)s'
    )
    handler.setFormatter(formatter)

    main()
