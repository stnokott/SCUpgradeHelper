"""Manager for database entities"""
from datetime import datetime
from typing import List, Optional, Type, Union, Tuple

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
from util import CustomLogger


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

    def _query_reddit_items(
        self,
        entity_type: Union[Type[Standalone], Type[Upgrade]],
        include_unconfirmed: bool,
    ):
        query = self._session.query(entity_type).filter(
            or_(
                entity_type.store.has(Store.url.ilike("%reddit.com%")),
                entity_type.store.has(Store.url.ilike("%redd.it%")),
            )
        )
        if not include_unconfirmed:
            query = query.filter_by(needs_review=False)
        return query

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
            standalones = self._query_reddit_items(Standalone, True).all()
            deletion = [
                standalone
                for standalone in standalones
                if now - standalone.loaddate > REDDIT_DATA_EXPIRY
            ]
        elif update_type == UpdateType.REDDIT_UPGRADES:
            upgrades = self._query_reddit_items(Upgrade, True).all()
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

        self._session.commit()

        deleted_count = len(deletion)
        if deleted_count > 0:
            self._logger.info(
                f"Deleted {deleted_count} stale entries for {update_type.value}"
            )

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
            self._logger.success(f"Found {store}.", CustomLogger.LEVEL_INFO)
        return store

    def _entity_exists(
        self, entity: Union[Manufacturer, Ship, Store, Standalone, Upgrade]
    ):
        query: Optional[Query] = None
        if type(entity) == Manufacturer:
            entity: Manufacturer
            query = self._session.query(Manufacturer).filter_by(name=entity.name)
        elif type(entity) == Ship:
            entity: Ship
            query = self._session.query(Ship).filter_by(name=entity.name)
        elif type(entity) == Store:
            entity: Store
            query = self._session.query(Store).filter_by(url=entity.url)
        elif type(entity) == Standalone:
            entity: Standalone
            query = self._session.query(Standalone).filter_by(
                price_usd=entity.price_usd,
                store_id=entity.store_id,
                ship_id=entity.ship_id,
            )
        elif type(entity) == Upgrade:
            entity: Upgrade
            query = self._session.query(Upgrade).filter_by(
                price_usd=entity.price_usd,
                store_id=entity.store_id,
                ship_id_from=entity.ship_id_from,
                ship_id_to=entity.ship_id_to,
            )
        else:
            raise ValueError(
                f"{self._entity_exists.__name__} can't handle entities of type {type(entity)}!"
            )
        return query.first() is not None

    def _update_entities(
        self,
        entities: List[Union[Manufacturer, Ship, Standalone, Upgrade]],
        update_type: UpdateType,
    ) -> int:
        if len(entities) == 0:
            self._logger.warning(
                f">>> No entities passed to {self._update_entities.__name__}."
            )
            return 0

        update_type_name: str = update_type.value
        self._logger.header_start(
            f"PROCESSING {update_type_name.upper()}", CustomLogger.LEVEL_INFO
        )
        existing_entities = self._get_entities(update_type)
        entities_set = set(entities)

        # delete stale entities first (older than expiry dates defined in const.py)
        self._remove_stale_entities(update_type)

        # remove entries that are currently existing
        cleaned_entities = [
            entity for entity in entities_set if not self._entity_exists(entity)
        ]
        cleaned_count = len(entities_set) - len(cleaned_entities)

        # add or merge entities
        total_count = 0
        for entity in cleaned_entities:
            if entity not in existing_entities:
                self._session.merge(entity)
                self._logger.debug(f">>> Adding/updating {entity}.")
                total_count += 1
        if total_count > 0:
            self._logger.success(
                f">>> Added or updated {total_count} {update_type_name}(s).",
                CustomLogger.LEVEL_INFO,
            )
        else:
            self._logger.info(f">>> No new {update_type_name}(s) detected.")

        if cleaned_count > 0:
            self._logger.info(
                f">>> {cleaned_count} already existing entries were ignored."
            )

        self._session.commit()
        self._logger.header_end(CustomLogger.LEVEL_INFO)
        return total_count

    def _get_entities(
        self, update_type: Union[UpdateType, Type[Base]], **kwargs
    ) -> List[Type[Base]]:
        include_unconfirmed: bool = kwargs.get("include_unconfirmed", True)
        if update_type in (UpdateType.MANUFACTURERS, Manufacturer):
            return self._session.query(Manufacturer).all()
        elif update_type in (UpdateType.SHIPS, Ship):
            return self._session.query(Ship).all()
        elif update_type == Standalone:
            return self._session.query(Standalone).all()
        elif update_type == Upgrade:
            return self._session.query(Upgrade).all()
        elif update_type == UpdateType.RSI_STANDALONES:
            return self._query_rsi_standalones().all()
        elif update_type == UpdateType.RSI_UPGRADES:
            return self._query_rsi_upgrades().all()
        elif update_type == UpdateType.REDDIT_STANDALONES:
            return self._query_reddit_items(Standalone, include_unconfirmed).all()
        elif update_type == UpdateType.REDDIT_UPGRADES:
            return self._query_reddit_items(Upgrade, include_unconfirmed).all()
        else:
            raise ValueError(f"Invalid update_type passed: {update_type}")

    def update_manufacturers(self, manufacturers: List[Manufacturer]) -> int:
        """
        Inserts manufacturers into database, updates if existing
        Args:
            manufacturers: list of manufacturers to process
        """
        updated_count = self._update_entities(manufacturers, UpdateType.MANUFACTURERS)
        self._log_update(UpdateType.MANUFACTURERS)
        return updated_count

    def update_ships(self, ships: List[Ship]) -> int:
        """
        Inserts ships into database, updates if existing
        Args:
            ships: list of ships to process
        """
        updated_count = self._update_entities(ships, UpdateType.SHIPS)
        self._log_update(UpdateType.SHIPS)
        return updated_count

    def update_rsi_standalones(self, standalones: List[Standalone]) -> int:
        """
        Inserts standalones into database, updates if existing
        Args:
            standalones: list of standalones to process
        """
        updated_count = self._update_entities(standalones, UpdateType.RSI_STANDALONES)
        self._log_update(UpdateType.RSI_STANDALONES)
        return updated_count

    def update_rsi_upgrades(self, upgrades: List[Upgrade]) -> int:
        """
        Inserts upgrades into database, updates if existing
        Args:
            upgrades: list of upgrades to process
        """
        updated_count = self._update_entities(upgrades, UpdateType.RSI_UPGRADES)
        self._log_update(UpdateType.RSI_UPGRADES)
        return updated_count

    def update_reddit_standalones(self, standalones: List[Standalone]) -> int:
        """
        Inserts standalones into database, updates if existing
        Args:
            standalones: list of standalones to process
        """
        updated_count = self._update_entities(
            standalones, UpdateType.REDDIT_STANDALONES
        )
        self._log_update(UpdateType.REDDIT_STANDALONES)
        return updated_count

    def update_reddit_upgrades(self, upgrades: List[Upgrade]) -> int:
        """
        Inserts upgrades into database, updates if existing
        Args:
            upgrades: list of upgrades to process
        """
        updated_count = self._update_entities(upgrades, UpdateType.REDDIT_UPGRADES)
        self._log_update(UpdateType.REDDIT_UPGRADES)
        return updated_count

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

    def find_ship_id_by_name(self, name: str) -> Optional[Tuple[int, bool]]:
        """
        Tries to find ship in database using fuzzy search.
        Returns ship id and `needs_review`-flag if found, else None
        :param name: Name of ship
        :type name: string
        :return: ship id and `needsreview` flag or None if not found
        :rtype: Optional[Tuple[int, bool]]
        """
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
                        return ship_id, True
                    else:
                        self._logger.success(
                            f"Mapped [{name}] -> [{result[0]}] (score {result[1]}/100).",
                            CustomLogger.LEVEL_DEBUG,
                        )
                        return ship_id, False
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

    def get_reddit_standalones(
        self, include_unconfirmed: bool = True
    ) -> List[Standalone]:
        """
        :param include_unconfirmed: Whether to include entries that still need review
        :type include_unconfirmed: bool

        Returns:
            All Reddit RSI upgrade entities in database, optionally filtered by `needs_review`
        """
        return self._get_entities(
            UpdateType.REDDIT_STANDALONES, include_unconfirmed=include_unconfirmed
        )

    def get_reddit_upgrades(self, include_unconfirmed: bool = True) -> List[Upgrade]:
        """
        :param include_unconfirmed: Whether to include entries that still need review
        :type include_unconfirmed: bool

        Returns:
            All Reddit RSI upgrade entities in database, optionally filtered by `needs_review`
        """
        return self._get_entities(
            UpdateType.REDDIT_UPGRADES, include_unconfirmed=include_unconfirmed
        )

    def get_all_standalones(self, include_unconfirmed: bool = True) -> List[Standalone]:
        return self.get_rsi_standalones() + self.get_reddit_standalones(
            include_unconfirmed
        )

    def get_all_upgrades(self, include_unconfirmed: bool = True) -> List[Upgrade]:
        return self.get_rsi_upgrades() + self.get_reddit_upgrades(include_unconfirmed)

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
