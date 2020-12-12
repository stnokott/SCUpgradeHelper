"""contains API classes"""
import json
import logging
from datetime import datetime
from typing import List

import requests

from const import SHIP_DATA_EXPIRY
from data.provider import DataProvider
from db.entity import Ship, Manufacturer


class SCApi:
    """
    Class to access endpoints exposed by http://starcitizen-api.com
    """

    __BASE_URL = "http://api.starcitizen-api.com"

    def __init__(self, api_key: str, logger: logging.Logger):
        self._api_key = api_key
        self._logger = logger

    def get_ships(self) -> List[Ship]:
        """
        Retrieve ships from official list using SC API
        Returns:
            list of ship entities
        """
        self._logger.info("### RETRIEVING SHIP DATA ###")
        self._logger.info("(this may take a while)")
        try:
            response = self._get("/ships")
            self._logger.info("########### DONE ###########")
            return self._ships_from_json(response)
        except RequestUnsuccessfulException as e:
            self._logger.warning(f"Unsuccessful request to ships endpoint: {e}")
            self._logger.info("########### ERROR ##########")
            return []

    @classmethod
    def _ships_from_json(cls, ships_json: json) -> List[Ship]:
        ships = []
        for ships_json in ships_json["data"]:
            if ships_json is not None:
                ships.append(cls._ship_from_json(ships_json))
        return ships

    @classmethod
    def _ship_from_json(cls, ship_json: json):
        return Ship(
            name=ship_json["name"],
            manufacturer=cls._manufacturer_from_json(ship_json["manufacturer"]),
        )

    @classmethod
    def _manufacturer_from_json(cls, manufacturer_json: json):
        return Manufacturer(
            id=int(manufacturer_json["id"]),
            name=manufacturer_json["name"],
            code=manufacturer_json["code"],
        )

    def _url(self, endpoint: str, use_cache: bool) -> str:
        return f"{self.__BASE_URL}/{self._api_key}/v1/{'cache' if use_cache else 'live'}{endpoint}"

    def _get(self, endpoint: str, use_cache: bool = True) -> requests.models.Response:
        request = requests.get(self._url(endpoint, use_cache))
        if request.status_code != 200:
            raise RequestUnsuccessfulException(
                f"Status code {request.status_code} received durin call to {endpoint}"
            )
        try:
            response_json = request.json()
        except json.decoder.JSONDecodeError as e:
            raise RequestUnsuccessfulException(f"Error while decoding response: {e}")
        if "success" not in response_json or "message" not in response_json:
            raise RequestUnsuccessfulException("Unknown error")
        if response_json["success"] != 1:
            raise RequestUnsuccessfulException(response_json["message"])
        if "data" not in response_json:
            raise RequestUnsuccessfulException("No data found")
        return response_json


class ShipDataProvider(DataProvider):
    """
    Provides data about ships in concept, development or game
    """

    def __init__(
        self, scapi_instance: SCApi, last_loaded: datetime, logger: logging.Logger
    ):
        super().__init__(last_loaded, SHIP_DATA_EXPIRY)
        self._scapi = scapi_instance
        self._logger = logger
        from data.scraper import SCToolsScraper

        self._scraper = SCToolsScraper()

    def _refresh_data(self) -> None:
        """
        Updates underlying ship data
        """
        # self._data = self._scapi.get_ships()
        self._data = self._scraper.get_ships()
        self._update_expiry()


class RequestUnsuccessfulException(Exception):
    """
    Thrown if a HTTP request is unsuccessful
    """

    pass
