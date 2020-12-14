"""Provides utility classes and functions"""


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
