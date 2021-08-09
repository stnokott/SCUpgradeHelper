from datetime import datetime

import pytest

from const import RSI_SCRAPER_STORE_OWNER, RSI_SCRAPER_STORE_URL
from db.entity import UpdateType
from db.manager import EntityManager
from util import CustomLogger

_logger = CustomLogger(__name__)


class TestEntityManager:
    _EM = EntityManager(_logger)

    def test_find_store(self):
        store = self._EM.find_store(RSI_SCRAPER_STORE_OWNER, RSI_SCRAPER_STORE_URL)
        assert store is not None
        assert store.url == RSI_SCRAPER_STORE_URL
        assert store.username == RSI_SCRAPER_STORE_OWNER
        assert store.upgrades is not None

    def test_update_manufacturers(self):
        assert self._EM.update_manufacturers([]) == 0
        with pytest.raises(ValueError):
            self._EM.update_manufacturers([1])

    def test_update_ships(self):
        assert self._EM.update_ships([]) == 0
        with pytest.raises(ValueError):
            self._EM.update_ships([1])

    def test_update_rsi_standalones(self):
        assert self._EM.update_rsi_standalones([]) == 0
        with pytest.raises(ValueError):
            self._EM.update_rsi_standalones([1])

    def test_update_rsi_upgrades(self):
        assert self._EM.update_rsi_upgrades([]) == 0
        with pytest.raises(ValueError):
            self._EM.update_rsi_upgrades([1])

    def test_update_reddit_standalones(self):
        assert self._EM.update_reddit_standalones([]) == 0
        with pytest.raises(ValueError):
            self._EM.update_reddit_standalones([1])

    def test_update_reddit_upgrades(self):
        assert self._EM.update_reddit_upgrades([]) == 0
        with pytest.raises(ValueError):
            self._EM.update_reddit_upgrades([1])

    def test_get_manufacturers(self):
        manufacturers = self._EM.get_manufacturers()
        assert manufacturers is not None
        assert len(manufacturers) > 0

    def test_get_ships(self):
        ships = self._EM.get_ships()
        assert ships is not None
        assert len(ships) > 0

    def test_get_rsi_standalones(self):
        rsi_standalones = self._EM.get_rsi_standalones()
        assert rsi_standalones is not None
        assert len(rsi_standalones) > 0

    def test_get_rsi_upgrades(self):
        rsi_upgrades = self._EM.get_rsi_upgrades()
        assert rsi_upgrades is not None
        assert len(rsi_upgrades) > 0

    def test_get_reddit_standalones(self):
        reddit_standalones = self._EM.get_reddit_standalones()
        assert reddit_standalones is not None

    def test_get_reddit_upgrades(self):
        reddit_upgrades = self._EM.get_reddit_upgrades()
        assert reddit_upgrades is not None

    def test_get_all_standalones(self):
        standalones = self._EM.get_all_standalones(True)
        assert standalones is not None
        assert len(standalones) > 0

    def test_get_all_upgrades(self):
        upgrades = self._EM.get_all_upgrades(True)
        assert upgrades is not None
        assert len(upgrades) > 0

    def test_get_loaddate(self):
        for update_type in [
            UpdateType.SHIPS,
            UpdateType.MANUFACTURERS,
            UpdateType.RSI_UPGRADES,
            UpdateType.RSI_STANDALONES,
            UpdateType.REDDIT_UPGRADES,
            UpdateType.REDDIT_STANDALONES,
        ]:
            loaddate = self._EM.get_loaddate(update_type)
            assert loaddate is None or type(loaddate) == datetime

    def test_find_ship_id_by_name(self):
        exact_matches = ["Gladius", "300i", "890 Jump", "Caterpillar", "Freelancer MAX"]
        approximate_matches = [
            "Aegis Gladius",
            "Great 300i",
            "890 Jump Yacht",
            "Caterpillar Special Deal",
            "Freelance MAXX",
            "Free lancer MA X",
            "F7C-M Heartseeker",
            "F7C Heardseeker",
        ]
        no_matches = [
            "Simple non-match",
            "Special Deal Upgrade",
            "Maximum but not exact",
            "999 Joint",
        ]
        for x in exact_matches + approximate_matches:
            ship_id, needs_review = self._EM.find_ship_id_by_name(x)
            assert ship_id is not None
            assert needs_review is not None
            assert ship_id > 0
            assert type(needs_review) == bool
        for x in no_matches:
            return_val = self._EM.find_ship_id_by_name(x)
            assert return_val is None
