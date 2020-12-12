"""Contains classes for scraping websites"""
import logging
from typing import List

import requests

from db.entity import Ship, Manufacturer


class RSIScraper:
    __SHIP_LIST_URL = "https://robertsspaceindustries.com/ship-matrix/index"

    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def get_ships(self) -> List[Ship]:
        response = requests.get(self.__SHIP_LIST_URL)
        if response.status_code != 200:
            self._logger.warning(
                f"Request to ship endpoint {self.__SHIP_LIST_URL} unsuccessful: {response.content}"
            )
            return []
        try:
            ships_json = response.json()["data"]
            ships = []
            for ship_json in ships_json:
                manufacturer_json = ship_json["manufacturer"]
                manufacturer = Manufacturer(
                    id=manufacturer_json["id"],
                    name=manufacturer_json["name"],
                    code=manufacturer_json["code"],
                )
                ships.append(
                    Ship(
                        id=ship_json["id"],
                        name=ship_json["name"],
                        manufacturer_id=manufacturer.id,
                        manufacturer=manufacturer,
                    )
                )
            return ships
        except AttributeError as e:
            self._logger.warning(f"Error occured while parsing ships json: {e}")
            return []
