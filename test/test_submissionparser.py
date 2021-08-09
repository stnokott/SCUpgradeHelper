import pytest

from data.scraper.submissionparser import (
    ParsedRedditSubmissionEntry,
)
from db.entity import UpdateType


def test_parse_price_string():
    price_tuples = [
        ("a", None),
        ("abc", None),
        ("a1", None),
        ("5..2", None),
        ("abc123", None),
        ("1.0", 1.0),
        ("2", 2.0),
        ("$3", 3.0),
        ("$3.5", 3.5),
        ("$ 4.50", 4.5),
        ("$ 6.79 ", 6.79),
        ("7.50 $", 7.5),
        ("$15.20 / €22", 15.2),
        ("15.20€ | $21.5", 21.5),
    ]
    for price_tuple in price_tuples:
        parsed_result = ParsedRedditSubmissionEntry._parse_price_string(price_tuple[0])
        if parsed_result is None:
            assert price_tuple[1] is None
        else:
            assert price_tuple[1] == parsed_result


def test_parsed_submission_entry():
    sample_price = "$20.5"
    sample_store_owner = "mysimplestoreowner"
    sample_store_url = "https://safebrowsing.com"
    sample_submission = ParsedRedditSubmissionEntry(
        UpdateType.REDDIT_STANDALONES,
        sample_price,
        sample_store_owner,
        sample_store_url,
        ship_name="Avenger",
    )
    assert sample_submission.update_type == UpdateType.REDDIT_STANDALONES
    assert sample_submission.price_usd == 20.5
    assert sample_submission.store_owner == sample_store_owner
    assert sample_submission.store_url == sample_store_url
    with pytest.raises(ValueError):
        # missing ship_names
        ParsedRedditSubmissionEntry(
            UpdateType.REDDIT_STANDALONES,
            sample_price,
            sample_store_owner,
            sample_store_url,
        )
        # including ship_name & ship_name_from
        ParsedRedditSubmissionEntry(
            UpdateType.REDDIT_STANDALONES,
            sample_price,
            sample_store_owner,
            sample_store_url,
            ship_name="fuuf",
            ship_name_from="soos",
        )
        # including ship_name_from, but not ship_name_to
        ParsedRedditSubmissionEntry(
            UpdateType.REDDIT_STANDALONES,
            sample_price,
            sample_store_owner,
            sample_store_url,
            ship_name_from="soos",
        )
        # Type Standalone, but kwargs for Upgrade
        ParsedRedditSubmissionEntry(
            UpdateType.REDDIT_STANDALONES,
            sample_price,
            sample_store_owner,
            sample_store_url,
            ship_name_from="soos",
            ship_name_to="fuuf",
        )
        # Type Upgrade, but kwargs for Standalone
        ParsedRedditSubmissionEntry(
            UpdateType.REDDIT_UPGRADES,
            sample_price,
            sample_store_owner,
            sample_store_url,
            ship_name="Avenger",
        )
        # Type Upgrade, but without ship name
        ParsedRedditSubmissionEntry(
            UpdateType.REDDIT_UPGRADES,
            sample_price,
            sample_store_owner,
            sample_store_url,
        )
