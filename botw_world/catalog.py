"""Explicit, append-only IDs and conservative logic, independent of AP imports."""
import json
from importlib.resources import files

GAME = "Breath of the Wild"
LOCATIONS = json.loads(files(__package__).joinpath("data/locations.json").read_text(encoding="utf-8"))
ITEMS = json.loads(files(__package__).joinpath("data/items.json").read_text(encoding="utf-8"))
RUNES = ("Magnesis", "Remote Bomb", "Stasis", "Cryonis")
PLATEAU_RUNES = {"Oman Au Shrine": "Magnesis", "Ja Baij Shrine": "Remote Bomb",
                  "Owa Daim Shrine": "Stasis", "Keh Namut Shrine": "Cryonis"}
BEAST_QUESTS = {"Voo Lota Shrine": "Freed - Divine Beast Vah Medoh",
                "Bareeda Naag Shrine": "Freed - Divine Beast Vah Medoh",
                "Raqa Zunzo Shrine": "Freed - Divine Beast Vah Naboris"}
# The heart container appears in the Divine Beast once its boss is beaten
# (map LinkTagAnd "Create" on Clear_RemainsX); picking it up sets the check.
BEAST_HEARTS = {"Vah Ruta Heart Container": "Freed - Divine Beast Vah Ruta",
                "Vah Rudania Heart Container": "Freed - Divine Beast Vah Rudania",
                "Vah Medoh Heart Container": "Freed - Divine Beast Vah Medoh",
                "Vah Naboris Heart Container": "Freed - Divine Beast Vah Naboris"}
GOAL_LOCATION = "Defeat Calamity Ganon"


def categories(row: dict) -> set[str]:
    """Exact categories of a row. The CSV stores them as one "|"-separated
    string: a substring test would make "Divine Beast Heart" a Divine Beast."""
    return {name for name in row["category"].split("|") if name}


def requirements(row: dict) -> tuple[str, ...]:
    """Sufficient ability requirements; vanilla equipment/food remain obtainable.

    Terminals are entrance checks, distinct from the rune-gated final altars.
    Non-Plateau shrines conservatively require all four runes. This baseline
    deliberately does not claim a minimal per-puzzle route or glitch logic.
    """
    name = row["name"]
    if name in PLATEAU_RUNES:
        return (PLATEAU_RUNES[name],)
    if row["region"] == "Great Plateau":
        return ()
    needed = ["Paraglider"]
    if categories(row) & {"Shrine", "Divine Beast"} or name == GOAL_LOCATION:
        needed.extend(RUNES)
    if name in BEAST_QUESTS:
        needed.append(BEAST_QUESTS[name])
    if name in BEAST_HEARTS:
        needed.append(BEAST_HEARTS[name])
    return tuple(needed)
