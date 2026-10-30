"""The regions Link may enter with region_lock (slot data), as the world's logic
opens them (botw_world/__init__.py connect_neighbours; the PopTracker pack's
reached_regions does the same): the Great Plateau, where the game starts; with
the Paraglider, a region whose map is held, across the seed's open borders
(slot data region_borders), outward from the Plateau; with map_travel_points,
any region whose map is held (its travel point is warped to); Hyrule Castle,
inside Central's area, with Central.

Read from the game's flags (a map's MapTower_NN, the Paraglider's IsGet_), not
from the items received: a reload to an earlier save closes again what that
save had not. The regions are named as the map's areas (data/region_borders.json,
tools/map_regions.py): those not reached are closed.
"""
from __future__ import annotations

from typing import Callable

from .travel_points import PARAGLIDER

PLATEAU = "Great Plateau"
# A region inside another's area, entered from it (botw_world/catalog.py).
INNER_REGIONS = {"Hyrule Castle": "Central"}


def map_flags(item_map: dict) -> dict[str, str]:
    """{region: its map's flag}: the item map's maps, "<region> Map"."""
    return {name.removesuffix(" Map"): entry["delivery"]["flag"]
            for name, entry in item_map.items() if entry["delivery"]["kind"] == "map"}


def reached(slot_data: dict, get: Callable, maps: dict[str, str]) -> frozenset[str] | None:
    """The regions Link may enter; None without region_lock, or while a flag is
    unreadable (a loading): nothing is closed then. get(flag, kind): the live
    value, None unreadable; maps: map_flags'."""
    if not slot_data.get("region_lock"):
        return None
    found = {PLATEAU}
    paraglider = get(PARAGLIDER, "bool")
    if paraglider is None:
        return None
    if paraglider:
        held = set()
        for region, flag in maps.items():
            value = get(flag, "bool")
            if value is None:
                return None
            if value:
                held.add(region)
        if slot_data.get("map_travel_points"):
            found |= held
        borders = [tuple(pair) for pair in slot_data.get("region_borders", ())]
        grown = True
        while grown:
            grown = False
            for ends in borders:
                for here, there in (ends, ends[::-1]):
                    if here in found and there not in found and there in held:
                        found.add(there)
                        grown = True
    found |= {inner for inner, outer in INNER_REGIONS.items() if outer in found}
    return frozenset(found)
