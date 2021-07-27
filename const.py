"""Contains constants used application-wide"""
from datetime import timedelta

DATABASE_FILEPATH = "database.db"
CONFIG_FILEPATH = "config.ini"

SHIP_DATA_EXPIRY = timedelta(days=7)
STANDALONE_DATA_EXPIRY = timedelta(days=1)
UPGRADE_DATA_EXPIRY = timedelta(days=1)
REDDIT_DATA_EXPIRY = timedelta(hours=1)

UPDATE_LOGS_ENTRY_LIMIT = 100

RSI_SCRAPER_STORE_NAME = "RSI"

MIN_LENGTH_EXCLUDES = [
    "G12",
    "G12R"
]
FUZZY_SEARCH_MAX_LEVENSHTEIN = 5
MAX_SHIP_NAME_LENGTH = 50


def update_max_ship_name_length(max_length: int):
    global MAX_SHIP_NAME_LENGTH
    MAX_SHIP_NAME_LENGTH = max_length
