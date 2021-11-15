from data.analyze import PathAnalyzer
from db.manager import EntityManager
from util.helpers import CustomLogger


def test_path_analyzer():
    logger = CustomLogger(__name__)
    em = EntityManager(logger, "test_database.db")
    path_analyzer = PathAnalyzer(em, logger)
    assert path_analyzer.get_upgrade_path(1, 60) is None
    assert path_analyzer.get_purchase_path(1) is None
    path_analyzer.update()
    assert path_analyzer.get_upgrade_path(1, 60) is not None
    assert path_analyzer.get_purchase_path(1) is not None
