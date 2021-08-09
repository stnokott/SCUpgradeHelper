from config import ConfigProvider
from data.api import SCApi
from util import CustomLogger


def test_sc_api():
    logger = CustomLogger(__name__)
    config_provider = ConfigProvider(logger)
    sc_api = SCApi(config_provider.sc_api_key, logger)
    ships = sc_api.get_ships()
    assert ships is not None
    assert len(ships) > 0
