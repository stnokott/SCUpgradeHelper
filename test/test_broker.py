from broker import SCDataBroker
from config import ConfigProvider
from util import CustomLogger


class TestSCDataBroker:
    _LOGGER = CustomLogger(__name__)
    _BROKER = SCDataBroker(_LOGGER, ConfigProvider(_LOGGER))

    def test_complete_update(self):
        self._BROKER.complete_update()

    def test_get_upgrade_path(self):
        upgrade_path = self._BROKER.get_upgrade_path(1, 60)
        assert upgrade_path is not None
        assert upgrade_path.total_cost is not None
        assert upgrade_path.total_cost > 0
        assert upgrade_path.upgrades[0].ship_id_from == 1
        assert upgrade_path.upgrades[-1].ship_id_to == 60

    def test_get_purchase_path(self):
        purchase_path = self._BROKER.get_purchase_path(1)
        assert purchase_path is not None
        assert len(purchase_path.path.upgrades) == 0
        assert len(purchase_path.path) == 0
        assert purchase_path.start_purchase is not None
        assert purchase_path.start_purchase.ship_id == 1
        assert purchase_path.start_purchase.price_usd > 0

    def test_get_ships(self):
        ships = self._BROKER.get_ships()
        assert ships is not None
        assert len(ships) > 0

    def test_get_upgrades(self):
        upgrades = self._BROKER.get_upgrades()
        assert upgrades is not None
        assert len(upgrades) > 0
