"""Manager for database entities"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import List

from const import DATABASE_FILEPATH
from db.entity import Ship, Base


class EntityManager:
    def __init__(self):
        self._engine = create_engine(f"sqlite:///{DATABASE_FILEPATH}", echo=True)
        self.Session = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)

    def _create_session(self) -> Session:
        session = self.Session()
        return session

    def load_ships(self, ships: List[Ship], drop: bool = False) -> None:
        session = self._create_session()
        if drop:
            session.query(Ship).delete()
            # add all ships to empty table
            session.add_all(ships)
        else:
            for ship in ships:
                # check if ship already exists in db
                queried_ship = (
                    session.query(Ship).filter(Ship.name == ship.name).first()
                )
                if not queried_ship:
                    # add if not existing in db
                    session.add(ship)
                else:
                    print(f"Skipping insertion of existing {ship}")

        session.commit()
        session.close()

    def get_ships(self) -> List[Ship]:
        session = self._create_session()
        ships = session.query(Ship).all()
        session.close()
        return ships

    def __del__(self):
        self._engine.dispose()
