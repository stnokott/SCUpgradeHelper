"""test"""
import logging

from broker import SCDataBroker
from config import ConfigProvider
from util.helpers import CustomLogger

if __name__ == "__main__":
    # TODO: separate refresh threshold for Reddit entries from deletion threshold
    #       (so old ones are kept even when parsing new ones)
    # TODO: add support for adding already existing own upgrades
    # TODO: use Decimal instead of float where possible
    # TODO: add support for finding best way to increase melt value of ship by upgrading (needs to retrieve melt value
    #       from somewhere
    # TODO: needs review entries need to be in separate database to show the original string that was matches against
    logger = CustomLogger(__name__, logging.INFO)

    config = ConfigProvider(logger)
    broker = SCDataBroker(logger, config)
    broker.complete_update(False, True)
    path = broker.get_upgrade_path(216, 150)
    if path is not None:
        path.full_print(logger)
    else:
        logger.info("No upgrade path found.")
