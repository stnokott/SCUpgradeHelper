"""Contains constants used application-wide"""
from logging import Filter
DATABASE_FILEPATH = "database.db"
CONFIG_FILEPATH = "config.ini"


class __SuppressAllLoggingFilter(Filter):
    def filter(self, record) -> bool:
        return False


SUPPRESS_ALL_LOGGING_FILTER = __SuppressAllLoggingFilter()
