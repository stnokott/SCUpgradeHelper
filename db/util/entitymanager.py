"""Manager for database entities"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import List

from db.entity import Ship, Base


class EntityManager:
    def __init__(self):
        self._engine = create_engine("sqlite:///database.db", echo=True)
        self.Session = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)

    def _create_session(self) -> Session:
        session = self.Session()
        return session

    def get_ships(self) -> List[Ship]:
        session = self._create_session()
        ships = session.query(Ship).all()
        session.close()
        return ships

    def __del__(self):
        self._engine.dispose()
