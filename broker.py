"""Contains broker classes for communicating data between APIs and the database"""
from logging import Logger
from typing import List

from config import ConfigProvider
from data.api import SCApi
from data.provider import (
    DataProviderManager,
    DataProviderType,
    ShipDataProvider,
    UpgradeDataProvider,
)
from db.entity import Ship, Upgrade
from db.manager import EntityManager


class SCDataBroker:
    """
    Broker communicating between DB and APIs
    """

    def __init__(
        self, logger: Logger, config: ConfigProvider, force_update: bool = False
    ):
        self._logger = logger
        self._em = EntityManager(logger)
        self._scapi = SCApi(config.sc_api_key, logger)
        self._data_provider_manager = DataProviderManager()
        ship_data_provider = ShipDataProvider(
            self._em.get_ships(), self._em.get_ships_loaddate(), logger
        )
        self._data_provider_manager.add_data_provider(
            DataProviderType.SHIPS,
            ship_data_provider,
        )
        self._data_provider_manager.add_data_provider(
            DataProviderType.UPGRADES,
            UpgradeDataProvider(
                self._em.get_upgrades(),
                ship_data_provider,
                self._em.get_upgrades_loaddate(),
                logger,
            ),
        )
        self._update_ships(force_update, True)
        self._update_upgrades(force_update, True)

    def force_complete_update(self) -> None:
        """
        Forces complete update of all underlying data.
        Very expensive operation, use sparingly!
        """
        self._update_ships(force=True, echo=True)
        self._update_upgrades(force=True, echo=True)

    def _update_ships(self, force: bool = False, echo: bool = False) -> None:
        ship_data_provider = self._data_provider_manager.get_data_provider(
            DataProviderType.SHIPS
        )
        ships, updated = ship_data_provider.get_data(force, echo)
        if updated or force:
            self._em.update_manufacturers([ship.manufacturer for ship in ships])
            self._em.update_ships(ships)

    def _update_upgrades(self, force: bool = False, echo: bool = False) -> None:
        upgrade_data_provider = self._data_provider_manager.get_data_provider(
            DataProviderType.UPGRADES
        )
        upgrades, updated = upgrade_data_provider.get_data(force, echo)
        if updated or force:
            self._em.update_upgrades(upgrades)

    def get_ships(self, force_update: bool = False) -> List[Ship]:
        """
        Get ships from database after updating expired API data
        Args:
            force_update: set to True to force update of underlying data

        Returns:
            list of ships
        """
        self._update_ships(force_update)
        return self._em.get_ships()

    def get_upgrades(self, force_update: bool = False) -> List[Upgrade]:
        """
        Get upgrades from database after updating expired API data
        Args:
            force_update: set to True to force update of underlying data

        Returns:
            list of upgrades
        """
        self._update_upgrades(force_update)
        return self._em.get_upgrades()
