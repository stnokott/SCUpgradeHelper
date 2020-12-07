"""Manager for database entities"""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import List

from const import DATABASE_FILEPATH
from data.provider import DataProviderManager, DataProviderType
from db.entity import Ship, Base


class EntityManager:
    """
    Manages the application's database and its entities
    """

    def __init__(
            self,
            data_provider_manager: DataProviderManager,
            logger: logging.Logger,
            reset_db: bool = False,
            update_later: bool = False,
    ):
        self._engine = create_engine(f"sqlite:///{DATABASE_FILEPATH}", echo=(logger.level == logging.DEBUG))
        self.Session = sessionmaker(bind=self._engine)
        self._data_provider_manager = data_provider_manager
        self._logger = logger
        self._create_schema()
        if not update_later:
            self._update_all_tables(not reset_db)

    def _create_schema(self):
        self._logger.debug("Applying database schemata...")
        Base.metadata.create_all(self._engine)

    def _create_session(self) -> Session:
        session = self.Session()
        return session

    def _update_table_by_provider_type(
            self, data_provider_type: DataProviderType, update_only: bool = True
    ):
        data_provider = self._data_provider_manager.get_data_provider(
            data_provider_type
        )
        update_performed = data_provider.update()
        if update_performed:
            if data_provider_type == DataProviderType.SHIPS:
                self._insert_ships(data_provider.get_data(), not update_only)
            else:
                raise ValueError(
                    f"No insert method known for provider type {data_provider_type}"
                )

    def _update_all_tables(self, update_only: bool):
        self._logger.info("Updating database...")
        self._update_table_by_provider_type(DataProviderType.SHIPS, update_only)
        self._logger.info("Database successfully updated.")

    def _insert_ships(self, ships: List[Ship], drop_first: bool) -> None:
        """
        Insert ships
        """
        self._logger.debug("Processing ship list...")
        session = self._create_session()
        if drop_first:
            self._logger.debug(f"Dropping {Ship.__tablename__} data...")
            session.query(Ship).delete()
            # add all ships to empty table
            self._logger.debug(f"Adding {len(ships)} ships to database...")
            session.add_all(ships)
        else:
            skipped_count = 0
            for ship in ships:
                # check if ship already exists in db
                query = session.query(Ship).filter(Ship.name == ship.name)
                queried_ship = query.first()
                if not queried_ship:
                    # add if not existing in db
                    session.add(ship)
                elif queried_ship != ship:
                    ship.copy_attrs_to(queried_ship)
                else:
                    skipped_count += 1
            if len(session.new) > 0:
                self._logger.debug(f"Inserting {len(session.new)} new ships:")
                for new_entity in session.new:
                    if type(new_entity) == Ship:
                        print(f">>> {new_entity}")
            if len(session.dirty) > 0:
                self._logger.debug(f"Updating {len(session.dirty)} ships with new data.")
            if skipped_count > 0:
                self._logger.debug(f"({skipped_count} pre-existing ships skipped.)")

        session.commit()
        session.close()
        self._logger.debug("Done processing ship list.")

    def get_ships(self) -> List[Ship]:
        """
        Retrieve list of Ship entities present in database
        """
        self._update_table_by_provider_type(DataProviderType.SHIPS)
        session = self._create_session()
        ships = session.query(Ship).all()
        session.close()
        return ships

    def __del__(self):
        self._engine.dispose()
