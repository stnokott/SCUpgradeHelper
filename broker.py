"""Contains broker classes for communicating data between APIs and the database"""
from logging import Logger
from typing import List

from config import ConfigProvider
from data.api import SCApi
from data.provider import (
    DataProviderManager,
    ShipDataProvider,
    OfficialUpgradeDataProvider,
    OfficialStandaloneDataProvider, DataProviderType, RedditDataProvider,
)
from data.scrape.submissionparser import ParsedRedditSubmissionEntry
from db.entity import Ship, Upgrade, UpdateType, EntityType, Standalone
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
                self._em.get_reddit_entities(),
                self._em.get_loaddate(UpdateType.REDDIT_ENTITIES),
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
        self._log_update(UpdateType.SHIPS)
        if updated or force:
            self._em.update_manufacturers([ship.manufacturer for ship in ships])
            self._em.update_ships(ships)

    def _update_rsi_standalones(self, force: bool = False, echo: bool = False) -> None:
        standalone_data_provider = self._data_provider_manager.get_data_provider(
            DataProviderType.RSI_STANDALONES
        )
        standalones, updated = standalone_data_provider.get_data(force, echo)
        self._log_update(UpdateType.RSI_STANDALONES)
        if updated or force:
            self._em.update_standalones(standalones)

    def _update_rsi_upgrades(self, force: bool = False, echo: bool = False) -> None:
        upgrade_data_provider = self._data_provider_manager.get_data_provider(
            DataProviderType.RSI_UPGRADES
        )
        upgrades, updated = upgrade_data_provider.get_data(force, echo)
        self._log_update(UpdateType.RSI_UPGRADES)
        if updated or force:
            self._em.update_upgrades(upgrades)

    def _update_reddit_entries(self, force: bool = False, echo: bool = False) -> None:
        reddit_data_provider = self._data_provider_manager.get_data_provider(
            DataProviderType.REDDIT_ENTRIES
        )
        entries: List[ParsedRedditSubmissionEntry]
        entries, updated = reddit_data_provider.get_data(force, echo)
        self._log_update(UpdateType.REDDIT_ENTITIES)
        if updated or force:
            standalones = []
            upgrades = []
            for entry in entries:
                if entry.entity_type == EntityType.STANDALONES:
                    ship_id = self._em.get_ship_id_by_name(entry.ship_name)
                    if ship_id is not None:
                        standalones.append(
                            Standalone(
                                price_usd=entry.price_usd,
                                store_name=entry.store_name,
                                ship_id=ship_id
                            )
                        )
                    else:
                        self._logger.debug(f"Ship name [{entry.ship_name}] could not be resolved!")
                elif entry.entity_type == EntityType.UPGRADES:
                    ship_id_from = self._em.get_ship_id_by_name(entry.ship_name_from)
                    ship_id_to = self._em.get_ship_id_by_name(entry.ship_name_to)
                    if ship_id_from is not None and ship_id_to is not None:
                        upgrades.append(
                            Upgrade(
                                price_usd=entry.price_usd,
                                store_name=entry.store_name,
                                ship_id_from=ship_id_from,
                                ship_id_to=ship_id_to
                            )
                        )
                    else:
                        unresolved_ship_names = []
                        if ship_id_from is None:
                            unresolved_ship_names.append(entry.ship_name_from)
                        if ship_id_to is None:
                            unresolved_ship_names.append(entry.ship_name_to)
                        self._logger.debug(
                            f"Ignored Reddit upgrade because ship name(s) [{', '.join(unresolved_ship_names)}] could not be resolved!")
            self._em.update_standalones(standalones)
            self._em.update_upgrades(upgrades)

    def _log_update(self, update_type: UpdateType) -> None:
        self._em.log_update(update_type)

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
