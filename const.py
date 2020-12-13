"""Contains constants used application-wide"""
from datetime import timedelta
from logging import Filter

DATABASE_FILEPATH = "database.db"
CONFIG_FILEPATH = "config.ini"

SHIP_DATA_EXPIRY = timedelta(days=7)
UPGRADE_DATA_EXPIRY = timedelta(days=1)


class __SuppressAllLoggingFilter(Filter):
    def filter(self, record) -> bool:
        return False


SUPPRESS_ALL_LOGGING_FILTER = __SuppressAllLoggingFilter()
