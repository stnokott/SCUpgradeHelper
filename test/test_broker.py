import pytest

from broker import SCDataBroker
from config import ConfigProvider
from util import CustomLogger


@pytest.fixture(scope="session")
def broker():
    logger = CustomLogger(__name__)
    broker = SCDataBroker(logger, ConfigProvider(logger))
    return broker


class TestSCDataBroker:
    def test_complete_update(self, broker):
        broker.complete_update(True)

    def test_get_upgrade_path(self, broker):
        upgrade_path = broker.get_upgrade_path(1, 60)
        assert upgrade_path is not None
        assert upgrade_path.total_cost is not None
        assert upgrade_path.total_cost > 0
        assert upgrade_path.upgrades[0].ship_id_from == 1
        assert upgrade_path.upgrades[-1].ship_id_to == 60

    def test_get_purchase_path(self, broker):
        purchase_path = broker.get_purchase_path(1)
        assert purchase_path is not None
        assert len(purchase_path.path.upgrades) == 0
        assert len(purchase_path.path) == 0
        assert purchase_path.start_purchase is not None
        assert purchase_path.start_purchase.ship_id == 1
        assert purchase_path.start_purchase.price_usd > 0

    def test_get_ships(self, broker):
        ships = broker.get_ships()
        assert ships is not None
        assert len(ships) > 0

    def test_get_upgrades(self, broker):
        upgrades = broker.get_upgrades()
        assert upgrades is not None
        assert len(upgrades) > 0
