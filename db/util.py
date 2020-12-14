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
        existing_manufacturers = self.get_manufacturers()
        manufacturers_set = set(manufacturers)

        # delete invalid manufacturers first
        deleted_count = 0
        for manufacturer in existing_manufacturers:
            if manufacturer not in manufacturers_set:
                self._session.delete(manufacturer)
                self._logger.debug(f">>> Removing {manufacturer}.")
                deleted_count += 1
        if deleted_count > 0:
            self._logger.info(f">>> Removed {deleted_count} invalid manufacturers from database.")
        else:
            self._logger.info(">>> No invalid manufacturers in database detected.")

        # add new manufacturers
        new_count = 0
        for manufacturer in manufacturers_set:
            if manufacturer not in existing_manufacturers:
                self._session.add(manufacturer)
                self._logger.debug(f">>> Adding {manufacturer}.")
                new_count += 1
        if new_count > 0:
            self._logger.info(f">>> Added {new_count} new manufacturers to database.")
        else:
            self._logger.info(">>> No new manufacturers detected.")

        self._session.commit()
        self._logger.debug("############# DONE #############")

    def get_manufacturers(self) -> List[Manufacturer]:
        return self._session.query(Manufacturer).all()

    def update_ships(self, ships: List[Ship]) -> None:
        """
        Insert ships
        Args:
            ships: ships to process
        """
        self._logger.info("### PROCESSING SHIPS ###")
        existing_ships = self.get_ships()
        ships_set = set(ships)

        self._logger.debug(">>> Applying manufacturers from database...")
        self.update_manufacturers([ship.manufacturer for ship in ships_set])

        # delete invalid ships first
        deleted_count = 0
        for ship in existing_ships:
            if ship not in ships_set:
                self._session.delete(ship)
                self._logger.debug(f">>> Removing {ship}.")
                deleted_count += 1
        if deleted_count > 0:
            self._logger.info(f">>> Removed {deleted_count} invalid ships from database.")
        else:
            self._logger.info(">>> No invalid ships in database detected.")

        # add new ships
        new_count = 0
        for ship in ships_set:
            if ship not in existing_ships:
                self._session.add(ship)
                self._logger.debug(f">>> Adding {ship}.")
                new_count += 1
        if new_count > 0:
            self._logger.info(f">>> Added {new_count} new ships to database.")
        else:
            self._logger.info(">>> No new ships detected.")

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
                self._logger.debug(f">>> Removing {upgrade}")
                deleted_count += 1
        self._logger.info(f">>> Removed {deleted_count} invalid upgrades from database.")

        # add new upgrades
        new_count = 0
        for upgrade in upgrades_set:
            if upgrade not in existing_upgrades:
                self._session.add(upgrade)
                self._logger.debug(f">>> Adding {upgrade}")
                new_count += 1
        self._logger.info(f">>> Added {new_count} new upgrades to database.")

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
