"""Contains broker classes for communicating data between APIs and the database"""
from logging import Logger
from typing import List

from config import ConfigProvider
from const import SUPPRESS_ALL_LOGGING_FILTER
from data.api import SCApi, ShipDataProvider
from data.provider import DataProviderManager, DataProviderType
from db.entity import Ship
from db.util import EntityManager


class SCDataBroker:
    """
    Broker communicating between DB and APIs
    """
    def __init__(self, logger: Logger, config: ConfigProvider):
        self._logger = logger
        self._scapi = SCApi(config.sc_api_key, logger)
        self._data_provider_manager = DataProviderManager()
        self._data_provider_manager.add_data_provider(DataProviderType.SHIPS, ShipDataProvider(self._scapi, logger))
        self._em = EntityManager(logger)
        self._update_ships(True)

    def _update_ships(self, drop: bool = False) -> None:
        ship_data_provider = self._data_provider_manager.get_data_provider(DataProviderType.SHIPS)
        if ship_data_provider.data_expiry.is_expired():
            self._logger.info("Ship data expired, updating...")
            ships = ship_data_provider.get_data(True)
            self._em.update_ships(ships, drop)
        else:
            self._logger.info(f"Ship data up-to-date until {ship_data_provider.data_expiry.expiry_date()}")

    def get_ships(self) -> List[Ship]:
        """
        Get ships from database after updating expired API data
        Returns:
            list of ships
        """
        self._logger.addFilter(SUPPRESS_ALL_LOGGING_FILTER)
        self._update_ships()
        self._logger.removeFilter(SUPPRESS_ALL_LOGGING_FILTER)
        return self._em.get_ships()
