"""Бот для получения статуса домашней работы от ЯП."""
import logging
import os
import time
from http import HTTPStatus
from urllib.error import HTTPError

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='Bot.log',
    encoding="utf-8",
    filemode='a',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

PRACTICUM_TOKEN = os.getenv('PRACT_TOKEN')
TELEGRAM_TOKEN = os.getenv('TEL_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Функция проверки наличия переменных окружения."""
    if not TELEGRAM_CHAT_ID or not TELEGRAM_TOKEN:
        logger.critical('Отцутствует токен.')
        return False
    if not PRACTICUM_TOKEN:
        raise SystemError('Отцутствует токен')

    return True


def get_api_answer(timestamp):
    """Функция делает запрос  API-сервиса."""
    logger.info('Проверка ответа от API...')
    timestamp = int(time.time())
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
    except Exception as error:
        raise f'Ощибка при запросе:{payload} к API: {error}.'
    if response.status_code != HTTPStatus.OK:
        raise HTTPError(f'API не отвечает: {response.status_code}')
    return response.json()


def check_response(response):
    """Проверка ответа API."""
    logger.info('Начало проверки ответа сервера')
    if not isinstance(response, dict):
        logger.error('Тип данных ответа API не является словарём')
        raise TypeError('response is not dict')
    if 'homeworks' not in response:
        logger.error('Нет ключа homeworks')
        raise KeyError('KeyError homeworks')
    if not isinstance(response.get('homeworks'), list):
        logger.error('homeworks не список')
        raise TypeError('homeworks is not list')
    return response['homeworks']


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
        logger.info(f'Начало отправки сообщения со статусом '
                    f'домашней работы: {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logger.error(f'Не удалось отправить сообщение: {error}')
    else:
        logger.debug('Сообщение отправленно!')
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)[0]
            message = parse_status(homework)
            if message is not None:
                send_message(bot, message)
            else:
                message = 'Статус работы не изменился'
                send_message(bot, message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            bot.send_message(TELEGRAM_CHAT_ID, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
