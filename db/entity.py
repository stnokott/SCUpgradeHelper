"""Contains entity classes for ORM"""
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String

Base = declarative_base()


class Ship(Base):
    """
    Class representing a purchasable ship or vehicle
    """

    __tablename__ = "SHIPS"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    manufacturer = Column(String)
    price_dollar = Column(Float)

    def __repr__(self):
        return "<%s@%d(%s, $%d)>" % self.__name__, self.id, self.name, self.price_dollar
