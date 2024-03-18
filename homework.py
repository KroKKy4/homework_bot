from http import HTTPStatus
import logging
import os
import sys
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import KeyError, URLError, ParamError

load_dotenv()

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
    tokens_dict = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    error_list = []
    for key, value in tokens_dict.items():
        if not value:
            error_list.append(f'Отсутствует обязательная переменная {key}')

    return error_list


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    logging.info('Начало отправки сообщения в Telegram.')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception:
        logging.error('Сбой при отправке сообщения')
    else:
        logging.debug('Сообщение успешно отправлено в Telegram.')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    current_time = timestamp or int(time.time())
    params_request = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': current_time},
    }
    logging.info('Начало запроса к API.')
    try:
        response = requests.get(**params_request)

        if response.status_code != HTTPStatus.OK:
            raise URLError(f'Сбой при обращении к URL {response.request.url}')

        logging.debug('Ответ от сервера получен')
        response_data = response.json()

        if 'current_date' not in response_data:
            raise ParamError('Отсутствует параметр `current_date`')

    except requests.RequestException as e:
        raise (f'Ошибка отправки запроса. {e}')
    except Exception as ex:
        raise (f'Произошла ошибка: {ex}')
    return response_data


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Неправильный тип данных ответа сервера: {type(response)}'
        )

    if 'homeworks' not in response:
        raise KeyError(
            f'Ответ сервера не содержит ключ "homeworks": {response}'
        )

    if not isinstance(response['homeworks'], list):
        raise TypeError(
            'В ответе API домашки под ключом `homeworks`'
            ' данные приходят не в виде списка.'
        )

    return response.get('homeworks')


def parse_status(homework):
    """Извлекает из информации статус домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('В ответе отсутствует ключ homework_name')

    homework_name = homework.get('homework_name')

    if 'status' not in homework:
        raise KeyError('В ответе API домашки нет ключа `status`.')

    verdict = HOMEWORK_VERDICTS.get(homework.get('status'))

    if not verdict:
        raise KeyError(
            'API домашки возвращает недокументированный статус'
            ' домашней работы.'
        )

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if check_tokens():
        err_msg = 'Отсутствуют обязательные переменные'
        logging.critical(err_msg)
        logger.critical(err_msg.format(tokens=check_tokens()))
        sys.exit("Ошибка: Токены не прошли валидацию")

    last_send = {
        'error': None,
    }

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                homework_status = parse_status(homework[0])
                send_message(bot, homework_status)
            else:
                homework_status = parse_status(homework)
            timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_send['error'] != message:
                send_message(bot, message)
                last_send['error'] = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logger = logging.getLogger(__name__)

    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    main()
