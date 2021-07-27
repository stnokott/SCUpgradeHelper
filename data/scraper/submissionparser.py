"""Contains classes for parsing Reddit submissions"""
import logging
from abc import ABC, abstractmethod

from bs4 import BeautifulSoup
from typing import Optional, List

from praw.reddit import Submission

from const import MAX_SHIP_NAME_LENGTH
from db.entity import EntityType


class NotParsableException(Exception):
    pass


class ParsedRedditSubmissionEntry:
    """
    Class providing data to create Purchasable entity.
    Names and such will need to be mapped to their corresponding entries in the database.
    """

    def __init__(self, *args, **kwargs):
        """
        ParsedSubmissionProxy(entity_type, price_usd[, ship_name = None][, ship_name_from = None, ship_name_to = None]
        """
        self.entity_type: EntityType = args[0]
        # remove non-numeric characters from price string
        numeric_filter = filter(str.isdigit, args[1])
        fixed_price_string = "".join(numeric_filter)
        if len(fixed_price_string) == 0:
            raise NotParsableException(f"Passed price [{args[1]}] not valid.")
        self.price_usd: float = float(fixed_price_string)
        self.store_name: str = args[2]
        self.ship_name: Optional[str] = kwargs.get("ship_name") or None
        if self.ship_name is not None and len(self.ship_name) > MAX_SHIP_NAME_LENGTH:
            raise NotParsableException(
                f"Name {self.ship_name} too long, unlikely to be ship"
            )
        self.ship_name_from: Optional[str] = kwargs.get("ship_name_from") or None
        self.ship_name_to: Optional[str] = kwargs.get("ship_name_to") or None
        if self.entity_type == EntityType.UPGRADES and (
            self.ship_name_from is None or self.ship_name_to is None
        ):
            raise ValueError(
                f"Trying to instantiate {self.__class__} of type UPGRADE without ship name from/to!"
            )
        elif self.entity_type == EntityType.STANDALONES and self.ship_name is None:
            raise ValueError(
                f"Trying to instantiate {self.__class__} of type STANDALONE without ship name!"
            )


class _GenericSubmissionParser(ABC):
    def __init__(self, logger: logging.Logger):
        self._logger = logger

    @abstractmethod
    def parse(
        self, submission: Submission
    ) -> Optional[List[ParsedRedditSubmissionEntry]]:
        pass


class _HTMLTableParser(_GenericSubmissionParser):
    class _TableMetadata:
        _COL_QUALIFIERS_IGNORE = ["pack"]
        _COL_QUALIFIERS_PRICE = ["price", "$", "cost"]
        _COL_QUALIFIERS_SHIP_NAME_FROM = ["from"]
        _COL_QUALIFIERS_SHIP_NAME_TO = ["to"]
        _COL_QUALIFIERS_SHIP_NAME = ["name", "ship", "item", "sale"]

        def __init__(self, header: List[str], logger: logging.Logger):
            self.valid = False
            self.type: Optional[EntityType] = None
            self.col_index_price: Optional[int] = None
            self.col_index_ship_name_from: Optional[int] = None
            self.col_index_ship_name_to: Optional[int] = None
            self.col_index_ship_name: Optional[int] = None

            # Check for ignore wildcards first
            if any(
                qualifier in "".join(header).lower()
                for qualifier in self._COL_QUALIFIERS_IGNORE
            ):
                logger.debug(f"Ignoring table based on qualifiers {'|'.join(header)}")
                return

            for i, header_item in enumerate(header):
                if any(
                    qualifier in header_item.lower()
                    for qualifier in self._COL_QUALIFIERS_PRICE
                ):
                    self.col_index_price = i
                elif any(
                    qualifier in header_item.lower()
                    for qualifier in self._COL_QUALIFIERS_SHIP_NAME_FROM
                ):
                    self.col_index_ship_name_from = i
                elif any(
                    qualifier in header_item.lower()
                    for qualifier in self._COL_QUALIFIERS_SHIP_NAME_TO
                ):
                    self.col_index_ship_name_to = i
                elif any(
                    qualifier in header_item.lower()
                    for qualifier in self._COL_QUALIFIERS_SHIP_NAME
                ):
                    self.col_index_ship_name = i

            if (
                self.col_index_ship_name_from is not None
                and self.col_index_ship_name_to is not None
            ):
                self.type = EntityType.UPGRADES
            elif self.col_index_ship_name is not None:
                self.type = EntityType.STANDALONES

            if self.type is None or self.col_index_price is None:
                logger.debug(f"Could not completely map columns {'|'.join(header)}")
            else:
                self.valid = True

    def __init__(self, logger: logging.Logger):
        super().__init__(logger)

    def parse(self, submission: Submission) -> List[ParsedRedditSubmissionEntry]:
        html = submission.selftext_html
        soup = BeautifulSoup(html, "html.parser")
        parsed_submissions = []
        for table_tag in soup.select("table"):
            table_header = [tag.text for tag in table_tag.select("thead > tr > th")]
            table_metadata = self._TableMetadata(table_header, self._logger)
            if table_metadata.valid:
                self._logger.debug(f"Found qualifying table: {'|'.join(table_header)}")
                table_content = []
                table_body = table_tag.select_one("tbody")
                # html to python-readable
                for row in table_body.select("tr"):
                    cols = row.select("td")
                    cols = [ele.text.strip() for ele in cols]
                    table_content.append([ele for ele in cols if ele])

                for row in table_content:
                    entity_type = table_metadata.type
                    try:
                        price_usd = row[table_metadata.col_index_price]
                        store_name = "Reddit"
                        # TODO: parse store name
                        if entity_type == EntityType.STANDALONES:
                            parsed_submissions.append(
                                ParsedRedditSubmissionEntry(
                                    entity_type,
                                    price_usd,
                                    store_name,
                                    ship_name=row[table_metadata.col_index_ship_name],
                                )
                            )
                        elif entity_type == EntityType.UPGRADES:
                            parsed_submissions.append(
                                ParsedRedditSubmissionEntry(
                                    entity_type,
                                    price_usd,
                                    store_name,
                                    ship_name_from=row[
                                        table_metadata.col_index_ship_name_from
                                    ],
                                    ship_name_to=row[
                                        table_metadata.col_index_ship_name_to
                                    ],
                                )
                            )
                    except IndexError:
                        # Some rows might be used as headers and can thus be ignored
                        pass
                    except NotParsableException as e:
                        self._logger.warning(e)
            else:
                self._logger.debug(
                    f"Table ignored: {'|'.join(table_header)} ({submission.permalink})"
                )
        return parsed_submissions


class SubmissionParsingSuite:
    _parsers: List[_GenericSubmissionParser]

    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self._parsers = [_HTMLTableParser(self._logger)]

    def parse(self, submission: Submission) -> List[ParsedRedditSubmissionEntry]:
        items = []
        for parser in self._parsers:
            items += parser.parse(submission)

        return items
