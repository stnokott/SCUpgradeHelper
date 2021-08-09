import os
import sys

import pytest

from const import CONFIG_FILEPATH

if __name__ == "__main__":
    config_file_dir = os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    )
    config_file_path = os.path.join(config_file_dir, CONFIG_FILEPATH)
    if not os.path.exists(config_file_path):
        sc_api_key = sys.argv[0]
        reddit_client_id = sys.argv[1]
        reddit_client_secret = sys.argv[2]
        with open(config_file_path, "w") as config_file:
            config_file.write(
                f"""
            [AUTH]
            scapikey={sc_api_key}
            redditclientid={reddit_client_id}
            redditclientsecret={reddit_client_secret}
            """
            )

    retcode = pytest.main()
