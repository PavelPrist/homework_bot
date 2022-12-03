import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import APIEndPointIsNotAvailable, NonCorrectResponseFromAPI

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


def check_tokens() -> bool:
    """
    Проверяет доступность переменных окружения, которые необходимы для работы.
    Если отсутствует хотя бы одна переменная окружения —
    бот прекращает работу.
    """
    logging.info('Проверяем доступность переменных окружения')
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot: telegram.bot.Bot, message: str) -> None:
    """
    Отправляет сообщение в Telegram чат.
    определяемый переменной окружения TELEGRAM_CHAT_ID
    """
    try:
        logging.info('Отправка статуса в telegram')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug(f'Успешная отправка сообщения: {message}')
    except Exception as error:
        logging.error(f'Ошибка отправки сообщения в Telegram - {error}')
        raise Exception(f'Ошибка при отправке сообщения-статус: {error}')


def get_api_answer(current_timestamp: int) -> dict:
    """
    Делает запрос к единственному эндпоинту API Yandex-сервиса.
    В качестве параметра в функцию передается временная метка.
    В случае успешного запроса должна вернуть ответ API,
    приведя его из формата JSON к типам данных Python
    """
    timestamp = current_timestamp or int(time.time())
    logging.info(f'<><><><><><><><><>><><><><><><><><><><><><><><><><><><><>>'
                 f'Запрос к API. URL: {ENDPOINT}, время: {timestamp}')
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            logging.error(
                f'Ответ API не вернул статус 200 ОК.'
                f'Ответ вернул код: {response.status_code}.'
                f'Причина: {response.reason}.'
                f'Текст: {response.text}.'
            )
            raise APIEndPointIsNotAvailable(
                'Ответ API не вернул статус 200 ОК.'
            )
        response_json = response.json()
        logging.debug(
            f'По запросу к API, получен ответ- {response_json}')
        return response_json
    except Exception as error:
        logging.error(f'Ошибка при запросе к API: {error}')
        raise APIEndPointIsNotAvailable(f'Ошибка при запросе к API: {error}')


def check_response(response: dict) -> list:
    """
    Проверяет ответ API на соответствие документации.
    В качестве параметра функция получает ответ API,
    приведенный к типам данных Python
    """
    logging.info('Проверка корректности ответа API')
    if not isinstance(response, dict):
        logging.error('Полученный ответ API не является dict')
        raise TypeError('Полученный ответ API не является dict')
    if 'homeworks' not in response or 'current_date' not in response:
        logging.error('Нет ключей homeworks или current_date в ответе API')
        raise NonCorrectResponseFromAPI('Нет ключа homeworks в ответе API')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        logging.error(f'Ответ в API homeworks:{homeworks} не является list')
        raise TypeError(f'Ответ в API homeworks:{homeworks} не является list')
    return homeworks


def parse_status(homework: dict) -> str:
    """
    Извлекает из информации о конкретной домашней работе статус этой работы.
    В случае успеха, функция возвращает подготовленную для отправки в Telegram
    строку, содержащую один из вердиктов словаря HOMEWORK_VERDICTS.
    """
    logging.info('Извлекаем статус работы для отправки в Telegram')
    if 'homework_name' not in homework:
        logging.error('Нет ключа homework_name в ответе API')
        raise KeyError('Нет ключа homework_name в ответе API')

    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(f'Неизвестный статус работы - {homework_status}')

    verdict = HOMEWORK_VERDICTS[homework_status]
    logging.info(f'Статус работы {homework_name}: {verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота и логирование."""
    log = '%(filename)s, %(asctime)s, %(name)s, %(levelname)s, %(message)s'
    logging.basicConfig(
        handlers=[
            logging.FileHandler(
                os.path.abspath('program.log'), mode='a', encoding='UTF-8'),
            logging.StreamHandler(sys.stdout)
        ],
        level=logging.DEBUG,
        format=log,
    )

    if not check_tokens():
        message = 'Отсутствуют переменные окружения. Бот прекращает работу!'
        logging.critical(message)
        sys.exit(message)

    logging.info('Telegram bot начал работу')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = 1667322796
    send_message(bot, 'Telegram bot начал работу')
    last_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            current_timestamp = response.get('current_date')
            homeworks_response = check_response(response)
            if homeworks_response:
                message = parse_status(homeworks_response[0])
            else:
                message = 'Статус не изменился'
            if message != last_message:
                send_message(bot, message)
                last_message = message
                logging.info(f'Получен новый статус домашней работы:{message}')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message, exc_info=True)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
