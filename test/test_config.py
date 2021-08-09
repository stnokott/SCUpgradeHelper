import os

from config import ConfigProvider
from const import CONFIG_FILEPATH
from util import CustomLogger


class TestConfigProvider:
    _MAIN_DIR = os.path.abspath(os.path.join(os.getcwd(), ".."))
    _TMP_DIR = os.path.join(_MAIN_DIR, "tmp")
    _MAIN_CONFIG_FILE_PATH = os.path.join(_MAIN_DIR, CONFIG_FILEPATH)
    _TMP_CONFIG_FILE_PATH = os.path.join(_TMP_DIR, CONFIG_FILEPATH)

    @classmethod
    def _hide_config_file(cls):
        if not os.path.exists(cls._TMP_DIR):
            os.mkdir(cls._TMP_DIR)
        if os.path.exists(os.path.join(cls._MAIN_DIR, CONFIG_FILEPATH)):
            # move file first to test behaviour when file doesnt exist
            os.rename(
                cls._MAIN_CONFIG_FILE_PATH,
                cls._TMP_CONFIG_FILE_PATH,
            )
        assert not os.path.exists(cls._MAIN_CONFIG_FILE_PATH)

    @classmethod
    def _unhide_config_file(cls):
        if os.path.exists(cls._MAIN_CONFIG_FILE_PATH) and os.path.exists(
            cls._TMP_CONFIG_FILE_PATH
        ):
            os.remove(cls._MAIN_CONFIG_FILE_PATH)
        os.rename(cls._TMP_CONFIG_FILE_PATH, cls._MAIN_CONFIG_FILE_PATH)
        assert os.path.exists(cls._MAIN_CONFIG_FILE_PATH)
        assert not os.path.exists(cls._TMP_CONFIG_FILE_PATH)

    @classmethod
    def _delete_tmp_dir(cls):
        os.rmdir(cls._TMP_DIR)

    def test_config_file_not_existing(self):
        self._hide_config_file()
        config_provider = ConfigProvider(CustomLogger(__name__))
        assert os.path.exists(self._MAIN_CONFIG_FILE_PATH)
        assert config_provider.sc_api_key is None
        assert config_provider.reddit_client_id is None
        assert config_provider.reddit_client_secret is None
        self._unhide_config_file()
        self._delete_tmp_dir()

    def test_config_file_existing(self):
        self._hide_config_file()
        with open(self._MAIN_CONFIG_FILE_PATH, "w") as config_file:
            config_file.write(
                """
                [AUTH]
                scapikey=abc123
                redditclientid=def456
                redditclientsecret=ghi789
            """
            )
        config_provider = ConfigProvider(CustomLogger(__name__))
        assert config_provider.sc_api_key == "abc123"
        assert config_provider.reddit_client_id == "def456"
        assert config_provider.reddit_client_secret == "ghi789"
        self._unhide_config_file()
        self._delete_tmp_dir()
