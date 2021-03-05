"""main"""
import logging

from broker import SCDataBroker
from config import ConfigProvider

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())

    config = ConfigProvider(logger)
    broker = SCDataBroker(logger, config)
    # broker.complete_update(echo=True)
    print(broker.get_ships())
    # reddit = RedditScraper(config.reddit_client_id, config.reddit_client_secret, logger)
