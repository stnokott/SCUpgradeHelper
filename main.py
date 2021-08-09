"""test"""
import logging

from broker import SCDataBroker
from config import ConfigProvider
from util import CustomLogger

if __name__ == "__main__":
    # TODO: add support for adding already existing own upgrades
    # TODO: use Decimal instead of float where possible
    logger = CustomLogger(__name__, logging.INFO)

    config = ConfigProvider(logger)
    broker = SCDataBroker(logger, config)
    broker.complete_update(False, True)
    path = broker.get_purchase_path(22)
    if path is not None:
        # path.full_print(logger)
        print(path)
    else:
        logger.info("No upgrade path found.")
