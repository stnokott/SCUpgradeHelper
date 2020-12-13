"""Contains classes for scraping websites"""
import json
import logging
from functools import reduce
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

from db.entity import Ship, Manufacturer


class RSIScraper:
    """
    Class to scrape data from official RSI page
    """

    __SHIP_LIST_URL = "https://robertsspaceindustries.com/ship-matrix/index"
    __SET_CURRENCY_URL = "https://robertsspaceindustries.com/api/store/setCurrency"
    __SKU_LIST_URL = "https://robertsspaceindustries.com/api/store/getSKUs"

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def get_ships(self) -> List[Ship]:
        """
        Retrieve ships from publicly exposed GraphQL json endpoint
        Returns:
            list of ships generated from json
        """
        response = requests.get(self.__SHIP_LIST_URL)
        if response.status_code != 200:
            self._logger.warning(
                f"Request to ship list endpoint {self.__SHIP_LIST_URL} unsuccessful: {response.content}"
            )
            return []
        try:
            ships = [
                self.ship_from_json(ship_json) for ship_json in response.json()["data"]
            ]
            available_skus = self.get_skus()
            return self.apply_skus_to_ships(ships, available_skus)

        except KeyError as e:
            self._logger.warning(f"Error occured while parsing ships json: {e}")
            return []

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
                    f"Request to SKU endpoint {self.__SKU_LIST_URL} unsuccessful: {response.content}"
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

    def set_currency_usd(self):
        """
        Sets current session currency in RSI store to USD
        """
        requests.post(self.__SET_CURRENCY_URL, data={"currency": "USD"})

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

    def apply_skus_to_ships(self, ships: List[Ship], skus: Dict[str, float]) -> List[Ship]:
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
            sku_name = reduce((lambda sku1, sku2: sku1 if skus[sku1] < skus[sku2] else sku2), sku_candidates)
            new_price = skus[sku_name]
            if ship.official_sku_price_usd is not None and ship.official_sku_price_usd != new_price:
                self._logger.warning(f"Price for {ship} overwritten (old: {ship.official_sku_price_usd}, new: {new_price}")
            ship.official_sku_price_usd = new_price
        return ships
