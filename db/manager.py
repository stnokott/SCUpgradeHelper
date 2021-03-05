"""Manager for database entities"""

import logging
from datetime import datetime
from typing import List, Optional, Type

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from const import DATABASE_FILEPATH, UPDATE_LOGS_ENTRY_LIMIT
from data.provider import EntityType
from db.entity import Ship, Base, Manufacturer, Upgrade, Standalone, UpdateLog
from util import StatusString


class EntityManager:
    """
    Manages the application's database and its entities
    """

    def __init__(self, logger: logging.Logger):
        self._engine = create_engine(f"sqlite:///{DATABASE_FILEPATH}", echo=False)
        self._session = Session(bind=self._engine, expire_on_commit=False)
        self._logger = logger
        self._create_schema()
        self._clean_update_logs()

    def _create_schema(self):
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
        for data_type in EntityType:
            max_loaddate_query = self._session.query(func.max(UpdateLog.loaddate)).filter_by(data_type=data_type)
            self._session.query(UpdateLog).filter(
                UpdateLog.data_type == data_type,
                UpdateLog.loaddate.notin_(max_loaddate_query)
            ).delete()
        self._session.commit()

    def _update_entities(self, entities: List[Type[Base]]) -> None:
        if len(entities) == 0:
            self._logger.info(
                f">>> No entities passed to {self._update_entities.__name__}."
            )
            return
        entity_type = entities[0].__class__
        entity_type_name = entity_type.__name__
        status = StatusString(f"PROCESSING {entity_type_name.upper()}S")
        self._logger.info(status.get_status_str())
        existing_entities = self._get_entities(entity_type)
        entities_set = set(entities)

        # delete invalid entities first
        deleted_count = 0
        for entity in existing_entities:
            if entity not in entities_set:
                self._session.delete(entity)
                self._logger.debug(f">>> Removing {entity}.")
                deleted_count += 1
        if deleted_count > 0:
            self._logger.info(
                f">>> Removed {deleted_count} invalid {entity_type_name}(s) from database."
            )
        else:
            self._logger.info(
                f">>> No invalid {entity_type_name}(s) in database detected."
            )

        # add new entities
        new_count = 0
        for entity in entities_set:
            if entity not in existing_entities:
                self._session.merge(entity)
                self._logger.debug(f">>> Adding {entity}.")
                new_count += 1
        if new_count > 0:
            self._logger.info(
                f">>> Added {new_count} new {entity_type_name}(s) to database."
            )
        else:
            self._logger.info(f">>> No new {entity_type_name}(s) detected.")

        self._session.commit()
        self._logger.info(status.get_status_done_str())

    def _get_entities(self, table_class: Type[Base]):
        return self._session.query(table_class).all()

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

    def log_update(self, data_type: EntityType) -> None:
        """
        Insert entry in log table
        Args:
            data_type: data provider type which got updated
        """
        self._session.add(UpdateLog(data_type=data_type, loaddate=datetime.now()))
        self._session.commit()

    def get_manufacturers(self) -> List[Manufacturer]:
        """
        Returns:
            All manufacturer entities in database
        """
        return self._get_entities(Manufacturer)

    def get_ships(self) -> List[Ship]:
        """
        Returns:
            All ship entities in database
        """
        return self._get_entities(Ship)

    def get_standalones(self) -> List[Standalone]:
        """
        Returns:
            All standalone entities in database
        """
        return self._get_entities(Standalone)

    def get_upgrades(self) -> List[Upgrade]:
        """
        Returns:
            All upgrade entities in database
        """
        return self._get_entities(Upgrade)

    def get_loaddate(self, data_type: EntityType) -> Optional[datetime]:
        """
        Get latest update date for specified data type
        Args:
            data_type: data type to query
        Returns:
            smallest datetime or None if none found
        """
        result = self._session.query(func.max(UpdateLog.loaddate)).filter_by(data_type=data_type).first()
        if result is None:
            return None
        return result[0]

    def __del__(self):
        self._session.close()
        self._engine.dispose()
