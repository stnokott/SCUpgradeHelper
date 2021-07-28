"""Contains constants used application-wide"""
from datetime import timedelta
from math import floor

DATABASE_FILEPATH = "database.db"
CONFIG_FILEPATH = "config.ini"

SHIP_DATA_EXPIRY = timedelta(days=7)
RSI_STANDALONE_DATA_EXPIRY = timedelta(days=1)
RSI_UPGRADE_DATA_EXPIRY = timedelta(days=1)
REDDIT_DATA_EXPIRY = timedelta(hours=1)

UPDATE_LOGS_ENTRY_LIMIT = 100

RSI_SCRAPER_STORE_NAME = "RSI"
RSI_SCRAPER_STORE_URL = "https://robertsspaceindustries.com/pledge"

REDDIT_PARSE_EXCLUDE_KEYWORDS = [
    "Upgrade",
    "from",
    " Paint",
    " Skin",
    " Armor",
    " Helmet",
    " Leg",
    " Undersuit",
    " Outfit",
    " Uniform",
    " Jacket",
    " Addon",  # Endeavour
    " Add-On",  # Endeavour
    " Pod",  # Endeavour
    " Gear",
    " Pack",
    " Module",
    " & ",
    " Model",
    " Mini",
    " Replica",
    " Figure",
    "Music",
    "Puglisi",
    " Trophy",
    " Plaque",
    " Collection",
    "Pistol",
    "Shotgun",
    "Sniper",
    "Knife",
    "Grenade",
    " Hangar",
    " Set",
    " Calendar",
    "JukeBox",
    "Juke Box",
    " Flower",
    " Cactus",
    " Tree",
]

FUZZY_SEARCH_PERFECT_MATCH_MIN_SCORE = 90

_FUZZY_SEARCH_MIN_SCORE_BASE = 65  # base of min score, does not increase, only decrease
_FUZZY_SEARCH_MIN_SCORE_MAX_OFFSET = 10  # max amount to decrease min score by
_FUZZY_SEARCH_LENGTH_OFFSET_FACTOR = 0.3  # scales query length to min score, lower values cause higher offsets for shorter queries


def fuzzy_search_min_score(length: int) -> int:
    return _FUZZY_SEARCH_MIN_SCORE_BASE - (
        10
        - min(
            max(floor(length * _FUZZY_SEARCH_LENGTH_OFFSET_FACTOR), 0),
            _FUZZY_SEARCH_MIN_SCORE_MAX_OFFSET,
        )
    )
