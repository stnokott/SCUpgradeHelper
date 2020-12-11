"""Contains utility classes for providing data"""
from abc import abstractmethod
from datetime import timedelta, datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy.schema import Table


class Expiry:
    """
    Class providing information about expiry
    """

    def __init__(self, last_updated: datetime, lifetime: timedelta):
        self.last_updated = last_updated
        self.lifetime = lifetime

    def is_expired(self) -> bool:
        """
        Checks if this instance is now expired
        Returns:
            True if expired, otherwise False
        """
        return self.last_updated + self.lifetime < datetime.now()

    def expires_in(self) -> Optional[timedelta]:
        """
        Returns the time left to expiry from now
        Returns:
            timedelta representing the time left to expiry
        """
        if self.is_expired():
            return None
        return self.last_updated + self.lifetime - datetime.now()


class DataProvider:
    """
    Abstract base class providing functions to update itself and to retrieve its data.
    """

    def __init__(self, last_loaded: datetime, data_lifetime: timedelta):
        self.data_expiry = Expiry(last_loaded, data_lifetime)
        self._data = []

    @abstractmethod
    def _refresh_data(self) -> None:
        """
        Update this provider's internal data
        """
        pass

    def _update_expiry(self) -> None:
        self.data_expiry.last_updated = datetime.now()

    def get_data(self, update: bool) -> List[Table]:
        """
        Retrieve this provider's data
        """
        if update:
            self._refresh_data()
        return self._data


class DataProviderType(Enum):
    """
    Enum for defining types of data providers
    """

    SHIPS = "Ships"


class DataProviderManager:
    """
    Class to manage data providers by their type
    """

    def __init__(self):
        self._data_providers = {}

    def get_data_provider(self, data_type: DataProviderType) -> DataProvider:
        """
        Return DataProvider instance by data_type
        Args:
            data_type: data type for which a DataProvider needs to be retrieved

        Returns:

        """
        if data_type not in self._data_providers:
            raise ValueError(f"provider for data type {data_type} not found.")
        return self._data_providers[data_type]

    def add_data_provider(
        self, data_type: DataProviderType, data_provider: DataProvider
    ) -> None:
        """
        Add data provider to manager if possible. Throws ValueError if already exists.
        Args:
            data_type: data type to save the provider under
            data_provider: data provider to add
        """
        if data_type in self._data_providers:
            raise ValueError(f"Provider for type {data_type} already exists.")
        self._data_providers[data_type] = data_provider
