"""Contains entity classes for ORM"""
import enum
from datetime import datetime

from sqlalchemy import (
    event,
    Column,
    ForeignKey,
    Integer,
    Float,
    DateTime,
    Enum,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, declared_attr

Base = declarative_base()


class UpdateType(enum.Enum):
    """
    Enum for specifying type of data update (e.g. when updating official standalone ships, use RSI_STANDALONES)
    """

    MANUFACTURERS = "Manufacturers"
    SHIPS = "Ships"
    RSI_STANDALONES = "Official Standalones"
    RSI_UPGRADES = "Official Upgrades"
    REDDIT_STANDALONES = "Reddit standalones"
    REDDIT_UPGRADES = "Reddit upgrades"


class Manufacturer(Base):
    """
    Class representing a ship manufacturer
    """

    __tablename__ = "MANUFACTURERS"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, unique=True, nullable=False)
    code = Column(Text, unique=True)

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
    __searchable__ = ["name"]

    id = Column(Integer, primary_key=True, autoincrement=True)
    loaddate = Column(DateTime)
    name = Column(Text, unique=True, nullable=False)
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
        return self.name == other.name and self.manufacturer_id == other.manufacturer_id

    def __hash__(self):
        return hash(("name", self.name))

    def __repr__(self):
        return f"<{Ship.__name__}>({self.manufacturer.code} {self.name})"


@event.listens_for(Ship, "before_insert")
@event.listens_for(Ship, "before_update")
def update_ship_loaddate(mapper, connection, target: Ship):
    """
    Update ship loaddate when persisting to DB
    Args:
        mapper: n/a
        connection: n/a
        target: ship entity to persist
    """
    target.loaddate = datetime.now()


Manufacturer.ships = relationship(
    "Ship", order_by=Ship.id, back_populates="manufacturer", cascade="all"
)


class Store(Base):
    """
    Entity representing a store where standalones/upgrades can be purchased
    """

    __tablename__ = "STORES"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    url = Column(Text, nullable=False)
    standalones = relationship("Standalone", order_by="Standalone.id", viewonly=True)
    upgrades = relationship("Upgrade", order_by="Upgrade.id", viewonly=True)

    uniq = UniqueConstraint(name, url)

    def __eq__(self, other):
        return self.name == other.name and self.url == other.url

    def __hash__(self):
        return hash(
            (
                "name",
                self.name,
                "url",
                self.url,
            )
        )

    def __repr__(self):
        return f"<{Store.__name__}>({self.name})"


class Purchasable(Base):
    __abstract__ = True

    id = Column(Integer, primary_key=True, autoincrement=True)
    loaddate = Column(DateTime)
    price_usd = Column(Float, nullable=False)

    @declared_attr
    def store_id(self):
        return Column(Integer, ForeignKey(Store.id), nullable=False)

    @declared_attr
    def store(self):
        return relationship("Store", cascade="merge")

    def __eq__(self, other):
        return self.price_usd == other.price_usd and self.store_id == other.store_id


class Standalone(Purchasable):
    """
    Entity representing a purchase that gives you a ship directly
    """

    __tablename__ = "STANDALONE"

    ship_id = Column(Integer, ForeignKey(Ship.id), nullable=False)
    ship = relationship("Ship")

    def __eq__(self, other):
        return super().__eq__(other) and self.ship_id == other.ship_id

    def __hash__(self):
        return hash(
            (
                "ship_id",
                self.ship_id,
                "price_usd",
                self.price_usd,
                "store_id",
                self.store_id,
            )
        )

    def __repr__(self):
        ship_name = self.ship.name if self.ship is not None else self.ship_id
        return f"<{Standalone.__name__}>({ship_name}: ${self.price_usd} @ {self.store.name})"


@event.listens_for(Standalone, "before_insert")
@event.listens_for(Standalone, "before_update")
def update_standalone_loaddate(mapper, connection, target: Standalone):
    """
    Update standalone loaddate when persisting to DB
    Args:
        mapper: n/a
        connection: n/a
        target: standalone entity to persist
    """
    target.loaddate = datetime.now()


class Upgrade(Purchasable):
    """
    Entity representing a ship upgrade
    """

    __tablename__ = "UPGRADES"

    ship_id_from = Column(Integer, ForeignKey(Ship.id), nullable=False)
    ship_id_to = Column(Integer, ForeignKey(Ship.id), nullable=False)

    ship_from = relationship("Ship", foreign_keys=[ship_id_from])
    ship_to = relationship("Ship", foreign_keys=[ship_id_to])

    def __eq__(self, other):
        return (
            super().__eq__(other)
            and self.ship_id_from == other.ship_id_from
            and self.ship_id_to == other.ship_id_to
        )

    def __hash__(self):
        return hash(
            (
                "ship_id_from",
                self.ship_id_from,
                "ship_id_to",
                self.ship_id_to,
                "price_usd",
                self.price_usd,
                "store_id",
                self.store_id,
            )
        )

    def __repr__(self):
        ship_from_name = (
            self.ship_from.name if self.ship_from is not None else self.ship_id_from
        )
        ship_to_name = (
            self.ship_to.name if self.ship_to is not None else self.ship_id_to
        )
        return (
            f"<{Upgrade.__name__}>(From [{ship_from_name}] to [{ship_to_name}]: "
            f"${self.price_usd} @ {self.store.name})"
        )


@event.listens_for(Upgrade, "before_insert")
@event.listens_for(Upgrade, "before_update")
def update_upgrade_loaddate(mapper, connection, target: Upgrade):
    """
    Update upgrade loaddate when persisting to DB
    Args:
        mapper: n/a
        connection: n/a
        target: upgrade entity to persist
    """
    target.loaddate = datetime.now()


class UpdateLog(Base):
    """
    Entity representing an entry in the log table
    """

    __tablename__ = "UPDATE_LOGS"

    id = Column(Integer, primary_key=True, autoincrement=True)
    update_type = Column(Enum(UpdateType))
    loaddate = Column(DateTime)

    def __eq__(self, other):
        return self.update_type == other.update_type and self.loaddate == other.loaddate

    def __hash__(self):
        return hash(("data_type", self.update_type, "loaddate", self.loaddate))

    def __repr__(self):
        return f"<{UpdateLog.__name__}>({self.update_type} updated at {self.loaddate})"
