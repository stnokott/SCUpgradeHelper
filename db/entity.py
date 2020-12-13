"""Contains entity classes for ORM"""
from datetime import datetime

from sqlalchemy import event, Column, ForeignKey, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Manufacturer(Base):
    """
    Class representing a ship manufacturer
    """

    __tablename__ = "MANUFACTURERS"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    code = Column(String, unique=True)

    def copy_attrs_to(self, target: "Manufacturer") -> None:
        """
        Copies this instance's values to the target
        Args:
            target: receiver of this instance's values
        """
        if self.name is not None:
            target.name = self.name
        if self.code is not None:
            target.code = self.code

    def __eq__(self, other):
        return (
            self.id == other.id and self.name == other.name and self.code == other.code
        )

    def __hash__(self):
        return hash(("name", self.name, "code", self.code))

    def __repr__(self):
        return f"<{Manufacturer.__name__}>({self.code}/{self.name})"


class Ship(Base):
    """
    Class representing a purchasable ship or vehicle
    """

    __tablename__ = "SHIPS"

    id = Column(Integer, primary_key=True, autoincrement=True)
    loaddate = Column(DateTime)
    name = Column(String, unique=True, nullable=False)
    official_sku_price_usd = Column(Float)
    manufacturer_id = Column(Integer, ForeignKey(Manufacturer.id), nullable=False)

    manufacturer = relationship("Manufacturer")

    def copy_attrs_to(self, target: "Ship") -> None:
        """
        Copies this instance's values to the target
        Args:
            target: receiver of this instance's values
        """
        if self.name is not None:
            target.name = self.name
        if self.official_sku_price_usd is not None:
            target.official_sku_price_usd = self.official_sku_price_usd
        if self.manufacturer_id is not None:
            target.manufacturer_id = self.manufacturer_id
        if self.manufacturer is not None:
            target.manufacturer = self.manufacturer

    def __eq__(self, other):
        return (
                self.name == other.name
                and self.official_sku_price_usd == other.official_sku_price_usd
                and self.manufacturer_id == other.manufacturer_id
        )

    def __hash__(self):
        return hash(("name", self.name))

    def __repr__(self):
        return f"<{Ship.__name__}>({self.manufacturer.code} {self.name}" \
               f"{', $' + str(self.official_sku_price_usd) if self.official_sku_price_usd is not None else ''}) "


@event.listens_for(Ship, "before_insert")
@event.listens_for(Ship, "before_update")
def update_ship_loaddate(mapper, connection, target: Ship):
    target.loaddate = datetime.now()


Manufacturer.ships = relationship(
    "Ship", order_by=Ship.id, back_populates="manufacturer", cascade="all"
)
