"""main"""
import logging

from broker import SCDataBroker
from config import ConfigProvider
from util import CustomLogger

if __name__ == "__main__":
    logger = CustomLogger(__name__, logging.DEBUG)

    config = ConfigProvider(logger)
    broker = SCDataBroker(logger, config)
    # broker.complete_update(echo=True)
    # print(broker.get_ships())
