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

REDDIT_PARSE_EXCLUDE_KEYWORDS = ["Upgrade", "from"]

FUZZY_SEARCH_MIN_SCORE = 60
FUZZY_SEARCH_PERFECT_MATCH_MIN_SCORE = 90
