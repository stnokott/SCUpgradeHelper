"""Contains entity classes for ORM"""
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, Float, String

Base = declarative_base()


class Ship(Base):
    """
    Class representing a purchasable ship or vehicle
    """

    __tablename__ = "SHIP"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    manufacturer = Column(String)

    def __init__(self, name: str, manufacturer: str):
        self.name = name
        self.manufacturer = manufacturer

    def __repr__(self):
        return f"<{Ship.__name__}]>({self.manufacturer} {self.name})"
