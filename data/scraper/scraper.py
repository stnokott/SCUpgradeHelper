"""Contains classes for scraping websites"""
import json
import re
from functools import reduce
from typing import List, Dict

import praw
import requests
from bs4 import BeautifulSoup
from praw.models import Submission
from requests import Session

from const import RSI_SCRAPER_STORE_OWNER
from data.scraper.submissionparser import (
    SubmissionParsingSuite,
    ParsedRedditSubmissionEntry,
)
from db.entity import Ship, Manufacturer, Upgrade, Standalone
from util import CustomLogger


class RedditScraper:
    """
    Class to scraper data from /r/starcitizen_trades
    """

    __SUBREDDIT_NAME = "starcitizen_trades"
    __SUBREDDIT_STORE_FLAIR_NAME = "store"
    __REDDIT_USER_AGENT = "python:scupgradehelper:v0.0.1 (by u/hibanabanana)"
    __USER_FLAIR_VALIDATOR = re.compile("^RSI \\S+, Trader, Trades: [1-9][0-9]*$")

    def __init__(self, client_id: str, client_secret: str, logger: CustomLogger):
        self._reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=self.__REDDIT_USER_AGENT,
        )
        self._subreddit = self._reddit.subreddit(self.__SUBREDDIT_NAME)
        self._logger = logger
        self._submission_parser = SubmissionParsingSuite(self._logger)

    def get_parsed_submissions(self) -> List[ParsedRedditSubmissionEntry]:
        submissions = self._get_latest_store_posts()
        items = []
        for submission in submissions:
            items += self._submission_parser.parse(submission)
        return items

    def _get_latest_store_posts(self) -> List[Submission]:
        """
        Retrieve submissions in subreddit matching appropriate flair, upvote ratio and trader reputation
        Returns:
            list of submissions matching filters
        """
        submissions = self._subreddit.search(
            f"flair:'{self.__SUBREDDIT_STORE_FLAIR_NAME}'",
            sort="new",
            limit=10,
        )
        filtered_submissions = self._filter_good_submissions(submissions)
        return filtered_submissions

    def _filter_good_submissions(
        self, submissions: List[Submission]
    ) -> List[Submission]:
        """
        Filter submissions to follow certain guidelines such as a specific trader history
        Args:
            submissions: list of submissions to filter
        Returns:
            Filtered list of submissions
        """
        return list(
            filter(
                lambda s: s.author_flair_text is not None
                and self.__USER_FLAIR_VALIDATOR.match(s.author_flair_text),
                submissions,
            )
        )


class RSIScraper:
    """
    Class to scraper data from official RSI page
    """

    __SHIP_LIST_URL = "https://robertsspaceindustries.com/ship-matrix/index"
    __SET_CURRENCY_URL = "https://robertsspaceindustries.com/api/store/setCurrency"
    __SKU_LIST_URL = "https://robertsspaceindustries.com/api/store/getSKUs"
    __UPGRADES_URL = "https://robertsspaceindustries.com/pledge-store/api/upgrade"

    __SET_AUTH_TOKEN_URL = (
        "https://robertsspaceindustries.com/api/account/v2/setAuthToken"
    )
    __SET_CONTEXT_TOKEN_URL = (
        "https://robertsspaceindustries.com/api/ship-upgrades/setContextToken"
    )

    def __init__(self, logger: CustomLogger):
        self._logger = logger
        self._ships = None

    def get_ships(self) -> List[Ship]:
        """
        Retrieve ships from publicly exposed GraphQL json endpoint
        Returns:
            list of ships generated from json
        """
        self._logger.header_start("REQUESTING OFFICIAL SHIPS", CustomLogger.LEVEL_INFO)
        ships = []
        response = requests.get(self.__SHIP_LIST_URL)
        # TODO: replace duplicate code
        if response.status_code != 200:
            self._logger.failure(
                f">>> Request to ship list endpoint {response.url} unsuccessful: {response.content}",
                CustomLogger.LEVEL_WARN,
            )
        else:
            try:
                ships = [
                    self.ship_from_json(ship_json)
                    for ship_json in response.json()["data"]
                ]
            except KeyError as e:
                self._logger.failure(
                    f">> Error occured while parsing ships json: {e}",
                    CustomLogger.LEVEL_WARN,
                )
        self._logger.success(
            f">>> {len(ships)} ships retrieved from {RSI_SCRAPER_STORE_OWNER}.",
            CustomLogger.LEVEL_WARN,
        )
        self._logger.header_end(CustomLogger.LEVEL_INFO)
        self._ships = ships
        return ships

    def get_standalones(self, ships: List[Ship]) -> List[Standalone]:
        """
        Retrieve official RSI standalone ship purchases
        Args:
            ships: ship list to associate ship names

        Returns:
            list of standalones
        """
        return self.create_standalones(ships, self.get_skus())

    @staticmethod
    def create_standalones(
        ships: List[Ship], skus: Dict[str, float]
    ) -> List[Standalone]:
        """
        Overwrites ship prices with list of sku prices, if found in sku list
        Args:
            ships: list of ships to process
            skus: dict of skus to apply

        Returns:
            altered list of ships
        """
        standalones = []
        sku_ship_names = skus.keys()
        for ship in ships:
            # find fitting sku candidates
            sku_candidates = list(
                filter(
                    lambda sku_ship_name, s=ship: s.name in sku_ship_name,
                    sku_ship_names,
                )
            )
            if len(sku_candidates) == 0:
                continue
            # reduce to one with smallest price
            sku_name = reduce(
                (lambda sku1, sku2: sku1 if skus[sku1] < skus[sku2] else sku2),
                sku_candidates,
            )
            new_price = skus[sku_name]
            standalones.append(
                Standalone(
                    ship_id=ship.id,
                    price_usd=new_price,
                )
            )
        return standalones

    def get_skus(self) -> Dict[str, float]:
        """
        Get available official skus
        Returns:
            dictionary of (ship name -> price (USD)
        """
        rows_fetched = 0
        total_rows = 999999
        current_page = 1
        skus = {}
        self.set_currency_usd()
        # TODO: taxes?
        while rows_fetched < total_rows:
            response = requests.post(
                self.__SKU_LIST_URL,
                data={
                    "itemType": "skus",
                    "page": current_page,
                    "product_id": 72,
                    "search": "",
                    "sort": "store",
                    "storefront": "pledge",
                    "type": "extras",
                },
            )
            if response.status_code != 200:
                self._logger.failure(
                    f"Request to SKU endpoint {response.url} unsuccessful: {response.content}",
                    CustomLogger.LEVEL_WARN,
                )
                return skus
            try:
                sku_json = response.json()["data"]
                total_rows = sku_json["totalrows"]
                if sku_json["rowcount"] == 0:
                    # last page reachd
                    return skus
                html = sku_json["html"]
                soup = BeautifulSoup(html, "html.parser")
                for info_tag in soup.select(".products-listing .product-item .info"):
                    name = info_tag.select_one(".title").get_text().strip()
                    price_usd = info_tag.select_one(".price .final-price").get(
                        "data-value"
                    )
                    price_usd = int(price_usd) / 100
                    skus[name] = price_usd
                rows_fetched += sku_json["rowcount"]
                current_page += 1
            except KeyError as e:
                self._logger.failure(
                    f"Error occured while parsing sku json: {e}",
                    CustomLogger.LEVEL_WARN,
                )
                return skus
        return skus

    def get_upgrades(self, from_ships: List[Ship]) -> List[Upgrade]:
        """
        Gets all upgrades for all provided ships available on the official RSI store
        Args:
            from_ships: list of ships for which upgrades need to be retrieved

        Returns:
            list of upgrades for all ships provided
        """
        self._logger.header_start(
            "REQUESTING OFFICIAL UPGRADE", CustomLogger.LEVEL_INFO
        )
        self._logger.info(f">>> Base of {len(from_ships)} ships will be used.")
        session = self.create_anon_authorized_session()
        upgrades = []
        for (i, ship) in enumerate(from_ships):
            if (i + 1) % 25 == 0:
                self._logger.info(
                    f">>> {round((i + 1) / len(from_ships) * 100, 2)}% processed."
                )
            upgrades += self.get_upgrades_by_ship_id(ship.id, session)
        self._logger.success(
            f">>> {len(upgrades)} upgrades found.", CustomLogger.LEVEL_INFO
        )
        self._logger.header_end(CustomLogger.LEVEL_INFO)
        return upgrades

    def get_upgrades_by_ship_id(self, ship_id: int, session: Session) -> List[Upgrade]:
        """
        Retrieve available upgrades on official RSI store by ship ID
        Args:
            ship_id: id of ship the available upgrades are to be retrieved for
            session: session object with all necessary cookies set, see create_anon_authorized_session()

        Returns:
            list of upgrades for this ship
        """
        response = session.post(
            self.__UPGRADES_URL,
            json={
                "operationName": "filterShips",
                "variables": {
                    "fromFilters": [],
                    "fromId": int(ship_id),
                    "toFilters": [],
                },
                "query": QUERY_FILTER_SHIPS,
            },
        )
        if response.status_code != 200:
            self._logger.failure(
                f"Request to upgrades endpoint {response.url} unsuccessful: {response.content}",
                CustomLogger.LEVEL_WARN,
            )
            return []
        try:
            upgrades = response.json()["data"]["to"]
            if upgrades is None or "ships" not in upgrades:
                self._logger.failure(
                    f"Invalid response for upgrades for upgrades from ship_id={ship_id}, ignoring.",
                    CustomLogger.LEVEL_WARN,
                )
                return []
            return [
                self.upgrade_from_json(upgrade_json, ship_id)
                for upgrade_json in upgrades["ships"]
            ]
        except (KeyError, TypeError) as e:
            self._logger.failure(
                f"Error occured while parsing upgrades json: {e}",
                CustomLogger.LEVEL_DEBUG,
            )
            return []

    def set_currency_usd(self):
        """
        Sets current session currency in RSI store to USD
        """
        requests.post(self.__SET_CURRENCY_URL, data={"currency": "USD"})

    @classmethod
    def create_anon_authorized_session(cls) -> requests.Session:
        """
        Initialize new anonymous RSI session, setting all relevant cookies in the process
        Returns:
            New session object with auth cookies set
        """
        session = requests.Session()
        session.post(cls.__SET_AUTH_TOKEN_URL)
        session.post(cls.__SET_CONTEXT_TOKEN_URL, data={})
        return session

    @staticmethod
    def ship_from_json(ship_json: json) -> Ship:
        """
        Create ship instance from RSI-formatted json
        Args:
            ship_json: ship json to parse. Needs to include id, name and manufacturer data

        Returns:
            Ship instance
        """
        manufacturer_json = ship_json["manufacturer"]
        manufacturer = Manufacturer(
            id=int(manufacturer_json["id"]),
            name=manufacturer_json["name"],
            code=manufacturer_json["code"],
        )
        return Ship(
            id=ship_json["id"],
            name=ship_json["name"],
            manufacturer_id=manufacturer.id,
            manufacturer=manufacturer,
        )

    @staticmethod
    def upgrade_from_json(upgrade_json: json, from_id: int) -> Upgrade:
        """
        Create Upgrade instance from RSI json
        Args:
            upgrade_json: json to parse
            from_id: RSI ship id this upgrade can be applied onto

        Returns:
            Upgrade instance representing database entity
        """
        available_upgrades = upgrade_json["skus"]
        cheapest_upgrade = reduce(
            (
                lambda upgr1, upgr2: upgr1
                if upgr1["upgradePrice"] < upgr2["upgradePrice"]
                else upgr2
            ),
            list(filter(lambda u: u["upgradePrice"] is not None, available_upgrades)),
        )
        return Upgrade(
            ship_id_from=int(from_id),
            ship_id_to=int(upgrade_json["id"]),
            price_usd=float(int(cheapest_upgrade["upgradePrice"]) / 100),
        )


QUERY_FILTER_SHIPS = (
    "query filterShips($fromId: Int, $toId: Int, $fromFilters: [FilterConstraintValues],"
    "$toFilters: [FilterConstraintValues]) {"
    "from(to: $toId, filters: $fromFilters) {"
    "    ships {"
    "      id"
    "    }"
    "  }"
    "  to(from: $fromId, filters: $toFilters) {"
    "    ships {"
    "      id"
    "      skus {"
    "        id"
    "        price"
    "        upgradePrice"
    "      }"
    "    }"
    "  }"
    "}"
)
