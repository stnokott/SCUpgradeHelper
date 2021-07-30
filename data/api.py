"""contains API classes"""
import json
from typing import List

import requests

from db.entity import Ship, Manufacturer
from util import CustomLogger


class SCApi:
    """
    Class to access endpoints exposed by https://starcitizen-api.com
    """

    __BASE_URL = "https://api.starcitizen-api.com"

    def __init__(self, api_key: str, logger: CustomLogger):
        self._api_key = api_key
        self._logger = logger

    def get_ships(self) -> List[Ship]:
        """
        Retrieve ships from official list using SC API
        Returns:
            list of ship entities
        """
        self._logger.header_start("RETRIEVING SHIP DATA", CustomLogger.LEVEL_INFO)
        self._logger.info("(this may take a while)")
        try:
            response = self._get("/ships")
            self._logger.header_end(CustomLogger.LEVEL_INFO)
            return self._ships_from_json(response)
        except RequestUnsuccessfulException as e:
            self._logger.warning(f"Unsuccessful request to ships endpoint: {e}")
            self._logger.header_end(CustomLogger.LEVEL_INFO)
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
            id=int(manufacturer_json["id"]), name=manufacturer_json["name"]
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


class RequestUnsuccessfulException(Exception):
    """
    Thrown if a HTTP request is unsuccessful
    """

    pass
