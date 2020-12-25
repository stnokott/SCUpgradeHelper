"""Contains classes for scraping websites"""
import json
import logging
import re
from functools import reduce
from typing import List, Dict

import praw
import requests
from bs4 import BeautifulSoup
from praw.models import Submission
from requests import Session

from db.entity import Ship, Manufacturer, Upgrade, Standalone


class RedditScraper:
    """
    Class to scrape data from /r/starcitizen_trades
    """

    __SUBREDDIT_NAME = "starcitizen_trades"
    __SUBREDDIT_STORE_FLAIR_NAME = "store"
    __REDDIT_USER_AGENT = "python:scupgradehelper:v0.0.1 (by u/hibanabanana)"
    __USER_FLAIR_VALIDATOR = re.compile("^RSI \\S+, Trader, Trades: [1-9][0-9]*$")

    def __init__(self, client_id: str, client_secret: str, logger: logging.Logger):
        self._reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=self.__REDDIT_USER_AGENT,
        )
        self._subreddit = self._reddit.subreddit(self.__SUBREDDIT_NAME)
        self._logger = logger
        self._get_latest_store_posts()

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
        filtered_submissions = self._filter_unique_submissions(filtered_submissions)
        return filtered_submissions

    def _filter_good_submissions(self, submissions: List[Submission]) -> List[Submission]:
        """
        Filter submissions to follow certain guidelines such as a specific trader history
        Args:
            submissions: list of submissions to filter
        Returns:
            Filtered list of submissions
        """
        return list(
            filter(lambda s: s.author_flair_text is not None and self.__USER_FLAIR_VALIDATOR.match(s.author_flair_text),
                   submissions))

    @classmethod
    def _filter_unique_submissions(cls, submissions: List[Submission]) -> List[Submission]:
        """
        Filter submissions to only contain unique stores.
        Returns most recent store post if multiple from same author found.
        Args:
            submissions: list of submissions to filter
        Returns:
            Filtered list of submissions
        """
        filtered_submissions = {}  # dict with author names as keys and submissions as values
        for submission in submissions:
            author_name = submission.author.name
            if author_name not in filtered_submissions:
                filtered_submissions[author_name] = submission
            else:
                existing_submission = filtered_submissions[author_name]
                if max(submission.created, (submission.edited or -1.0)) > max(existing_submission.created,
                                                                            (existing_submission.edited or -1.0)):
                    filtered_submissions[author_name] = submission
        return list(filtered_submissions.values())


class RSIScraper:
    """
    Class to scrape data from official RSI page
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

    __STORE_NAME = "RSI"

    def __init__(self, logger: logging.Logger):
        self._logger = logger
        self._ships = None

    def get_ships(self) -> List[Ship]:
        """
        Retrieve ships from publicly exposed GraphQL json endpoint
        Returns:
            list of ships generated from json
        """
        self._logger.info("### REQUESTING SHIPS ###")
        ships = []
        response = requests.get(self.__SHIP_LIST_URL)
        # TODO: replace duplicate code
        if response.status_code != 200:
            self._logger.warning(
                f">>> Request to ship list endpoint {response.url} unsuccessful: {response.content}"
            )
        else:
            try:
                ships = [
                    self.ship_from_json(ship_json)
                    for ship_json in response.json()["data"]
                ]
            except KeyError as e:
                self._logger.warning(f">> Error occured while parsing ships json: {e}")
        self._logger.info(f">>> {len(ships)} ships retrieved from {self.__STORE_NAME}.")
        self._logger.info("########### DONE ###########")
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

    def create_standalones(
            self, ships: List[Ship], skus: Dict[str, float]
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
                    lambda sku_ship_name: ship.name in sku_ship_name,
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
            standalones.append(Standalone(ship_id=ship.id, price_usd=new_price, store_name=self.__STORE_NAME))
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
                "https://robertsspaceindustries.com/api/store/getSKUs",
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
                self._logger.warning(
                    f"Request to SKU endpoint {response.url} unsuccessful: {response.content}"
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
                self._logger.warning(f"Error occured while parsing sku json: {e}")
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
        self._logger.info("### REQUESTING UPGRADES ###")
        self._logger.info(f">>> {len(from_ships)} ships will be processed.")
        session = self.create_anon_authorized_session()
        upgrades = []
        for (i, ship) in enumerate(from_ships):
            if (i + 1) % 25 == 0:
                self._logger.info(
                    f">>> {round((i + 1) / len(from_ships) * 100, 2)}% processed."
                )
            upgrades += self.get_upgrades_by_ship_id(ship.id, session)
        self._logger.info(f">>> {len(upgrades)} upgrades found.")
        self._logger.info("############ DONE #########")
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
            self._logger.warning(
                f"Request to upgrades endpoint {response.url} unsuccessful: {response.content}"
            )
            return []
        try:
            upgrades = response.json()["data"]["to"]
            if upgrades is None or "ships" not in upgrades:
                return []
            return [
                self.upgrade_from_json(upgrade_json, ship_id)
                for upgrade_json in upgrades["ships"]
            ]
        except (KeyError, TypeError) as e:
            self._logger.warning(f"Error occured while parsing upgrades json: {e}")
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

    @classmethod
    def ship_from_json(cls, ship_json: json) -> Ship:
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

    @classmethod
    def upgrade_from_json(cls, upgrade_json: json, from_id: int) -> Upgrade:
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
            list(filter(lambda u: u["upgradePrice"] is not None, available_upgrades))
        )
        return Upgrade(
            ship_from_id=int(from_id),
            ship_to_id=int(upgrade_json["id"]),
            price_usd=float(int(cheapest_upgrade["upgradePrice"]) / 100),
            store_name=cls.__STORE_NAME,
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
