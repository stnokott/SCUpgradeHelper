"""Contains broker classes for communicating data between APIs and the database"""
import datetime
from typing import List

from config import ConfigProvider
from data.api import SCApi
from data.provider import (
    DataProviderManager,
    ShipDataProvider,
    OfficialUpgradeDataProvider,
    OfficialStandaloneDataProvider,
    DataProviderType,
    RedditDataProvider,
)
from data.scraper.submissionparser import ParsedRedditSubmissionEntry
from db.entity import Ship, Upgrade, UpdateType, Standalone
from db.manager import EntityManager
from util import CustomLogger


class SCDataBroker:
    """
    Broker communicating between DB and APIs
    """

    def __init__(
        self, logger: CustomLogger, config: ConfigProvider, force_update: bool = False
    ):
        self._logger = logger
        self._em = EntityManager(logger)
        self._scapi = SCApi(config.sc_api_key, logger)
        self._data_provider_manager = DataProviderManager()
        ship_data_provider = ShipDataProvider(
            self._em.get_ships(), self._em.get_loaddate(UpdateType.SHIPS), logger
        )
        self._data_provider_manager.add_data_provider(
            DataProviderType.SHIPS,
            ship_data_provider,
        )
        self._data_provider_manager.add_data_provider(
            DataProviderType.RSI_STANDALONES,
            OfficialStandaloneDataProvider(
                self._em.get_rsi_standalones(),
                ship_data_provider,
                self._em.get_loaddate(UpdateType.RSI_STANDALONES),
                logger,
            ),
        )
        self._data_provider_manager.add_data_provider(
            DataProviderType.RSI_UPGRADES,
            OfficialUpgradeDataProvider(
                self._em.get_rsi_upgrades(),
                ship_data_provider,
                self._em.get_loaddate(UpdateType.RSI_UPGRADES),
                logger,
            ),
        )
        self._data_provider_manager.add_data_provider(
            DataProviderType.REDDIT_ENTRIES,
            RedditDataProvider(
                config.reddit_client_id,
                config.reddit_client_secret,
                self._em.get_reddit_standalones() + self._em.get_reddit_upgrades(),
                min(
                    self._em.get_loaddate(UpdateType.REDDIT_STANDALONES)
                    or datetime.datetime(1900, 1, 1),
                    self._em.get_loaddate(UpdateType.REDDIT_UPGRADES)
                    or datetime.datetime(1900, 1, 1),
                ),
                logger,
            ),
        )
        self.complete_update(force_update, True)

    def complete_update(self, force: bool = False, echo: bool = False) -> None:
        """
        Forces complete update of all underlying data.
        Very expensive operation, use sparingly!

        Args:
            force: True if forcing update
            echo: True if logging needed
        """
        self._update_ships(force, echo)
        self._update_rsi_standalones(force, echo)
        self._update_rsi_upgrades(force, echo)
        self._update_reddit_entries(force, echo)

    def _update_ships(self, force: bool = False, echo: bool = False) -> None:
        ship_data_provider = self._data_provider_manager.get_data_provider(
            DataProviderType.SHIPS
        )
        ships, updated = ship_data_provider.get_data(force, echo)
        if updated or force:
            self._em.update_manufacturers([ship.manufacturer for ship in ships])
            self._em.update_ships(ships)

    def _update_rsi_standalones(self, force: bool = False, echo: bool = False) -> None:
        standalone_data_provider = self._data_provider_manager.get_data_provider(
            DataProviderType.RSI_STANDALONES
        )
        standalones, updated = standalone_data_provider.get_data(force, echo)
        if updated or force:
            self._em.update_rsi_standalones(standalones)

    def _update_rsi_upgrades(self, force: bool = False, echo: bool = False) -> None:
        upgrade_data_provider = self._data_provider_manager.get_data_provider(
            DataProviderType.RSI_UPGRADES
        )
        upgrades, updated = upgrade_data_provider.get_data(force, echo)
        if updated or force:
            self._em.update_rsi_upgrades(upgrades)

    def _update_reddit_entries(self, force: bool = False, echo: bool = False) -> None:
        reddit_data_provider = self._data_provider_manager.get_data_provider(
            DataProviderType.REDDIT_ENTRIES
        )
        entries: List[ParsedRedditSubmissionEntry]
        entries, updated = reddit_data_provider.get_data(force, echo)
        if updated or force:
            standalones = []
            upgrades = []
            for entry in entries:
                if entry.update_type == UpdateType.REDDIT_STANDALONES:
                    ship_id = self._em.find_ship_id_by_name(entry.ship_name)
                    if ship_id is not None:
                        standalones.append(
                            Standalone(
                                price_usd=entry.price_usd,
                                store_name=entry.store_name,
                                ship_id=ship_id,
                            )
                        )
                elif entry.update_type == UpdateType.REDDIT_UPGRADES:
                    ship_id_from = self._em.find_ship_id_by_name(entry.ship_name_from)
                    ship_id_to = self._em.find_ship_id_by_name(entry.ship_name_to)
                    if ship_id_from is not None and ship_id_to is not None:
                        upgrades.append(
                            Upgrade(
                                price_usd=entry.price_usd,
                                store_name=entry.store_name,
                                ship_id_from=ship_id_from,
                                ship_id_to=ship_id_to,
                            )
                        )
            self._logger.info(
                f"{len(entries) - (len(standalones) + len(upgrades))} Reddit entries could not be resolved."
            )
            self._em.update_reddit_standalones(standalones)
            self._em.update_reddit_upgrades(upgrades)

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
        self._update_rsi_upgrades(force_update)
        return self._em.get_rsi_upgrades()
