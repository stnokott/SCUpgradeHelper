"""Provides utility classes and functions"""
from datetime import timedelta


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
