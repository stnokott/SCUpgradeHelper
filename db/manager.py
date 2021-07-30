"""Manager for database entities"""
from datetime import datetime
from typing import List, Optional, Type, Union

from fuzzywuzzy import process, fuzz
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, configure_mappers, Query
from sqlalchemy.sql.expression import func, or_

from const import (
    DATABASE_FILEPATH,
    UPDATE_LOGS_ENTRY_LIMIT,
    RSI_SCRAPER_STORE_OWNER,
    SHIP_DATA_EXPIRY,
    RSI_STANDALONE_DATA_EXPIRY,
    RSI_UPGRADE_DATA_EXPIRY,
    FUZZY_SEARCH_PERFECT_MATCH_MIN_SCORE,
    fuzzy_search_min_score,
    REDDIT_DATA_EXPIRY,
)
from db.entity import (
    UpdateType,
    Ship,
    Base,
    Manufacturer,
    Upgrade,
    Standalone,
    UpdateLog,
    Store,
)
from util import StatusString, CustomLogger


class EntityManager:
    """
    Manages the application's database and its entities
    """

    def __init__(self, logger: CustomLogger):
        self._engine = create_engine(f"sqlite:///{DATABASE_FILEPATH}", echo=False)
        configure_mappers()
        self._session = Session(bind=self._engine, expire_on_commit=False)
        self._logger = logger
        self._prepare_database()
        self._clean_update_logs()

    def _prepare_database(self):
        self._logger.debug("Applying database schemata...")
        Base.metadata.create_all(self._engine)

    def _clean_update_logs(self):
        """
        Cleans all entries in update log table except for newest to save space
        """
        self._logger.debug(f"Checking {UpdateLog.__name__} entry count...")
        log_count = self._session.query(UpdateLog).count()
        if not log_count > UPDATE_LOGS_ENTRY_LIMIT:
            self._logger.debug("Limit not exceeded, no cleanup necessary.")
            return

        self._logger.debug(">>> Limit exceeded, cleaning entries...")
        for update_type in UpdateType:
            max_loaddate_query = self._session.query(
                func.max(UpdateLog.loaddate)
            ).filter_by(data_type=update_type)
            self._session.query(UpdateLog).filter(
                UpdateLog.update_type == update_type,
                UpdateLog.loaddate.notin_(max_loaddate_query),
            ).delete()
        self._session.commit()

    def _query_rsi_standalones(self) -> Query:
        return self._session.query(Standalone).filter(
            Standalone.store.has(Store.username == RSI_SCRAPER_STORE_OWNER)
        )

    def _query_rsi_upgrades(self) -> Query:
        return self._session.query(Upgrade).filter(
            Upgrade.store.has(Store.username == RSI_SCRAPER_STORE_OWNER)
        )

    def _query_reddit_standalones(self) -> Query:
        return self._session.query(Standalone).filter(
            or_(
                Standalone.store.has(Store.url.ilike("%reddit.com%")),
                Standalone.store.has(Store.url.ilike("%redd.it%")),
            )
        )

    def _query_reddit_upgrades(self) -> Query:
        return self._session.query(Upgrade).filter(
            or_(
                Upgrade.store.has(Store.url.ilike("%reddit.com%")),
                Upgrade.store.has(Store.url.ilike("%redd.it%")),
            )
        )

    def _remove_stale_entities(self, update_type: UpdateType) -> None:
        now = datetime.now()
        deletion = []
        if update_type == UpdateType.SHIPS:
            ships: List[Ship] = self._session.query(Ship).all()
            deletion = [
                ship for ship in ships if now - ship.loaddate > SHIP_DATA_EXPIRY
            ]
        elif update_type == UpdateType.RSI_STANDALONES:
            standalones: List[Standalone] = self._session.query(Standalone).all()
            deletion = [
                standalone
                for standalone in standalones
                if now - standalone.loaddate > RSI_STANDALONE_DATA_EXPIRY
            ]
        elif update_type == UpdateType.RSI_UPGRADES:
            upgrades = self._query_rsi_upgrades().all()
            deletion = [
                upgrade
                for upgrade in upgrades
                if now - upgrade.loaddate > RSI_UPGRADE_DATA_EXPIRY
            ]
        elif update_type == UpdateType.REDDIT_STANDALONES:
            standalones = self._query_reddit_standalones().all()
            deletion = [
                standalone
                for standalone in standalones
                if now - standalone.loaddate > REDDIT_DATA_EXPIRY
            ]
        elif update_type == UpdateType.REDDIT_UPGRADES:
            upgrades = self._query_reddit_upgrades().all()
            deletion = [
                upgrade
                for upgrade in upgrades
                if now - upgrade.loaddate > REDDIT_DATA_EXPIRY
            ]
        else:
            self._logger.debug(
                f"Ignoring request to remove stale entities for type {update_type}"
            )
            return
        for item in deletion:
            self._session.delete(item)
        self._logger.info(f"Deleting {len(deletion)} stale entries for {update_type}")
        self._session.commit()

    def find_store(self, username: str, url: str) -> Store:
        """
        Find store by username and URL. Create one if not found.
        :param username: username of store owner
        :type username: string
        :param url: Reddit URL of store
        :type url: string
        :return: Store instance
        :rtype: Store
        """
        store = self._session.query(Store).filter_by(username=username, url=url).first()
        if store is None:
            store = Store(username=username, url=url)
            self._session.add(store)
            self._session.flush()
            self._logger.debug(f"Created new store {store}.")
        return store

    def _update_entities(
        self,
        entities: List[Union[Manufacturer, Ship, Standalone, Upgrade]],
        update_type: UpdateType,
    ) -> None:
        if len(entities) == 0:
            self._logger.warning(
                f">>> No entities passed to {self._update_entities.__name__}."
            )
            return

        update_type_name: str = update_type.value
        status = StatusString(f"PROCESSING {update_type_name.upper()}")
        self._logger.info(status.get_status_str())
        existing_entities = self._get_entities(update_type)
        entities_set = set(entities)

        # delete invalid entities first
        self._remove_stale_entities(update_type)

        # add new entities
        new_count = 0
        for entity in entities_set:
            if entity not in existing_entities:
                self._session.merge(entity)
                self._logger.debug(f">>> Adding {entity}.")
                new_count += 1
        if new_count > 0:
            self._logger.success(
                f">>> Added {new_count} new {update_type_name}(s) to database.",
                CustomLogger.LEVEL_INFO,
            )
        else:
            self._logger.info(f">>> No new {update_type_name}(s) detected.")

        self._session.commit()
        self._logger.info(status.get_status_done_str())

    def _get_entities(
        self, entity_type: Union[UpdateType, Type[Base]]
    ) -> List[Type[Base]]:
        if entity_type in (UpdateType.MANUFACTURERS, Manufacturer):
            return self._session.query(Manufacturer).all()
        elif entity_type in (UpdateType.SHIPS, Ship):
            return self._session.query(Ship).all()
        elif entity_type == Standalone:
            return self._session.query(Standalone).all()
        elif entity_type == Upgrade:
            return self._session.query(Upgrade).all()
        elif entity_type == UpdateType.RSI_STANDALONES:
            return self._query_rsi_standalones().all()
        elif entity_type == UpdateType.RSI_UPGRADES:
            return self._query_rsi_upgrades().all()
        elif entity_type == UpdateType.REDDIT_STANDALONES:
            return self._query_reddit_standalones().all()
        elif entity_type == UpdateType.REDDIT_UPGRADES:
            return self._query_reddit_upgrades().all()
        else:
            raise ValueError(f"Invalid update_type passed: {entity_type}")

    def update_manufacturers(self, manufacturers: List[Manufacturer]) -> None:
        """
        Inserts manufacturers into database, updates if existing
        Args:
            manufacturers: list of manufacturers to process
        """
        self._update_entities(manufacturers, UpdateType.MANUFACTURERS)
        self._log_update(UpdateType.MANUFACTURERS)

    def update_ships(self, ships: List[Ship]) -> None:
        """
        Inserts ships into database, updates if existing
        Args:
            ships: list of ships to process
        """
        self._update_entities(ships, UpdateType.SHIPS)
        self._log_update(UpdateType.SHIPS)

    def update_rsi_standalones(self, standalones: List[Standalone]):
        """
        Inserts standalones into database, updates if existing
        Args:
            standalones: list of standalones to process
        """
        self._update_entities(standalones, UpdateType.RSI_STANDALONES)
        self._log_update(UpdateType.RSI_STANDALONES)

    def update_rsi_upgrades(self, upgrades: List[Upgrade]) -> None:
        """
        Inserts upgrades into database, updates if existing
        Args:
            upgrades: list of upgrades to process
        """
        self._update_entities(upgrades, UpdateType.RSI_UPGRADES)
        self._log_update(UpdateType.RSI_UPGRADES)

    def update_reddit_standalones(self, standalones: List[Standalone]):
        """
        Inserts standalones into database, updates if existing
        Args:
            standalones: list of standalones to process
        """
        self._update_entities(standalones, UpdateType.REDDIT_STANDALONES)
        self._log_update(UpdateType.REDDIT_STANDALONES)

    def update_reddit_upgrades(self, upgrades: List[Upgrade]) -> None:
        """
        Inserts upgrades into database, updates if existing
        Args:
            upgrades: list of upgrades to process
        """
        self._update_entities(upgrades, UpdateType.REDDIT_UPGRADES)
        self._log_update(UpdateType.REDDIT_UPGRADES)

    def _log_update(self, update_type: UpdateType) -> None:
        """
        Insert entry in log table
        Args:
            update_type: data provider type which got updated
        """
        self._session.add(UpdateLog(update_type=update_type, loaddate=datetime.now()))
        self._session.commit()

    def get_manufacturers(self) -> List[Manufacturer]:
        """
        Returns:
            All manufacturer entities in database
        """
        return self._get_entities(UpdateType.MANUFACTURERS)

    def get_ships(self) -> List[Ship]:
        """
        Returns:
            All ship entities in database
        """
        return self._get_entities(UpdateType.SHIPS)

    def find_ship_id_by_name(self, name: str) -> Optional[int]:
        ships: List[Ship] = self._session.query(Ship).all()
        if ships is None or len(ships) == 0 or name == "" or name == '"':
            return None

        candidate_sets = [
            [ship.name for ship in ships],
            [f"{ship.manufacturer.name} {ship.name}" for ship in ships],
        ]  # try with base ship name and with manufacturer if no match found

        for candidate_set in candidate_sets:
            results = process.extract(
                name,
                candidate_set,
                scorer=fuzz.token_set_ratio,
                limit=3,
            )
            max_score = max([result[1] for result in results])
            best_candidates = list(filter(lambda c: c[1] == max_score, results))
            best_candidates.sort(key=lambda c: len(c[0]), reverse=True)
            result = best_candidates[0]

            if result is not None and result[1] >= fuzzy_search_min_score(
                min(len(name), len(result[0]))
            ):
                ship_id = self._get_ship_id_by_name(result[0])
                if ship_id is not None:
                    if result[1] < FUZZY_SEARCH_PERFECT_MATCH_MIN_SCORE:
                        self._logger.warning(
                            f"Match [{name}] -> [{result[0]}] needs to be reviewed (score {result[1]}/100)."
                        )
                    else:
                        self._logger.success(
                            f"Mapped [{name}] -> [{result[0]}] (score {result[1]}/100).",
                            CustomLogger.LEVEL_DEBUG,
                        )
                    return ship_id
        self._logger.failure(
            f"Ship name [{name}] could not be resolved to entry in database!",
            CustomLogger.LEVEL_DEBUG,
        )
        return None

    def _get_ship_id_by_name(self, s: str):
        result = self._session.query(Ship).where(Ship.name == s).first()
        if result is not None:
            return result.id
        else:
            return None

    def get_rsi_standalones(self) -> List[Standalone]:
        """
        Returns:
            All official RSI standalone entities in database
        """
        return self._get_entities(UpdateType.RSI_STANDALONES)

    def get_rsi_upgrades(self) -> List[Upgrade]:
        """
        Returns:
            All officlal RSI upgrade entities in database
        """
        return self._get_entities(UpdateType.RSI_UPGRADES)

    def get_reddit_standalones(self) -> List[Standalone]:
        """
        Returns:
            All Reddit RSI upgrade entities in database
        """
        return self._get_entities(UpdateType.REDDIT_STANDALONES)

    def get_reddit_upgrades(self) -> List[Upgrade]:
        """
        Returns:
            All Reddit RSI upgrade entities in database
        """
        return self._get_entities(UpdateType.REDDIT_UPGRADES)

    def get_loaddate(self, update_type: UpdateType) -> Optional[datetime]:
        """
        Get latest update date for specified data type
        Args:
            update_type: data type to query
        Returns:
            smallest datetime or None if none found
        """
        result = (
            self._session.query(func.max(UpdateLog.loaddate))
            .filter_by(update_type=update_type)
            .first()
        )
        if result is None:
            return None
        return result[0]

    def __del__(self):
        self._session.close()
        self._engine.dispose()
