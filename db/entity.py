"""Contains entity classes for ORM"""
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String

Base = declarative_base()


class Ship(Base):
    """
    Class representing a purchasable ship or vehicle
    """

    __tablename__ = "SHIP"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True)
    manufacturer = Column(String)

    def __init__(self, name: str, manufacturer: str):
        self.name = name
        self.manufacturer = manufacturer

    def copy_attrs_to(self, target: 'Ship') -> None:
        """
        Copies this instance's values to the target
        Args:
            target: receiver of this instance's values
        """
        target.name = self.name
        target.manufacturer = self.manufacturer

    def __eq__(self, other):
        return (
            self.id == other.id
            and self.name == other.name
            and self.manufacturer == other.manufacturer
        )

    def __repr__(self):
        return f"<{Ship.__name__}>({self.manufacturer} {self.name})"
