"""Contains classes for parsing Reddit submissions"""
import re
from abc import ABC, abstractmethod
from typing import Optional, List

from bs4 import BeautifulSoup
from praw.reddit import Submission

from db.entity import UpdateType
from util.const import REDDIT_PARSE_EXCLUDE_KEYWORDS
from util.helpers import CustomLogger


class NotParsableException(Exception):
    pass


class ParsedRedditSubmissionEntry:
    """
    Class providing data to create Purchasable entity.
    Names and such will need to be mapped to their corresponding entries in the database.
    """

    _REGEX_PRICE_MATCH = re.compile(r"\D?(?:\$\s?(\d[\d.,]*))|(?:(\d[\d.,]*)\s?\$)\D?")
    _REGEX_QUALIFY_SIMPLE_PARSE = re.compile(r"^\s*\d[\d.,]*\s*$")
    _REGEX_PARSE_PRICE_FLOAT = re.compile(r"[^\d.]")
    _REGEX_CHECK_PRICE_STR = re.compile(r"^\d+\D?\d*$")

    @classmethod
    def _parse_price_string(cls, price_string: str) -> Optional[float]:
        if "$" in price_string:
            regex_match = cls._REGEX_PRICE_MATCH.search(price_string)
            if regex_match is not None:
                match_str = regex_match.group(1) or regex_match.group(2)
                return float(match_str.replace(",", "."))
        else:
            # Do simple parse
            if cls._REGEX_QUALIFY_SIMPLE_PARSE.match(price_string) is None:
                return None
            parsed_string = re.sub(cls._REGEX_PARSE_PRICE_FLOAT, "", price_string)
            if (
                parsed_string.strip() != ""
                and cls._REGEX_CHECK_PRICE_STR.match(parsed_string) is not None
            ):
                return float(parsed_string)
            else:
                return None

    def __init__(self, *args, **kwargs):
        """
        ParsedSubmissionProxy(
            update_type,
            price_usd,
            store_owner,
            store_url
            [, ship_name = None]
            [, ship_name_from = None, ship_name_to = None]
        """
        self.update_type: UpdateType = args[0]
        parsed_price: Optional[float] = self._parse_price_string(args[1])
        if parsed_price is None:
            # could not be parsed
            raise NotParsableException(f"Price [{args[1]}] invalid")
        self.price_usd: float = parsed_price
        self.store_owner: str = args[2]
        self.store_url: str = args[3]
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
                if (
                    any(
                        qualifier in header_item.lower()
                        for qualifier in self._COL_QUALIFIERS_PRICE
                    )
                    and self.col_index_price is None
                ):
                    self.col_index_price = i
                elif (
                    any(
                        qualifier in header_item.lower()
                        for qualifier in self._COL_QUALIFIERS_SHIP_NAME_FROM
                    )
                    and self.col_index_ship_name_from is None
                ):
                    self.col_index_ship_name_from = i
                elif (
                    any(
                        qualifier in header_item.lower()
                        for qualifier in self._COL_QUALIFIERS_SHIP_NAME_TO
                    )
                    and self.col_index_ship_name_to is None
                ):
                    self.col_index_ship_name_to = i
                elif (
                    any(
                        qualifier in header_item.lower()
                        for qualifier in self._COL_QUALIFIERS_SHIP_NAME
                    )
                    and self.col_index_ship_name is None
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
                        if update_type == UpdateType.REDDIT_STANDALONES:
                            parsed_submissions.append(
                                ParsedRedditSubmissionEntry(
                                    update_type,
                                    price_usd,
                                    submission.author.name,
                                    submission.shortlink,
                                    ship_name=row[table_metadata.col_index_ship_name],
                                )
                            )
                        elif update_type == UpdateType.REDDIT_UPGRADES:
                            parsed_submissions.append(
                                ParsedRedditSubmissionEntry(
                                    update_type,
                                    price_usd,
                                    submission.author.name,
                                    submission.shortlink,
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
                    f"Table ignored: {'|'.join(table_header)} ({submission.shortlink})"
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
