"""Manager for database entities"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from const import DATABASE_FILEPATH
from db.entity import Ship, Base, Manufacturer, Upgrade


class EntityManager:
    """
    Manages the application's database and its entities
    """

    def __init__(self, logger: logging.Logger):
        self._engine = create_engine(
            f"sqlite:///{DATABASE_FILEPATH}", echo=False
        )
        self._session = Session(bind=self._engine, expire_on_commit=False)
        self._logger = logger
        self._create_schema()

    def _create_schema(self):
        self._logger.debug("Applying database schemata...")
        Base.metadata.create_all(self._engine)

    def update_manufacturers(
        self, manufacturers: List[Manufacturer]
    ) -> None:
        """
        Insert manufacturers or update if existing
        Args:
            manufacturers: manufacturers to process
        """
        self._logger.debug("### PROCESSING MANUFACTURERS ###")
        self._logger.debug(">>> Removing duplicates...")
        manufacturers = set(manufacturers)

        self._logger.debug(f"Dropping {Manufacturer.__tablename__} data...")
        self._session.query(Manufacturer).delete()
        # add all manufacturers to empty table
        self._logger.debug(
            f"Adding {len(manufacturers)} manufacturers to database..."
        )
        self._session.add_all(manufacturers)

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

    def update_ships(self, ships: List[Ship]) -> None:
        """
        Insert ships
        Args:
            ships: ships to process
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

        # drop existing data first
        self._logger.debug(f"Dropping {Ship.__tablename__} data...")
        self._session.query(Ship).delete()
        # add all ships to empty table
        self._logger.debug(f"Adding {len(ships)} ships to database...")
        self._session.add_all(ships)

        for new_ship in self._session.new:
            if isinstance(new_ship, Ship):
                self._logger.info(f">>> New ship added: {new_ship}.")

        self._session.commit()
        self._logger.info("######### DONE #########")

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

    def update_upgrades(self, upgrades: List[Upgrade]) -> None:
        """
        Insert upgrades
        Args:
            upgrades: upgrades to process
        """
        self._logger.info("### PROCESSING UPGRADES ###")
        existing_upgrades = self.get_upgrades()
        upgrades_set = set(upgrades)

        # delete invalid upgrades first
        deleted_count = 0
        for upgrade in existing_upgrades:
            if upgrade not in upgrades_set:
                self._session.delete(upgrade)
                deleted_count += 1
        self._logger.info(f">>> Removing {deleted_count} invalid upgrades from database...")

        # add new upgrades
        new_count = 0
        for upgrade in upgrades_set:
            if upgrade not in existing_upgrades:
                self._session.add(upgrade)
                new_count += 1
        self._logger.info(f">>> Adding {new_count} new upgrades to database...")

        self._session.commit()
        self._logger.info("########## DONE ###########")

    def get_upgrades_loaddate(self) -> Optional[datetime]:
        """
        Gets smallest load date from upgrades database
        Returns:
            datetime of smallest load date
        """
        result = self._session.query(func.min(Upgrade.loaddate)).first()
        if result is None:
            return None
        return result[0]

    def get_upgrades(self) -> List[Upgrade]:
        """
        Retrieve list of Upgrade entities present in database
        """
        ships = self._session.query(Upgrade).all()
        return ships

    def __del__(self):
        self._session.close()
        self._engine.dispose()
