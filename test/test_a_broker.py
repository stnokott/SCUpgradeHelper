"""Renamed to be executed first"""
import pytest

from broker import SCDataBroker
from config import ConfigProvider
from db.entity import Upgrade, Standalone
from util import CustomLogger


@pytest.fixture(scope="session")
def broker():
    logger = CustomLogger(__name__)
    broker = SCDataBroker(logger, ConfigProvider(logger))
    return broker


class TestSCDataBroker:
    def test_complete_update(self, broker: SCDataBroker):
        broker.complete_update(True)

    def test_get_upgrade_path(self, broker: SCDataBroker):
        broker._em.update_rsi_upgrades(
            [
                Upgrade(ship_id_from=1, ship_id_to=25, price_usd=999.0, store_id=1),
                Upgrade(ship_id_from=25, ship_id_to=60, price_usd=999.0, store_id=1),
            ]
        )
        upgrade_path = broker.get_upgrade_path(1, 60)
        assert upgrade_path is not None
        assert upgrade_path.total_cost is not None
        assert upgrade_path.total_cost == (999.0 + 999.0)
        assert upgrade_path.upgrades[0].ship_id_from == 1
        assert upgrade_path.upgrades[-1].ship_id_to == 60

    def test_get_purchase_path(self, broker: SCDataBroker):
        broker._em.update_rsi_standalones(
            [Standalone(price_usd=25.0, ship_id=999.0, store_id=1)]
        )
        purchase_path = broker.get_purchase_path(1)
        assert purchase_path is not None
        assert len(purchase_path.path.upgrades) == 0
        assert len(purchase_path.path) == 0
        assert purchase_path.start_purchase is not None
        assert purchase_path.start_purchase.ship_id == 1
        assert purchase_path.start_purchase.price_usd > 0

    def test_get_ships(self, broker: SCDataBroker):
        ships = broker.get_ships()
        assert ships is not None
        assert len(ships) > 0

    def test_get_upgrades(self, broker: SCDataBroker):
        upgrades = broker.get_upgrades()
        assert upgrades is not None
        assert len(upgrades) > 0
