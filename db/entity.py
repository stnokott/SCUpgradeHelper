"""Contains entity classes for ORM"""
from datetime import datetime

from sqlalchemy import event, Column, ForeignKey, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Manufacturer(Base):
    """
    Class representing a ship manufacturer
    """

    __tablename__ = "MANUFACTURERS"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    code = Column(String, unique=True)

    def copy_attrs_to(self, target: "Manufacturer") -> None:
        """
        Copies this instance's values to the target
        Args:
            target: receiver of this instance's values
        """
        target.name = self.name
        target.code = self.code

    def __eq__(self, other):
        return (
                self.id == other.id and self.name == other.name and self.code == other.code
        )

    def __repr__(self):
        return f"<{Manufacturer.__name__}>({self.name})"


class Ship(Base):
    """
    Class representing a purchasable ship or vehicle
    """

    __tablename__ = "SHIPS"

    id = Column(Integer, primary_key=True, autoincrement=True)
    loaddate = Column(DateTime)
    name = Column(String, unique=True)
    manufacturer_id = Column(Integer, ForeignKey(Manufacturer.id))

    manufacturer = relationship("Manufacturer", back_populates="ships")

    def __init__(self, name: str, manufacturer: Manufacturer):
        self.name = name
        self.manufacturer_id = manufacturer.id
        self.manufacturer = manufacturer

    def copy_attrs_to(self, target: "Ship") -> None:
        """
        Copies this instance's values to the target
        Args:
            target: receiver of this instance's values
        """
        target.name = self.name
        target.manufacturer_id = self.manufacturer_id

    def __eq__(self, other):
        return self.name == other.name and self.manufacturer_id == other.manufacturer_id

    def __repr__(self):
        return f"<{Ship.__name__}>({self.manufacturer.code} {self.name})"


@event.listens_for(Ship, 'before_insert')
@event.listens_for(Ship, 'before_update')
def update_ship_loaddate(mapper, connection, target: Ship):
    target.loaddate = datetime.now()


Manufacturer.ships = relationship("Ship", order_by=Ship.id, back_populates="manufacturer", cascade="all")
