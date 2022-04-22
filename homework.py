import logging
import os
import sys
import time
from http import HTTPStatus

from dotenv import load_dotenv

import requests

import telegram


load_dotenv()
logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    format='%(funcName)s, %(lineno)s, %(levelname)s, %(message)s',
    filemode='w'
)
logger = logging.getLogger(__name__)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
MONTH_PERIOD = 15925248
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправить сообщение в TG чат.
    аргументы:
        bot: объект класса telegram.Bot, от которого придет сообщение,
        message: строка сообщения, отправляемая ботом.
    """
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info(
            f'Сообщение отправлено в телеграм чат {TELEGRAM_CHAT_ID}:{message}'
        )
    except Exception as error:
        logger.exception(f'Cбой при отправке сообщения в Telegram: {error}')
        raise error(f'Cбой при отправке сообщения в Telegram: {error}')


def get_api_answer(current_timestamp):
    """Запросить эндпоинт API-сервиса.
    аргументы:
        current_timestamp: временная метка.
    При HTTPStatus.OK возвратить responce в формате json().
    """
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT,
                                headers=HEADERS,
                                params=params
                                )
    except Exception as error:
        logger.error(f'Ошибка при запросе к эндпоинту API-сервиса: {error}')
        raise error('get() missing 1 required positional argument')

    status_code = response.status_code
    if status_code != HTTPStatus.OK:
        logger.error(f'Недоступность эндпоинта {status_code}')
        raise Exception(f'Недоступность эндпоинта {status_code}')
    return response.json()


def check_response(response):
    """Проверить ответ API на корректность.
    аргументы:
       responce = ответ API в .json() формате.
    При ожидаемом ответе, вернуть список домашних
    работ по ключу ['homeworks']
    """
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарём')
    try:
        list_homeworks = response['homeworks']
    except KeyError as error:
        logger.error(f'Ошибка словаря по ключу homeworks {error}')
        raise KeyError(f'Ошибка словаря по ключу homeworks {error}')
    try:
        homework = list_homeworks[0]
    except IndexError as error:
        logger.error(f'Список домашних работ пуст {error}')
        raise IndexError(f'Список домашних работ пуст {error}')
    return homework


def parse_status(homework):
    """Извлечь из информации о конкретной домашней работе статус этой работы.
    аргументы:
        homework = список домашних работ из словаря homeworks
    Возвратить название работы, вердикт из словаря HOMEWORK_STATUSES.
    """
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует ключ "homework_name" в ответе API')
    if 'status' not in homework:
        raise Exception('Отсутствует ключ "status" в ответе API')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    try:
        verdict = HOMEWORK_STATUSES[homework_status]
    except Exception as error:
        logger.error(f'Недокументированный статус ДЗ {error}')
        raise Exception(f'Недокументированный статус ДЗ {error}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности всех переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = (int(time.time() - MONTH_PERIOD))
    if not check_tokens():
        logger.critical('TOKEN_NOT_FOUND')
        raise ValueError('Отсутствуют одна или несколько переменных окружения')

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework:
                send_message(bot, parse_status(homework))
            current_timestamp = response.get('current_date', current_timestamp)
        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}')
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt='[%(asctime)s: %(levelname)s] %(message)s'
        )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    main()
