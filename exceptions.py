class APIEndPointIsNotAvailable(Exception):
    """Обработка исключения при недоступности ENDPOINT API."""
    pass


class NonCorrectResponseFromAPI(Exception):
    """В ответе API отсутствует current_date или homework статус."""
    pass
