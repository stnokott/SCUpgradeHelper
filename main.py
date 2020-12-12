"""main"""
import logging

from broker import SCDataBroker
from config import ConfigProvider

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    config = ConfigProvider(logger)
    broker = SCDataBroker(logger, config, force_update=True)
    print(broker.get_ships())
