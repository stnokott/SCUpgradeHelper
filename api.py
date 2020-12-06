"""contains API classes"""
import requests
from typing import List

from db.entity import Ship


class SCApi:
    _BASE_URL = "http://api.starcitizen-api.com"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def get_ships(self) -> List[Ship]:
        try:
            print("Retrieving ship data...")
            response = self._get("/ships")
            print("Parsing ship data...")
            return self._ships_from_json(response)
        except RequestUnsuccessfulException as e:
            print(f"Unsuccessful request to ships endpoint: {e}")
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
        return f"{self._BASE_URL}/{self._api_key}/v1/{'cache' if use_cache else 'live'}{endpoint}"

    def _get(self, endpoint: str, use_cache: bool = True) -> requests.models.Response:
        response_json = requests.get(self._url(endpoint, use_cache)).json()
        if "success" not in response_json or "message" not in response_json:
            raise RequestUnsuccessfulException("Unknown error")
        if response_json["success"] != 1:
            raise RequestUnsuccessfulException(response_json["message"])
        if "data" not in response_json:
            raise RequestUnsuccessfulException("No data found")
        return response_json


class RequestUnsuccessfulException(Exception):
    pass
