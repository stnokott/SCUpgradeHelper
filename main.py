"""main"""
import logging

from config import ConfigProvider
from broker import SCDataBroker

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    config = ConfigProvider(logger)
    broker = SCDataBroker(logger, config)
    print(broker.get_ships())
