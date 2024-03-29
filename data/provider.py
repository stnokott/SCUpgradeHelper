"""Contains utility classes for providing data"""
import enum
from abc import abstractmethod
from datetime import timedelta, datetime
from typing import List, Tuple, Any, Type

from data.scraper.scraper import RSIScraper, RedditScraper
from db.entity import Ship, Upgrade, Standalone, Base
from util.const import (
    SHIP_DATA_EXPIRY,
    RSI_UPGRADE_DATA_EXPIRY,
    RSI_STANDALONE_DATA_EXPIRY,
    REDDIT_DATA_EXPIRY,
)
from util.helpers import format_timedelta, CustomLogger


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
        if self.last_updated is None:
            return True
        return self.last_updated + self.lifetime < datetime.now()

    def expires_in(self) -> str:
        """
        Returns the time left to expiry from now
        Returns:
            timedelta representing the time left to expiry
        """
        if self.is_expired():
            return "(not expired)"
        return format_timedelta(self.last_updated + self.lifetime - datetime.now())


class DataProvider:
    """
    Abstract base class providing functions to update itself and to retrieve its data.
    """

    def __init__(
        self,
        initial_data: List[Any],
        last_loaded: datetime,
        data_lifetime: timedelta,
        logger: CustomLogger,
    ):
        self._data = initial_data
        self.data_expiry = Expiry(last_loaded, data_lifetime)
        self._logger = logger

    @abstractmethod
    def _refresh_data(self) -> None:
        """
        Update this provider's internal data
        """
        pass

    def _update_expiry(self) -> None:
        self.data_expiry.last_updated = datetime.now()

    def get_data(
        self, force: bool = False, echo: bool = False
    ) -> Tuple[List[Any], bool]:
        """
        Retrieve this data provider's data
        Args:
            force: forces refresh of data if True
            echo: produces info logs if True

        Returns:
            [0]: list of ORM entities
            [1]: True if provider's data got updated, otherwise False
        """
        self._logger.info(f"Checking {self.__class__.__name__} expiry...")
        refreshed = False
        if self.data_expiry.is_expired():
            self._logger.info(
                f">>> {self.__class__.__name__} data expired, updating..."
            )
            self._refresh_data()
            refreshed = True
        elif force:
            self._logger.info(f">>> {self.__class__.__name__} data update forced...")
            self._refresh_data()
            refreshed = True
        elif echo:
            self._logger.success(
                f">>> {self.__class__.__name__} data valid, expires in {self.data_expiry.expires_in()}",
                CustomLogger.LEVEL_INFO,
            )
        return self._data, refreshed


class DataProviderType(enum.Enum):
    SHIPS = "RSI Ships"
    RSI_STANDALONES = "RSI Standalones"
    RSI_UPGRADES = "RSI Upgrades"
    REDDIT_ENTRIES = "Reddit entries"


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
            raise ValueError(f"provider for update type {data_type} not found.")
        return self._data_providers[data_type]

    # TODO: add data providers automatically on initialization
    def add_data_provider(
        self, data_type: DataProviderType, data_provider: DataProvider
    ) -> None:
        """
        Add data provider to manager if possible. Throws ValueError if already exists.
        Args:
            data_type: type to save the provider under
            data_provider: data provider to add
        """
        if data_type in self._data_providers:
            raise ValueError(f"Provider for type {data_type} already exists.")
        self._data_providers[data_type] = data_provider


class ShipDataProvider(DataProvider):
    """
    Provides data about ships in concept, development or game
    """

    def __init__(
        self, initial_data: List[Ship], last_loaded: datetime, logger: CustomLogger
    ):
        super().__init__(initial_data, last_loaded, SHIP_DATA_EXPIRY, logger)
        self.__scraper = RSIScraper(self._logger)

    def _refresh_data(self) -> None:
        """
        Updates underlying ship data
        """
        self._data = self.__scraper.get_ships()
        self._update_expiry()


class OfficialStandaloneDataProvider(DataProvider):
    """
    Provides data about standalone ship offers
    """

    def __init__(
        self,
        initial_data: List[Standalone],
        ship_data_provider: ShipDataProvider,
        last_loaded: datetime,
        logger: CustomLogger,
    ):
        super().__init__(initial_data, last_loaded, RSI_STANDALONE_DATA_EXPIRY, logger)
        self.__ship_data_provider = ship_data_provider
        self._scraper = RSIScraper(self._logger)

    def _refresh_data(self) -> None:
        """
        Updates underlying ship data
        """
        self._data = self._scraper.get_standalones(
            self.__ship_data_provider.get_data()[0]
        )
        self._update_expiry()


class OfficialUpgradeDataProvider(DataProvider):
    """
    Provides data about ship upgrades
    """

    def __init__(
        self,
        initial_data: List[Upgrade],
        ship_data_provider: ShipDataProvider,
        last_loaded: datetime,
        logger: CustomLogger,
    ):
        super().__init__(initial_data, last_loaded, RSI_UPGRADE_DATA_EXPIRY, logger)
        self.__ship_data_provider = ship_data_provider
        self._scraper = RSIScraper(self._logger)

    def _refresh_data(self) -> None:
        """
        Updates underlying ship data
        """
        self._data = self._scraper.get_upgrades(self.__ship_data_provider.get_data()[0])
        self._update_expiry()


class RedditDataProvider(DataProvider):
    """
    Provides data about store entries on Reddit
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        initial_data: List[Type[Base]],
        last_loaded: datetime,
        logger: CustomLogger,
    ):
        super().__init__(initial_data, last_loaded, REDDIT_DATA_EXPIRY, logger)
        self._scraper = RedditScraper(client_id, client_secret, self._logger)

    def _refresh_data(self) -> None:
        """
        Updates underlying entry data
        """
        self._data = self._scraper.get_parsed_submissions()
        self._update_expiry()
