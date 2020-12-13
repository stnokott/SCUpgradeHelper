"""Contains classes for scraping websites"""
import json
import logging
from functools import reduce
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
from requests import Session

from db.entity import Ship, Manufacturer, Upgrade


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
                    self.ship_from_json(ship_json) for ship_json in response.json()["data"]
                ]
                available_skus = self.get_skus()
                return self.apply_skus_to_ships(ships, available_skus)
            except KeyError as e:
                self._logger.warning(f">> Error occured while parsing ships json: {e}")
        self._logger.info(f">>> {len(ships)} ships retrieved from {self.__STORE_NAME}.")
        self._logger.info("########### DONE ###########")
        return ships

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

    def apply_skus_to_ships(
        self, ships: List[Ship], skus: Dict[str, float]
    ) -> List[Ship]:
        """
        Overwrites ship prices with list of sku prices, if found in sku list
        Args:
            ships: list of ships to process
            skus: dict of skus to apply

        Returns:
            altered list of ships
        """
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
            if (
                ship.official_sku_price_usd is not None
                and ship.official_sku_price_usd != new_price
            ):
                self._logger.warning(
                    f"Price for {ship} overwritten (old: {ship.official_sku_price_usd}, new: {new_price}"
                )
            ship.official_sku_price_usd = new_price
        return ships

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
            if (i+1) % 25 == 0:
                self._logger.info(f">>> {round((i+1)/len(from_ships)*100, 2)}% processed.")
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
                "variables": {"fromFilters": [], "fromId": int(ship_id), "toFilters": []},
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
            return [self.upgrade_from_json(upgrade_json, ship_id) for upgrade_json in upgrades["ships"]]
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
            id=manufacturer_json["id"],
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
            available_upgrades,
        )
        return Upgrade(
            ship_from_id=from_id,
            ship_to_id=upgrade_json["id"],
            price_usd=int(cheapest_upgrade["upgradePrice"])/100,
            seller=cls.__STORE_NAME
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
