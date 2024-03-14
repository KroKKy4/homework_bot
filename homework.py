import logging
import os
import sys
import time
from http import HTTPStatus
from tokenize import TokenError

import requests
import telegram
from dotenv import load_dotenv
from exceptions import StatusError, TelegramError, URLError

load_dotenv()

GREETINGS_TEXT = 'Привет!'
SUCCESSFUL_SENDING_TEXT = 'Сообщение успешно отправлено'

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    source = ("PRACTICUM_TOKEN", "TELEGRAM_TOKEN", "TELEGRAM_CHAT_ID")
    token_list = [token for token in source if not globals()[token]]
    if token_list:
        text_error = f'''Отсутствует обязательная переменная окружения:
        {" ".join(token_list)}'''
        logging.critical(text_error)
        raise TokenError(text_error)


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту."""
    params = {'from_date': timestamp}
    logging.info(f'Производим запрос к {ENDPOINT} c params={params}')
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            raise URLError(f'Эндпоинт - {ENDPOINT} недоступен')
        logging.info(f'Запрос к {ENDPOINT} c params={params} успешен')
        return response.json()
    except requests.RequestException:
        raise ConnectionError(f'Сбой запроса к {ENDPOINT} c params={params}!')


def check_response(response):
    """Проверяет ответ API на соответствие."""
    logging.info('Проверка ответа от сервера')
    if not isinstance(response, dict):
        raise TypeError('Структура данных не соответствует заданной')
    if 'homeworks' not in response:
        raise KeyError('Ключ - "homeworks" отсутствует')
    if 'current_date' not in response:
        raise KeyError('Ключ - "current_date" отсутствует')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Структура данных "homeworks" не '
                        'соответствует заданной')
    logging.info('Проверку API-ответа сервера успешна')
    return homeworks


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    logging.info('Начинаем проверку статуса домашней работы')
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError('Ключ "homework_name" отсутствует')
    status = homework.get('status')
    if not status:
        raise KeyError('Ключ "status" отсутствует')
    verdict = HOMEWORK_VERDICTS.get(status)
    if not verdict:
        raise StatusError('Неизвестный статус домашней работы')
    logging.info('Проверка статуса домашней работы успешна')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    logging.info('Начинаем отправку сообщения!')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(SUCCESSFUL_SENDING_TEXT)
    except TelegramError:
        logging.error('Ошибка отправки')


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    send_message(bot, GREETINGS_TEXT)
    start_error_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if not homework:
                logging.debug('Нет новых статусов у работ')
            else:
                homework_status = parse_status(homework[0])
                send_message(bot, homework_status)
            timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message, exc_info=True)
            if start_error_message != message:
                send_message(bot, message)
                start_error_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        encoding='utf-8',
        format='%(asctime)s [%(levelname)s] [функция %(funcName)s '
               'стр.%(lineno)d] - %(message)s'
    )
    logging.StreamHandler(sys.stdout)
    main()
