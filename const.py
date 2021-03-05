"""Contains constants used application-wide"""
from datetime import timedelta

DATABASE_FILEPATH = "database.db"
CONFIG_FILEPATH = "config.ini"

SHIP_DATA_EXPIRY = timedelta(days=7)
STANDALONE_DATE_EXPIRY = timedelta(days=1)
UPGRADE_DATA_EXPIRY = timedelta(days=1)
