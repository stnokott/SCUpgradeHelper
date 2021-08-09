from datetime import timedelta

from util import format_timedelta, CustomLogger


def test_format_timedelta():
    delta1 = timedelta(days=0)
    assert format_timedelta(delta1) == "00:00:00"
    delta2 = timedelta(days=1)
    assert format_timedelta(delta2) == "1 days, 00:00:00"
    delta3 = timedelta(days=3, hours=4, minutes=59)
    assert format_timedelta(delta3) == "3 days"  # remove hours when more days than x


def test_custom_logger():
    logger = CustomLogger(__name__)
    logger.log("fuuf")
    logger.log("fuuf", CustomLogger.LEVEL_WARN)
    logger.info("feef")
    logger.warning("soos")
    logger.error("meem")
    logger.info(5)
    logger.info(5.2)
    logger.info(CustomLogger("testObjectPrint"))
