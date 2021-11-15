"""Contains broker classes for communicating data between APIs and the database"""
import datetime
from os import path
from typing import List, Optional

from config import ConfigProvider
from data.analyze import PathAnalyzer, UpgradePath, PurchasePath
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
from util.const import RSI_SCRAPER_STORE_URL, RSI_SCRAPER_STORE_OWNER, DATABASE_FILEPATH
from util.helpers import CustomLogger


class SCDataBroker:
    """
    Broker communicating between DB and APIs
    """

    def __init__(
        self, logger: CustomLogger, config: ConfigProvider, database_path=None
    ):
        self._logger = logger
        if database_path is None:
            database_dir = path.abspath(
                path.join(path.abspath(path.dirname(__file__)), "..")
            )
            self._em = EntityManager(logger, path.join(database_dir, DATABASE_FILEPATH))
        else:
            self._em = EntityManager(logger, database_path)
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
        self._path_analyzer = PathAnalyzer(self._em, self._logger)

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
        self._path_analyzer.update()

    def get_upgrade_path(
        self, ship_id_from: int, ship_id_to: int
    ) -> Optional[UpgradePath]:
        return self._path_analyzer.get_upgrade_path(ship_id_from, ship_id_to)

    def get_purchase_path(self, ship_id_to: int) -> Optional[PurchasePath]:
        return self._path_analyzer.get_purchase_path(ship_id_to)

    def _update_ships(self, force: bool = False, echo: bool = False) -> None:
        ship_data_provider = self._data_provider_manager.get_data_provider(
            DataProviderType.SHIPS
        )
        ships, updated = ship_data_provider.get_data(force, echo)
        if updated or force:
            self._em.update_manufacturers([ship.manufacturer for ship in ships])
            self._em.update_ships(ships)
            self._path_analyzer.update()

    def _update_rsi_standalones(self, force: bool = False, echo: bool = False) -> None:
        standalone_data_provider = self._data_provider_manager.get_data_provider(
            DataProviderType.RSI_STANDALONES
        )
        standalones, updated = standalone_data_provider.get_data(force, echo)
        if updated or force:
            store = self._em.find_store(RSI_SCRAPER_STORE_OWNER, RSI_SCRAPER_STORE_URL)
            for standalone in standalones:
                standalone.store = store
                standalone.store_id = store.id
            self._em.update_rsi_standalones(standalones)
            self._path_analyzer.update()

    def _update_rsi_upgrades(self, force: bool = False, echo: bool = False) -> None:
        upgrade_data_provider = self._data_provider_manager.get_data_provider(
            DataProviderType.RSI_UPGRADES
        )
        upgrades, updated = upgrade_data_provider.get_data(force, echo)
        if updated or force:
            store = self._em.find_store(RSI_SCRAPER_STORE_OWNER, RSI_SCRAPER_STORE_URL)
            for upgrade in upgrades:
                upgrade.store = store
                upgrade.store_id = store.id
            self._em.update_rsi_upgrades(upgrades)
            self._path_analyzer.update()

    def _update_reddit_entries(self, force: bool = False, echo: bool = False) -> None:
        reddit_data_provider = self._data_provider_manager.get_data_provider(
            DataProviderType.REDDIT_ENTRIES
        )
        entries: List[ParsedRedditSubmissionEntry]
        entries, updated = reddit_data_provider.get_data(force, echo)
        need_review_count_standalones = 0
        need_review_count_upgrades = 0
        if updated or force:
            standalones = []
            upgrades = []
            for entry in entries:
                store = self._em.find_store(entry.store_owner, entry.store_url)
                if entry.update_type == UpdateType.REDDIT_STANDALONES:
                    ship_id, needs_review = self._em.find_ship_id_by_name(
                        entry.ship_name
                    ) or (None, None)
                    if ship_id is not None:
                        if needs_review:
                            need_review_count_standalones += 1
                        standalones.append(
                            Standalone(
                                price_usd=entry.price_usd,
                                store=store,
                                store_id=store.id,
                                ship_id=ship_id,
                                needs_review=needs_review,
                            )
                        )
                elif entry.update_type == UpdateType.REDDIT_UPGRADES:
                    ship_id_from, needs_review_from = self._em.find_ship_id_by_name(
                        entry.ship_name_from
                    ) or (None, None)
                    ship_id_to, needs_review_to = self._em.find_ship_id_by_name(
                        entry.ship_name_to
                    ) or (None, None)
                    if ship_id_from is not None and ship_id_to is not None:
                        needs_review = any([needs_review_from, needs_review_to])
                        if needs_review:
                            need_review_count_upgrades += 1
                        upgrades.append(
                            Upgrade(
                                price_usd=entry.price_usd,
                                store=store,
                                store_id=store.id,
                                ship_id_from=ship_id_from,
                                ship_id_to=ship_id_to,
                                needs_review=needs_review,
                            )
                        )

            total_standalones = self._em.update_reddit_standalones(standalones)
            total_upgrades = self._em.update_reddit_upgrades(upgrades)

            self._logger.info(
                f"{len(entries) - (len(standalones) + len(upgrades))} Reddit entries could not be resolved."
            )

            if need_review_count_standalones > 0 and total_standalones > 0:
                self._logger.warning(
                    f"{need_review_count_standalones} Reddit standalones need to be checked manually."
                )
            if need_review_count_upgrades > 0 and total_upgrades > 0:
                self._logger.warning(
                    f"{need_review_count_upgrades} Reddit upgrades need to be checked manually."
                )
            self._path_analyzer.update()

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
