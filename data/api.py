"""contains API classes"""
from datetime import datetime, timedelta
import logging
from json.decoder import JSONDecodeError
import requests
from typing import List

from data.provider import DataProvider
from db.entity import Ship


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
    def _ships_from_json(cls, json: requests.models.Response) -> List[Ship]:
        ships = []
        for ship_json in json["data"]:
            if ship_json is not None:
                ships.append(cls._ship_from_json(ship_json))
        return ships

    @classmethod
    def _ship_from_json(cls, json: requests.models.Response):
        return Ship(name=json["name"], manufacturer="TODO")

    def _url(self, endpoint: str, use_cache: bool) -> str:
        return f"{self.__BASE_URL}/{self._api_key}/v1/{'cache' if use_cache else 'live'}{endpoint}"

    def _get(self, endpoint: str, use_cache: bool = True) -> requests.models.Response:
        request = requests.get(self._url(endpoint, use_cache))
        if request.status_code != 200:
            raise RequestUnsuccessfulException(f"Status code {request.status_code} received durin call to {endpoint}")
        try:
            response_json = request.json()
        except JSONDecodeError as e:
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
    __DATA_LIFETIME = timedelta(days=1)

    def __init__(self, scapi_instance: SCApi, logger: logging.Logger):
        super().__init__(self.__DATA_LIFETIME)
        self._scapi = scapi_instance
        self._logger = logger

    def update(self) -> bool:
        """
        Updates underlying ship data if expired
        Returns:
            True if update performed, False otherwise
        """
        if not self._is_data_expired():
            self._logger.debug("Ship data not expired, skipping update.")
            return False
        self._logger.debug("Ship data expired.")
        self._data = self._scapi.get_ships()
        self._last_fetched_datetime = datetime.now()
        return True


class RequestUnsuccessfulException(Exception):
    """
    Thrown if a HTTP request is unsuccessful
    """
    pass
