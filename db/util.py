"""Manager for database entities"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from const import DATABASE_FILEPATH
from db.entity import Ship, Base, Manufacturer


class EntityManager:
    """
    Manages the application's database and its entities
    """

    def __init__(self, logger: logging.Logger):
        self._engine = create_engine(
            f"sqlite:///{DATABASE_FILEPATH}", echo=(logger.level == logging.DEBUG)
        )
        self._session = Session(bind=self._engine, expire_on_commit=False)
        self._logger = logger
        self._create_schema()

    def _create_schema(self):
        self._logger.debug("Applying database schemata...")
        Base.metadata.create_all(self._engine)

    def update_manufacturers(
        self, manufacturers: List[Manufacturer], drop_first: bool
    ) -> None:
        """
        Insert manufacturers or update if existing
        Args:
            manufacturers: manufacturers to process
            drop_first: will drop ship table before processing if True
        """
        self._logger.debug("### PROCESSING MANUFACTURERS ###")
        self._logger.debug(">>> Removing duplicates...")
        manufacturers = set(manufacturers)

        if drop_first:
            self._logger.debug(f"Dropping {Manufacturer.__tablename__} data...")
            self._session.query(Manufacturer).delete()
            # add all manufacturers to empty table
            self._logger.debug(
                f"Adding {len(manufacturers)} manufacturers to database..."
            )
            self._session.add_all(manufacturers)
        else:
            for manufacturer in manufacturers:
                self.update_manufacturer(manufacturer, commit=False)
        self._session.commit()
        self._logger.debug("############# DONE #############")

    def update_manufacturer(self, manufacturer: Manufacturer, commit: bool = True):
        # check if manufacturer already exists
        queried_manufacturer = self.get_manufacturer_by_name(manufacturer.name)
        if not queried_manufacturer:
            # add if not existing in db
            self._session.add(manufacturer)
        elif queried_manufacturer != manufacturer:
            # overwrite data if exists, but not equal
            manufacturer.copy_attrs_to(queried_manufacturer)
        if commit:
            self._session.commit()

    def get_manufacturer_by_name(self, manufacturer_name: str):
        """
        Get ship manufactuerer by name
        Args:
            manufacturer_name: manufacturer name

        Returns:
            Manufacturer instance if found, otherwise None
        """
        query = self._session.query(Manufacturer).filter(
            Manufacturer.name == manufacturer_name
        )
        queried_manufacturer = query.first()
        return queried_manufacturer

    def update_ships(self, ships: List[Ship], drop_first: bool) -> None:
        """
        Insert ships or update if existing
        Args:
            ships: ships to process
            drop_first: will drop ship table before processing if True
        """
        self._logger.info("### PROCESSING SHIPS ###")

        self._logger.debug(">>> Applying manufacturers from database...")
        for ship in ships:
            queried_manufacturer = self.get_manufacturer_by_name(ship.manufacturer.name)
            if queried_manufacturer:
                ship.manufacturer_id = queried_manufacturer.id
                ship.manufacturer = queried_manufacturer
            else:
                self.update_manufacturer(queried_manufacturer, commit=False)

        if drop_first:
            self._logger.debug(f"Dropping {Ship.__tablename__} data...")
            self._session.query(Ship).delete()
            # add all ships to empty table
            self._logger.debug(f"Adding {len(ships)} ships to database...")
            self._session.add_all(ships)
        else:
            for ship in ships:
                self.update_ship(ship, commit=False)
        new_ship_count = 0
        if len(self._session.new) > 0:
            for new_ship in self._session.new:
                if isinstance(new_ship, Ship):
                    new_ship_count += 1
                    self._logger.info(f">>> New ship added: {new_ship}.")
        updated_ship_count = 0
        if len(self._session.dirty) > 0:
            for updated_ship in self._session.dirty:
                if isinstance(updated_ship, Ship):
                    updated_ship_count += 1
                    self._logger.info(f">>> Ship updated: {updated_ship}.")
        if new_ship_count + updated_ship_count < len(ships):
            self._logger.info(
                f">>> {len(ships) - (new_ship_count + updated_ship_count)} pre-existing ships skipped."
            )

        self._session.commit()
        self._logger.info("######### DONE #########")

    def update_ship(self, ship: Ship, commit: bool = True):
        # check if ship already exists
        queried_ship = self.get_ship_by_name(ship.name)
        if not queried_ship:
            # add if not existing in db
            self._session.add(ship)
        elif queried_ship != ship:
            # overwrite data if exists, but not equal
            ship.copy_attrs_to(queried_ship)
        if commit:
            self._session.commit()

    def get_ships_loaddate(self) -> Optional[datetime]:
        """
        Gets smallest load date from ship database
        Returns:
            datetime of smallest load date
        """
        result = self._session.query(func.min(Ship.loaddate)).first()
        if result is None:
            return None
        return result[0]

    def get_ship_by_name(self, ship_name: str):
        """
        Returns ship by name if found else None
        Args:
            ship_name: ship name to filter by

        Returns:
            Ship instance if exists, else None
        """
        with self._session.no_autoflush:
            query = self._session.query(Ship).filter(Ship.name == ship_name)
            queried_ship = query.first()
        return queried_ship

    def get_ships(self) -> List[Ship]:
        """
        Retrieve list of Ship entities present in database
        """
        ships = self._session.query(Ship).all()
        return ships

    def __del__(self):
        self._session.close()
        self._engine.dispose()
