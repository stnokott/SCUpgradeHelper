"""Contains utility classes for providing data"""
from abc import abstractmethod
from datetime import timedelta, datetime
from enum import Enum
from typing import List

from sqlalchemy.schema import Table


class DataProvider:
    """
    Abstract base class providing functions to update itself and to retrieve its data.
    """
    def __init__(self, data_lifetime: timedelta):
        self._data_lifetime = data_lifetime
        # TODO: retrieve _last_fetched_datetime from file
        self._last_fetched_datetime = datetime(1900, 1, 1, 1, 1, 1, 1)
        self._data = []

    def _is_data_expired(self) -> bool:
        """
        Returns True if underlying data is expired and needs to be fetched again
        """
        return (self._last_fetched_datetime + self._data_lifetime) < datetime.now()

    @abstractmethod
    def update(self) -> bool:
        """
        Update this provider's internal data if necessary
        Returns:
            True if update performed, False otherwise
        """
        pass

    def get_data(self) -> List[Table]:
        """
        Retrieve this provider's data
        """
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

    def add_data_provider(self, data_type: DataProviderType, data_provider: DataProvider) -> None:
        """
        Add data provider to manager if possible. Throws ValueError if already exists.
        Args:
            data_type: data type to save the provider under
            data_provider: data provider to add
        """
        if data_type in self._data_providers:
            raise ValueError(f"Provider for type {data_type} already exists.")
        self._data_providers[data_type] = data_provider
