"""Explicit, append-only IDs and the logic, independent of AP imports."""
import csv
import json
from importlib.resources import files

GAME = "Breath of the Wild"
# The project's version, written into each seed's slot data for the client to compare.
WORLD_VERSION = json.loads(files(__package__).joinpath("archipelago.json").read_text(encoding="utf-8"))["world_version"]
LOCATIONS = json.loads(files(__package__).joinpath("data/locations.json").read_text(encoding="utf-8"))
ITEMS = json.loads(files(__package__).joinpath("data/items.json").read_text(encoding="utf-8"))
RUNES = ("Magnesis", "Remote Bomb", "Stasis", "Cryonis")
TRAPS = tuple(row["name"] for row in ITEMS if row.get("trap"))
# What reaching each location takes in the game (data/logic.csv, one row each):
# the climate to cross, the runes its shrine cannot be done without, and any
# other item or event.
LOGIC = {row["location"]: row for row in csv.DictReader(
    files(__package__).joinpath("data/logic.csv").read_text(encoding="utf-8").splitlines())}
# The armour each climate asks for: every group must be met, by one of its items.
CLIMATES = {
    "none": (),
    "heat": (("Flamebreaker Set",),),                   # Death Mountain
    "desert": (("Desert Voe Set",),),                   # the Gerudo Desert by day
    "cold": (("Warm Doublet", "Snowquill Set"),),       # Gerudo Highlands, Mount Lanayru, Tabantha's peaks
    "cold_extreme": (("Snowquill Set",),),              # Hebra
    "?": (("Desert Voe Set",), ("Snowquill Set",)),     # not told yet: the strictest
}
GOAL_LOCATION = "Defeat Calamity Ganon"
PLATEAU_RUNES = {name: row["runes"] for name, row in LOGIC.items()
                 if name in ("Oman Au Shrine", "Ja Baij Shrine", "Owa Daim Shrine", "Keh Namut Shrine")}


def categories(row: dict) -> set[str]:
    """Exact categories of a row. The CSV stores them as one "|"-separated
    string: a substring test would make "Divine Beast Heart" a Divine Beast."""
    return {name for name in row["category"].split("|") if name}


def requirements(row: dict) -> tuple[tuple[tuple[str, ...], int], ...]:
    """What reaching a location takes: groups that must all be met, each by one
    of its items, `count` times. Outside the Great Plateau, the Paraglider; then
    its row of data/logic.csv. A player may always do more than the logic asks
    (elixirs instead of armour): the logic only promises what it can rely on."""
    logic = LOGIC[row["name"]]
    groups = [] if row["region"] == "Great Plateau" else [(("Paraglider",), 1)]
    groups += [(names, 1) for names in CLIMATES[logic["climate"]]]
    runes = logic["runes"]
    groups += [((rune,), 1) for rune in (RUNES if runes == "all" else () if runes in ("", "none")
                                          else runes.split("|"))]
    for item in filter(None, logic["extra"].split("|")):
        name, _, count = item.partition(":")
        groups.append(((name,), int(count or 1)))
    return tuple(groups)


def required_items(row: dict) -> set[str]:
    """Every item or event named by a location's requirements."""
    return {name for names, _ in requirements(row) for name in names}


def _check_logic() -> None:
    """Every location has a valid row: a typo in data/logic.csv fails at load."""
    names = {row["name"] for row in LOCATIONS}
    if set(LOGIC) != names:
        raise ValueError(f"data/logic.csv rows differ from the locations: "
                         f"{sorted(set(LOGIC) ^ names)[:5]}")
    items = {row["name"] for row in ITEMS}
    events = {f"Freed - {row['name']}" for row in LOCATIONS if "Divine Beast" in categories(row)}
    for row in LOCATIONS:
        logic = LOGIC[row["name"]]
        if logic["climate"] not in CLIMATES:
            raise ValueError(f"{row['name']}: unknown climate {logic['climate']!r}")
        runes = logic["runes"]
        if runes not in ("", "none", "all") and not set(runes.split("|")) <= set(RUNES):
            raise ValueError(f"{row['name']}: unknown runes {runes!r}")
        unknown = required_items(row) - items - events
        if unknown:
            raise ValueError(f"{row['name']}: unknown requirement {sorted(unknown)}")


_check_logic()
