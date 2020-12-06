"""main"""
from api import SCApi
from config import ConfigProvider
from db.util import EntityManager

if __name__ == '__main__':
    em = EntityManager()
    config = ConfigProvider()
    api = SCApi(config.sc_api_key)
    print(api.get_ships())
