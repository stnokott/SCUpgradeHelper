"""Contains classes for parsing Reddit submissions"""
import logging
from abc import ABC, abstractmethod
from logging import Logger

from bs4 import BeautifulSoup
from typing import Optional, List

from praw.reddit import Submission

from db.entity import Purchasable, EntityType


class _GenericSubmissionParser(ABC):
    def __init__(self, logger: logging.Logger):
        self._logger = logger

    @abstractmethod
    def parse(self, submission: Submission) -> Purchasable:
        pass


class _HTMLTableParser(_GenericSubmissionParser):
    class _TableMetadata:
        __COL_QUALIFIERS_IGNORE = ["pack"]
        __COL_QUALIFIERS_PRICE = ["price", "$", "€"]
        __COL_QUALIFIERS_SHIP_NAME_FROM = ["from"]
        __COL_QUALIFIERS_SHIP_NAME_TO = ["to"]
        __COL_QUALIFIERS_SHIP_NAME = ["name", "ship", "item", "sale"]

        def __init__(self, header: List[str], logger: logging.Logger):
            self.valid = False
            self.type: Optional[EntityType] = None
            self.col_index_price: Optional[int] = None
            self.col_index_ship_name_from: Optional[int] = None
            self.col_index_ship_name_to: Optional[int] = None
            self.col_index_ship_name: Optional[int] = None
            # Check for ignore wildcards first
            if any(qualifier in ''.join(header).lower() for qualifier in self.__COL_QUALIFIERS_IGNORE):
                logger.debug(f"Ignoring table based on qualifiers {'|'.join(header)}")
                return
            for i, header_item in enumerate(header):
                if any(qualifier in header_item.lower() for qualifier in self.__COL_QUALIFIERS_PRICE):
                    self.col_index_price = i
                elif any(qualifier in header_item.lower() for qualifier in self.__COL_QUALIFIERS_SHIP_NAME_FROM):
                    self.col_index_ship_name_from = i
                elif any(qualifier in header_item.lower() for qualifier in self.__COL_QUALIFIERS_SHIP_NAME_TO):
                    self.col_index_ship_name_to = i
                elif any(qualifier in header_item.lower() for qualifier in self.__COL_QUALIFIERS_SHIP_NAME):
                    self.col_index_ship_name = i
            if self.col_index_ship_name_from is not None and self.col_index_ship_name_to is not None:
                self.type = EntityType.UPGRADES
            elif self.col_index_ship_name is not None:
                self.type = EntityType.STANDALONES
            if self.type is None or self.col_index_price is None:
                logger.debug(f"Could not completely map columns {'|'.join(header)}")
            else:
                self.valid = True

    def __init__(self, logger: logging.Logger):
        super().__init__(logger)

    def parse(self, submission: Submission) -> Optional[Purchasable]:
        html = submission.selftext_html
        soup = BeautifulSoup(html, "html.parser")
        for table_tag in soup.select("table"):
            table_header = [tag.text for tag in table_tag.select("thead > tr > th")]
            table_metadata = self._TableMetadata(table_header, self._logger)
            if table_metadata.valid:
                self._logger.debug(f"Found qualifying table: {'|'.join(table_header)}")
                table_content = []
                table_body = table_tag.select_one("tbody")
                for row in table_body.select("tr"):
                    cols = row.select("td")
                    cols = [ele.text.strip() for ele in cols]
                    table_content.append([ele for ele in cols if ele])
            else:
                self._logger.debug(f"Table ignored: {'|'.join(table_header)}")
        return None


class SubmissionParsingSuite:
    _parsers: List[_GenericSubmissionParser]

    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self._parsers = [_HTMLTableParser(self._logger)]

    def parse(self, submission: Submission) -> Optional[Purchasable]:
        for parser in self._parsers:
            result = parser.parse(submission)
            if result is not None:
                return result
        self._logger.warning(
            f"Could not find suitable parsing solution for {submission.permalink}"
        )
        return None
