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
        if self.manufacturer_id is not None:
            target.manufacturer_id = self.manufacturer_id
        if self.manufacturer is not None:
            target.manufacturer = self.manufacturer

    def __eq__(self, other):
        return (
            self.name == other.name
            and self.manufacturer_id == other.manufacturer_id
        )

    def __hash__(self):
        return hash(("name", self.name))

    def __repr__(self):
        return (
            f"<{Ship.__name__}>({self.manufacturer.code} {self.name}"
        )


@event.listens_for(Ship, "before_insert")
@event.listens_for(Ship, "before_update")
def update_ship_loaddate(mapper, connection, target: Ship):
    target.loaddate = datetime.now()


Manufacturer.ships = relationship(
    "Ship", order_by=Ship.id, back_populates="manufacturer", cascade="all"
)


class Standalone(Base):
    """
    Entity representing a purchase that gives you a ship directly
    """

    __tablename__ = "STANDALONE"

    id = Column(Integer, primary_key=True, autoincrement=True)
    loaddate = Column(DateTime)
    ship_id = Column(Integer, ForeignKey(Ship.id), nullable=False)
    price_usd = Column(Float, nullable=False)
    store_name = Column(String, nullable=False)

    ship = relationship("Ship")

    def __eq__(self, other):
        return (
                self.ship_id == other.ship_id
                and self.price_usd == other.price_usd
                and self.store_name == other.store_name
        )

    def __hash__(self):
        return hash(
            (
                "ship_id",
                self.ship_id,
                "price_usd",
                self.price_usd,
                "store_name",
                self.store_name,
            )
        )

    def __repr__(self):
        ship_name = self.ship.name if self.ship is not None else self.ship_id
        return f"<{Standalone.__name__}>({ship_name}: ${self.price_usd} @ {self.store_name})"


@event.listens_for(Standalone, "before_insert")
@event.listens_for(Standalone, "before_update")
def update_standalone_loaddate(mapper, connection, target: Standalone):
    target.loaddate = datetime.now()


class Upgrade(Base):
    """
    Entity representing a ship upgrade
    """

    __tablename__ = "UPGRADES"

    id = Column(Integer, primary_key=True, autoincrement=True)
    loaddate = Column(DateTime)
    ship_from_id = Column(Integer, ForeignKey(Ship.id), nullable=False)
    ship_to_id = Column(Integer, ForeignKey(Ship.id), nullable=False)
    price_usd = Column(Float, nullable=False)
    store_name = Column(String, nullable=False)

    ship_from = relationship("Ship", foreign_keys=[ship_from_id])
    ship_to = relationship("Ship", foreign_keys=[ship_to_id])

    def __eq__(self, other):
        return (
                self.ship_from_id == other.ship_from_id
                and self.ship_to_id == other.ship_to_id
                and self.price_usd == other.price_usd
                and self.store_name == other.store_name
        )

    def __hash__(self):
        return hash(
            (
                "ship_from_id",
                self.ship_from_id,
                "ship_to_id",
                self.ship_to_id,
                "price_usd",
                self.price_usd,
                "store_name",
                self.store_name,
            )
        )

    def __repr__(self):
        ship_from_name = self.ship_from.name if self.ship_from is not None else self.ship_from_id
        ship_to_name = self.ship_to.name if self.ship_to is not None else self.ship_to_id
        return f"<{Upgrade.__name__}>(From [{ship_from_name}] to [{ship_to_name}]: " \
               f"${self.price_usd} @ {self.store_name})"


@event.listens_for(Upgrade, "before_insert")
@event.listens_for(Upgrade, "before_update")
def update_upgrade_loaddate(mapper, connection, target: Upgrade):
    target.loaddate = datetime.now()
