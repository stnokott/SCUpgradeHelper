from datetime import datetime, timedelta

import pytest

from data.provider import (
    Expiry,
    DataProviderManager,
    ShipDataProvider,
    OfficialStandaloneDataProvider,
    OfficialUpgradeDataProvider,
    DataProviderType,
)
from util.helpers import format_timedelta, CustomLogger


def test_expiry_expired():
    last_updated_last_year = datetime.now() - timedelta(days=365)
    lifetime = timedelta(days=1)
    expired = Expiry(last_updated_last_year, lifetime)
    assert expired.is_expired()


def test_expiry_not_expired():
    last_updated_less_than_one_hour_ago = datetime.now() - timedelta(
        minutes=59, seconds=59
    )
    lifetime = timedelta(hours=1)
    expired = Expiry(last_updated_less_than_one_hour_ago, lifetime)
    assert not expired.is_expired()
    assert expired.expires_in() == format_timedelta(timedelta(minutes=0, seconds=1))


class TestDataProviderManager:
    _DPM = DataProviderManager()

    def test_add_data_provider(self):
        logger = CustomLogger(__name__)
        ship_data_provider = ShipDataProvider([], datetime.now(), logger)
        official_standalone_data_provider = OfficialStandaloneDataProvider(
            [], ship_data_provider, datetime.now(), logger
        )
        official_upgrade_data_provider = OfficialUpgradeDataProvider(
            [], ship_data_provider, datetime.now(), logger
        )
        self._DPM.add_data_provider(DataProviderType.SHIPS, ship_data_provider)
        self._DPM.add_data_provider(
            DataProviderType.RSI_STANDALONES, official_standalone_data_provider
        )
        self._DPM.add_data_provider(
            DataProviderType.RSI_UPGRADES, official_upgrade_data_provider
        )

    def test_get_data_provider(self):
        ship_data_provider = self._DPM.get_data_provider(DataProviderType.SHIPS)
        assert ship_data_provider is not None
        assert type(ship_data_provider) == ShipDataProvider
        official_standalone_data_provider = self._DPM.get_data_provider(
            DataProviderType.RSI_STANDALONES
        )
        assert official_standalone_data_provider is not None
        assert type(official_standalone_data_provider) == OfficialStandaloneDataProvider
        official_upgrade_data_provider = self._DPM.get_data_provider(
            DataProviderType.RSI_UPGRADES
        )
        assert official_upgrade_data_provider is not None
        assert type(official_upgrade_data_provider) == OfficialUpgradeDataProvider
        with pytest.raises(ValueError):
            self._DPM.get_data_provider(DataProviderType.REDDIT_ENTRIES)

    def test_get_data_provider_data(self):
        ship_data_provider = self._DPM.get_data_provider(DataProviderType.SHIPS)
        data, updated = ship_data_provider.get_data(True, False)
        assert data is not None
        assert len(data) > 0
        assert updated is True
        data, updated = ship_data_provider.get_data(False, False)
        assert data is not None
        assert len(data) > 0
        assert updated is False
