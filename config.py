"""contains config classes"""

import configparser
import logging
import os

from const import CONFIG_FILEPATH

DEFAULT_VALUES = {"AUTH": {"SCApiKey": ""}}


class ConfigProvider:
    """
    Provides configuration data from config file
    """
    def __init__(self, logger: logging.Logger):
        self._ensure_file_exists()
        self._config = configparser.ConfigParser()
        self._config.read(CONFIG_FILEPATH)

        # read AUTH section
        auth_section = self._get_section("AUTH")
        self.sc_api_key = auth_section["scapikey"]
        self.reddit_client_id = auth_section["redditclientid"]
        self.reddit_client_secret = auth_section["redditclientsecret"]
        logger.info("Configuration parsed.")

    def _get_section(self, section_name: str) -> configparser.SectionProxy:
        # check if section exists
        if not self._config.has_section(section_name):
            self._config[section_name] = DEFAULT_VALUES[section_name]
            self._write_config(self._config)
            # return immediately with default values if not exists
            return self._config[section_name]

        # retrieve section values
        section = self._config[section_name]
        expected_section_keys = DEFAULT_VALUES[section_name].keys()
        actual_section_keys = section.keys()
        changed = False
        # check if each key exists
        for expected_key in expected_section_keys:
            if expected_key not in actual_section_keys:
                # add key with default value if not exists
                section[expected_key] = DEFAULT_VALUES[section_name][expected_key]
                changed = True
        if changed:
            # save changes to file if needed
            self._write_config(self._config)
        return section

    @classmethod
    def _ensure_file_exists(cls) -> None:
        if os.path.exists(CONFIG_FILEPATH):
            return
        # create config object with default values
        config = configparser.ConfigParser()
        for section_name in DEFAULT_VALUES:
            config[section_name] = DEFAULT_VALUES[section_name]
        # save to file
        cls._write_config(config)

    @classmethod
    def _write_config(cls, config: configparser.ConfigParser) -> None:
        with open(os.path.join(os.getcwd(), CONFIG_FILEPATH), "w") as config_file:
            config.write(config_file)
