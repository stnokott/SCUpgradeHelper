"""Provides utility classes and functions"""
import logging
import shutil
from datetime import timedelta
from logging import Logger
from math import floor, ceil
from typing import Any

from colorama import init, Fore, Style, Back


def format_timedelta(delta: timedelta) -> str:
    """
    Create nicely formatted string from timedelta
    Args:
        delta: timedelta to process

    Returns:
        formatted string from timedelta
    """
    output_str = ""
    total_seconds = delta.total_seconds()
    if delta.days > 0:
        if delta.days > 2:
            return f"{delta.days} days"
        else:
            output_str += f"{delta.days} days, "
    total_seconds -= delta.days * 86400
    hours = str(round(total_seconds // 3600)).zfill(2)
    minutes = str(round((total_seconds % 3600) // 60)).zfill(2)
    seconds = str(round(total_seconds % 60)).zfill(2)

    output_str += f"{hours}:{minutes}:{seconds}"
    return output_str


init(strip=False)


class CustomLogger:
    LEVEL_DEBUG = logging.DEBUG
    LEVEL_INFO = logging.INFO
    LEVEL_WARN = logging.WARNING
    LEVEL_ERR = logging.ERROR

    def __init__(self, name: str, level: int = LEVEL_INFO):
        self._logger = Logger(name)
        self._logger.setLevel(level)
        self._logger.addHandler(logging.StreamHandler())

    def debug(self, s: Any):
        self._logger.debug(Fore.BLACK + str(s) + Style.RESET_ALL)

    def _header(self, s: str, level: int):
        s_len = len(s)
        console_width = shutil.get_terminal_size().columns
        padded_char_count_left = floor((console_width - s_len) / 2) - 1
        padded_char_count_right = ceil((console_width - s_len) / 2) - 1
        msg = f"{'#' * padded_char_count_left} {str(s)} {'#' * padded_char_count_right}"
        self._logger.log(level, Back.GREEN + Fore.BLACK + msg + Style.RESET_ALL)

    def header_start(self, s: Any, level: int):
        self._logger.log(level, "\n")
        self._header(str(s), level)

    def header_end(self, level: int):
        self._header("DONE", level)

    def success(self, s: Any, level: int):
        self._logger.log(level, Back.BLACK + Fore.GREEN + str(s) + Style.RESET_ALL)

    def failure(self, s: Any, level: int):
        self._logger.log(level, Back.BLACK + Fore.RED + str(s) + Style.RESET_ALL)

    def info(self, s: Any):
        self._logger.info(Back.BLACK + Fore.WHITE + str(s) + Style.RESET_ALL)

    def warning(self, s: Any):
        self._logger.warning(Back.YELLOW + Fore.BLACK + str(s) + Style.RESET_ALL)

    def error(self, s: Any):
        self._logger.error(Back.RED + Fore.WHITE + str(s) + Style.RESET_ALL)
