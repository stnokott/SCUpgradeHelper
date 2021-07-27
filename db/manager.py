"""Manager for database entities"""
from datetime import datetime
from typing import List, Optional, Type, Union

from fuzzywuzzy import process, fuzz
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, configure_mappers, aliased
from sqlalchemy.sql.expression import func

from const import (
    DATABASE_FILEPATH,
    UPDATE_LOGS_ENTRY_LIMIT,
    RSI_SCRAPER_STORE_NAME,
    SHIP_DATA_EXPIRY,
    STANDALONE_DATA_EXPIRY,
    UPGRADE_DATA_EXPIRY,
    FUZZY_SEARCH_PERFECT_MATCH_MIN_SCORE,
    fuzzy_search_min_score,
)
from db.entity import (
    UpdateType,
    Ship,
    Base,
    Manufacturer,
    Upgrade,
    Standalone,
    UpdateLog,
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

    def _remove_stale_entities(
        self, entity_type: Union[Ship, Standalone, Upgrade]
    ) -> None:
        # TODO: find solution to differentiate between official and Reddit entries
        return
        now = datetime.now()
        if entity_type == Ship:
            query = self._session.query(Ship).where(
                now - Ship.loaddate > SHIP_DATA_EXPIRY
            )
        elif entity_type == Standalone:
            query = self._session.query(Standalone).where(
                now - Standalone.loaddate > STANDALONE_DATA_EXPIRY
            )
        elif entity_type == Upgrade:
            query = self._session.query(Upgrade).where(
                now - Upgrade.loaddate > UPGRADE_DATA_EXPIRY
            )
        else:
            self._logger.debug(
                f"Ignoring request to remove stale entities for type {entity_type}"
            )
            return
        deleted_count = 0
        for item in query:
            deleted_count += 1
            self._session.delete(item)
        self._logger.info(f"Deleting {deleted_count} stale entries for {entity_type}")
        self._session.commit()

    def _update_entities(
        self, entities: List[Union[Manufacturer, Ship, Standalone, Upgrade]]
    ) -> None:
        if len(entities) == 0:
            self._logger.warning(
                f">>> No entities passed to {self._update_entities.__name__}."
            )
            return

        entity_types = set([entity.__class__ for entity in entities])
        if len(entity_types) != 1:
            raise ValueError(f"Passed entities of more than one type: ({entity_types})")

        entity_type = entity_types.pop()
        entity_type_name = entity_type.__name__
        status = StatusString(f"PROCESSING {entity_type_name.upper()}S")
        self._logger.info(status.get_status_str())
        existing_entities = self._get_entities(entity_type)
        entities_set = set(entities)

        # delete invalid entities first
        self._remove_stale_entities(entity_type)

        # add new entities
        new_count = 0
        for entity in entities_set:
            if entity not in existing_entities:
                self._session.merge(entity)
                self._logger.debug(f">>> Adding {entity}.")
                new_count += 1
        if new_count > 0:
            self._logger.success(
                f">>> Added {new_count} new {entity_type_name}(s) to database.",
                CustomLogger.LEVEL_INFO,
            )
        else:
            self._logger.info(f">>> No new {entity_type_name}(s) detected.")

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
            return (
                self._session.query(Standalone)
                .filter_by(store_name=RSI_SCRAPER_STORE_NAME)
                .all()
            )
        elif entity_type == UpdateType.RSI_UPGRADES:
            return (
                self._session.query(Upgrade)
                .filter_by(store_name=RSI_SCRAPER_STORE_NAME)
                .all()
            )
        elif entity_type == UpdateType.REDDIT_ENTITIES:
            standalones = (
                self._session.query(Standalone)
                .filter(Standalone.store_name != RSI_SCRAPER_STORE_NAME)
                .all()
            )
            upgrades = (
                self._session.query(Upgrade)
                .filter(Upgrade.store_name != RSI_SCRAPER_STORE_NAME)
                .all()
            )
            return standalones + upgrades
        else:
            raise ValueError(f"Invalid update_type passed: {entity_type}")

    def update_manufacturers(self, manufacturers: List[Manufacturer]) -> None:
        """
        Inserts manufacturers into database, updates if existing
        Args:
            manufacturers: list of manufacturers to process
        """
        self._update_entities(manufacturers)

    def update_ships(self, ships: List[Ship]) -> None:
        """
        Inserts ships into database, updates if existing
        Args:
            ships: list of ships to process
        """
        self._update_entities(ships)

    def update_standalones(self, standalones: List[Standalone]):
        """
        Inserts standalones into database, updates if existing
        Args:
            standalones: list of standalones to process
        """
        self._update_entities(standalones)

    def update_upgrades(self, upgrades: List[Upgrade]) -> None:
        """
        Inserts upgrades into database, updates if existing
        Args:
            upgrades: list of upgrades to process
        """
        self._update_entities(upgrades)

    def log_update(self, update_type: UpdateType) -> None:
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

    def get_reddit_entities(self) -> List[Upgrade]:
        """
        Returns:
            All Reddit RSI upgrade entities in database
        """
        return self._get_entities(UpdateType.REDDIT_ENTITIES)

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
