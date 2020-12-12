"""Contains classes for scraping websites"""
from typing import List

import requests
from bs4 import BeautifulSoup

from db.entity import Ship, Manufacturer


class SCToolsScraper:
    __SHIP_LIST_URL = "https://starcitizen.tools/List_of_pledge_vehicles"

    def get_ships(self) -> List[Ship]:
        page = requests.get(self.__SHIP_LIST_URL)
        soup = BeautifulSoup(page.content, "html.parser")
        rows = soup.select("table tbody tr")
        ships = []
        for row in rows:
            try:
                name = row.select_one("td.data-name a").text
                manufacturer_name = row.select_one("td.data-manufacturer a").text
                price = row.select_one(
                    "td.data-standalonecost div.data-standalonecost-value a"
                ).text
                # remove non-digit chars
                numeric_filter = filter(str.isdigit, price)
                price = int("".join(numeric_filter))

                manufacturer = Manufacturer(name=manufacturer_name)
                ship = Ship(name=name, price=price, manufacturer=manufacturer)
                ships.append(ship)
            except AttributeError:
                continue
        return ships
