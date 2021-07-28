"""Contains classes for parsing Reddit submissions"""
from abc import ABC, abstractmethod

from bs4 import BeautifulSoup
from typing import Optional, List

from praw.reddit import Submission

from const import REDDIT_PARSE_EXCLUDE_KEYWORDS
from db.entity import UpdateType
from util import CustomLogger


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
        self.update_type: UpdateType = args[0]
        # remove non-numeric characters from price string
        numeric_filter = filter(str.isdigit, args[1])
        fixed_price_string = "".join(numeric_filter)
        if len(fixed_price_string) == 0:
            raise NotParsableException(f"Price [{args[1]}] invalid")
        self.price_usd: float = float(fixed_price_string)
        self.store_name: str = args[2]
        self.ship_name: Optional[str] = kwargs.get("ship_name") or None
        self.ship_name_from: Optional[str] = kwargs.get("ship_name_from") or None
        self.ship_name_to: Optional[str] = kwargs.get("ship_name_to") or None
        for name in [self.ship_name, self.ship_name_from, self.ship_name_to]:
            if name is not None and any(
                key.lower() in name.lower() for key in REDDIT_PARSE_EXCLUDE_KEYWORDS
            ):
                raise NotParsableException(f"[{name}] contains exclude keyword")
        if self.update_type == UpdateType.REDDIT_UPGRADES and (
            self.ship_name_from is None or self.ship_name_to is None
        ):
            raise ValueError(
                f"Trying to instantiate {self.__class__} of type UPGRADE without ship name from/to!"
            )
        elif (
            self.update_type == UpdateType.REDDIT_STANDALONES and self.ship_name is None
        ):
            raise ValueError(
                f"Trying to instantiate {self.__class__} of type STANDALONE without ship name!"
            )


class _GenericSubmissionParser(ABC):
    def __init__(self, logger: CustomLogger):
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

        def __init__(self, header: List[str], logger: CustomLogger):
            self.valid = False
            self.type: Optional[UpdateType] = None
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
                self.type = UpdateType.REDDIT_UPGRADES
            elif self.col_index_ship_name is not None:
                self.type = UpdateType.REDDIT_STANDALONES

            if self.type is None or self.col_index_price is None:
                logger.debug(f"Could not completely map columns {'|'.join(header)}")
            else:
                self.valid = True

    def __init__(self, logger: CustomLogger):
        super().__init__(logger)

    def parse(self, submission: Submission) -> List[ParsedRedditSubmissionEntry]:
        html = submission.selftext_html
        soup = BeautifulSoup(html, "html.parser")
        parsed_submissions = []
        for table_tag in soup.select("table"):
            table_header = [tag.text for tag in table_tag.select("thead > tr > th")]
            table_metadata = self._TableMetadata(table_header, self._logger)
            if table_metadata.valid:
                table_content = []
                table_body = table_tag.select_one("tbody")
                # html to python-readable
                for row in table_body.select("tr"):
                    cols = row.select("td")
                    cols = [ele.text.strip() for ele in cols]
                    table_content.append([ele for ele in cols if ele])

                for row in table_content:
                    update_type = table_metadata.type
                    try:
                        price_usd = row[table_metadata.col_index_price]
                        store_name = "Reddit"
                        # TODO: parse store name
                        # TODO: parse manufacturer name
                        if update_type == UpdateType.REDDIT_STANDALONES:
                            parsed_submissions.append(
                                ParsedRedditSubmissionEntry(
                                    update_type,
                                    price_usd,
                                    store_name,
                                    ship_name=row[table_metadata.col_index_ship_name],
                                )
                            )
                        elif update_type == UpdateType.REDDIT_UPGRADES:
                            parsed_submissions.append(
                                ParsedRedditSubmissionEntry(
                                    update_type,
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
                        self._logger.debug(f"Entry ignored, reason: {e}")
            else:
                self._logger.debug(
                    f"Table ignored: {'|'.join(table_header)} ({submission.permalink})"
                )
        return parsed_submissions


class SubmissionParsingSuite:
    _parsers: List[_GenericSubmissionParser]

    def __init__(self, logger: CustomLogger):
        self._logger = logger
        self._parsers = [_HTMLTableParser(self._logger)]

    def parse(self, submission: Submission) -> List[ParsedRedditSubmissionEntry]:
        items = []
        for parser in self._parsers:
            items += parser.parse(submission)

        return items
