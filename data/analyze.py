from typing import List, Optional

from dijkstra import DijkstraSPF, Graph

from db.entity import Upgrade, Standalone
from db.manager import EntityManager
from util import CustomLogger


class UpgradePath:
    def __init__(self, upgrades: List[Upgrade]):
        self.upgrades = upgrades
        self.total_cost = sum([upgrade.price_usd for upgrade in self.upgrades])

    def __len__(self):
        return len(self.upgrades)

    def __repr__(self):
        s_summary = (
            f"{self.upgrades[0].ship_from.name} -> {self.upgrades[-1].ship_to.name}"
        )
        step_count = len(self)
        s_step_count = f"{step_count} step{'s' if step_count > 1 else ''}"
        store_count = len(set([u.store.username for u in self.upgrades]))
        s_store_count = f"across {store_count} store{'s' if store_count > 1 else ''}"
        s_total_cost = f"${self.total_cost}"
        s = f"<{UpgradePath.__name__}>([{s_summary}]: {s_step_count} {s_store_count}, total {s_total_cost})"
        return s


class PurchasePath:
    def __init__(self, start: Standalone, path: UpgradePath):
        self.start_purchase = start
        self.path = path

    def __repr__(self):
        target_ship = (
            self.path.upgrades[-1].ship_to
            if len(self.path.upgrades) > 0
            else self.start_purchase.ship
        )
        s_summary = f"Target: {target_ship.name}"
        step_count = 1 + len(self.path)
        s_step_count = f"{step_count} step{'s' if step_count > 1 else ''}"
        total_cost = self.start_purchase.price_usd + self.path.total_cost
        s = f"<{PurchasePath.__name__}>([{s_summary}], {s_step_count}, total ${total_cost})"
        return s


_SHIP_ID_NONE = 0


class PathAnalyzer:
    def __init__(self, entity_manager: EntityManager, logger: CustomLogger):
        self._em = entity_manager
        self._logger = logger
        self._graph = Graph()
        self._standalones = []
        self._upgrades = []

    def update(self):
        self._graph = Graph()
        self._standalones = self._em.get_all_standalones(include_unconfirmed=False)
        self._upgrades = self._em.get_all_upgrades(include_unconfirmed=False)

        # Add upgrade paths from None to Standalone
        for standalone in self._standalones:
            self._graph.add_edge(
                _SHIP_ID_NONE, standalone.ship_id, standalone.price_usd
            )

        # Add upgrade paths for Upgrades
        for upgrade in self._upgrades:
            self._graph.add_edge(
                upgrade.ship_id_from, upgrade.ship_id_to, upgrade.price_usd
            )

    def _resolve_standalone(self, ship_id: int, price_usd: float) -> Standalone:
        candidates = list(
            filter(
                lambda s: s.ship_id == ship_id and s.price_usd == price_usd,
                self._standalones,
            )
        )
        if len(candidates) == 0:
            raise ValueError("Candidate could not be resolved!")
        candidates.sort(key=lambda s: s.price_usd)
        return candidates[0]

    def _resolve_upgrade(
        self, ship_id_from: int, ship_id_to: int, price_usd: float
    ) -> Upgrade:
        candidates = list(
            filter(
                lambda s: s.ship_id_from == ship_id_from
                and s.ship_id_to == ship_id_to
                and s.price_usd == price_usd,
                self._upgrades,
            )
        )
        if len(candidates) == 0:
            raise ValueError("Candidate could not be resolved!")
        candidates.sort(key=lambda s: s.price_usd)
        return candidates[0]

    def _resolve_upgrade_path(self, path: List[int], dspf: DijkstraSPF) -> UpgradePath:
        upgrades: List[Upgrade] = []
        i = 0
        while i + 1 < len(path):
            ship_id_from = path[i]
            ship_id_to = path[i + 1]
            upgrades.append(
                self._resolve_upgrade(
                    ship_id_from,
                    ship_id_to,
                    dspf.get_edge_weight(self._graph, ship_id_from, ship_id_to),
                )
            )
            i += 1
        return UpgradePath(upgrades)

    def get_upgrade_path(
        self, start_ship_id: int, target_ship_id: int
    ) -> Optional[UpgradePath]:
        if start_ship_id == _SHIP_ID_NONE:
            raise ValueError(
                f"Invalid <start_ship_id>={_SHIP_ID_NONE}, "
                f"please use {self.get_upgrade_path.__name__}() instead."
            )

        dspf = DijkstraSPF(self._graph, start_ship_id)
        try:
            upgrade_path = dspf.get_path(target_ship_id)
        except KeyError:
            return None
        return self._resolve_upgrade_path(upgrade_path, dspf)

    def get_purchase_path(self, target_ship_id: int) -> Optional[PurchasePath]:
        dspf = DijkstraSPF(self._graph, _SHIP_ID_NONE)
        path = dspf.get_path(target_ship_id)
        starting_standalone = self._resolve_standalone(
            path[1], dspf.get_edge_weight(self._graph, path[0], path[1])
        )
        try:
            upgrade_path = self._resolve_upgrade_path(path[1:], dspf)
        except KeyError:
            return None
        return PurchasePath(starting_standalone, upgrade_path)
