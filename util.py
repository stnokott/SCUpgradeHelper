"""Provides utility classes and functions"""
import enum
import logging
from datetime import timedelta
from logging import Logger
from typing import Union

from colorama import init, Fore, Style, Back


class StatusString:
    """
    Provides status strings for logging
    """
    __DONE_STR = "DONE"

    def __init__(self, status: str):
        self.__status = status

    def get_status_str(self) -> str:
        """
        Returns:
            status string
        """
        return f"### {self.__status} ###"

    def get_status_done_str(self) -> str:
        """
        Returns:
            status done string
        """
        if len(self.__status) < 4:
            return f"### {self.__DONE_STR} ###"
        surrounding_hashs = round((len(self.__status) - len(self.__DONE_STR)) / 2) * "#"
        return f"###{surrounding_hashs} {self.__DONE_STR} {surrounding_hashs}###"


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

    def debug(self, s: str):
        self._logger.debug(s)

    def header(self, s: str, level: int):
        self._logger.log(level, Back.GREEN + Fore.BLACK + s + Style.RESET_ALL)

    def success(self, s: str, level: int):
        self._logger.log(level, Back.WHITE + Fore.GREEN + s + Style.RESET_ALL)

    def failure(self, s: str, level: int):
        self._logger.log(level, Back.WHITE + Fore.RED + s + Style.RESET_ALL)

    def info(self, s: str):
        self._logger.info(Fore.GREEN + s + Style.RESET_ALL)

    def warning(self, s: str):
        self._logger.warning(Back.YELLOW + Fore.BLACK + s + Style.RESET_ALL)

    def error(self, s: str):
        self._logger.error(Back.RED + Fore.WHITE + s + Style.RESET_ALL)