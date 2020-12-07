"""main"""
import logging

from data.api import SCApi, ShipDataProvider
from config import ConfigProvider
from data.provider import DataProviderManager, DataProviderType
from db.util import EntityManager

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())

    config = ConfigProvider(logger)
    scapi = SCApi(config.sc_api_key, logger)
    data_provider_manager = DataProviderManager()
    data_provider_manager.add_data_provider(DataProviderType.SHIPS, ShipDataProvider(scapi, logger))
    em = EntityManager(data_provider_manager, logger)
    print(em.get_ships())
