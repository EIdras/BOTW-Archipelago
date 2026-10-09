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
# What a climate the game does not let the player through asks for: every group
# must be met, by one of its items. Only the volcano's heart burns Link within
# seconds; cold and desert heat are crossed with food and elixirs, found everywhere.
CLIMATES = {
    "none": (),
    "heat": (("Flamebreaker Set",),),                   # Death Mountain's burning zone
}
GOAL_LOCATION = "Defeat Calamity Ganon"
# The weapons of the filler: a group by its weight, then one of its weapons.
# Its level orders the weapons through the game (the weapon_order option):
# 1 first, 5 last; 0, the jokes, stay wherever the fill put them.
WEAPONS = {
    "medium": (20, 1, ("Soldier's Broadsword", "Soldier's Claymore", "Soldier's Spear", "Soldier's Bow",
                       "Soldier's Shield", "Zora Sword", "Gerudo Scimitar", "Gerudo Spear",
                       "Eightfold Blade", "Silver Bow")),
    "solid": (25, 2, ("Knight's Broadsword", "Knight's Claymore", "Knight's Bow", "Knight's Shield",
                      "Royal Broadsword", "Royal Claymore", "Royal Halberd", "Royal Bow", "Royal Shield")),
    "elemental": (20, 2, ("Flameblade", "Frostblade", "Thunderblade", "Great Flameblade",
                          "Great Frostblade", "Great Thunderblade", "Flamespear", "Frostspear",
                          "Thunderspear", "Fire Rod", "Ice Rod", "Lightning Rod", "Meteor Rod",
                          "Blizzard Rod", "Thunderstorm Rod")),
    # Strong, but they break fast.
    "fragile": (10, 3, ("Royal Guard's Sword", "Royal Guard's Claymore", "Royal Guard's Spear",
                        "Royal Guard's Bow", "Royal Guard's Shield", "Dragonbone Boko Bat",
                        "Dragonbone Moblin Club")),
    "ancient": (10, 3, ("Ancient Short Sword", "Ancient Bladesaw", "Ancient Spear", "Ancient Bow",
                        "Ancient Shield", "Guardian Sword++", "Ancient Battle Axe++", "Guardian Spear++",
                        "Guardian Shield++")),
    "mighty_lynel": (5, 3, ("Mighty Lynel Sword", "Mighty Lynel Crusher", "Mighty Lynel Spear",
                            "Mighty Lynel Bow", "Mighty Lynel Shield")),
    "savage_lynel": (5, 4, ("Savage Lynel Sword", "Savage Lynel Crusher", "Savage Lynel Spear",
                            "Savage Lynel Bow", "Savage Lynel Shield")),
    "special": (5, 3, ("Korok Leaf", "Giant Boomerang", "Sea-Breeze Boomerang", "Duplex Bow",
                       "Phrenic Bow", "Demon Carver", "Windcleaver", "Stone Smasher", "Torch",
                       "Moonlight Scimitar")),
    # The amiibo's: rare, and useful items.
    "treasure": (4, 5, ("Biggoron's Sword", "Fierce Deity Sword", "Sword of the Six Sages",
                        "Goddess Sword", "Sword", "Twilight Bow", "Hero's Shield")),
    "joke": (4, 0, ("Soup Ladle", "Boat Oar", "Farming Hoe", "Wooden Mop", "Tree Branch", "Pot Lid")),
}
WEAPON_LEVELS = {name: level for _weight, level, names in WEAPONS.values() for name in names}
# The generated filler, one draw per slot the other items leave: a family by
# its weight, then one of its items by theirs (smaller sums of rupees more often,
# a weapon by its group's weight).
FILLER = {
    "arrows": (30, {"10 Arrows": 1, "10 Fire Arrows": 1, "10 Ice Arrows": 1, "10 Shock Arrows": 1,
                    "10 Bomb Arrows": 1, "5 Ancient Arrows": 1}),
    "elixirs": (25, {name: 1 for name in (
        "Hasty Elixir", "Electro Elixir", "Tough Elixir", "Hearty Elixir", "Fireproof Elixir",
        "Chilly Elixir", "Spicy Elixir", "Mighty Elixir", "Sneaky Elixir", "Energizing Elixir",
        "Enduring Elixir", "Fairy Tonic")}),
    "weapons": (25, {name: weight / len(names) for weight, _level, names in WEAPONS.values()
                     for name in names}),
    "gems": (10, {name: 1 for name in ("Diamond", "Ruby", "Sapphire", "Topaz", "Opal", "Amber")}),
    "rupees": (10, {"Blue Rupee": 30, "Red Rupee": 35, "Purple Rupee": 20, "Silver Rupee": 10,
                    "Gold Rupee": 5}),
}
PLATEAU_RUNES = {name: row["runes"] for name, row in LOGIC.items()
                 if name in ("Oman Au Shrine", "Ja Baij Shrine", "Owa Daim Shrine", "Keh Namut Shrine")}
# The map of each region but the Great Plateau, an item: {region: item}. A tower
# reveals the area of the game's map named after it (tools/map_regions.py); with
# tower_maps on region_keys, a region's locations are in logic once its map is in.
MAPS = {row["name"][:-len(" Map")]: row["name"] for row in ITEMS if "Map" in row.get("category", ())}
# Regions whose locations need no map: the Plateau, where the game starts, and
# Hyrule Castle (Ganon), which the sanctum's own options gate.
MAPLESS_REGIONS = frozenset({"Great Plateau", "Hyrule Castle"})
# The maps a starting_map of "gentle" draws from: the regions the game itself
# leads to first, from the Plateau to Kakariko, Hateno and Lake Hylia.
GENTLE_REGIONS = ("Dueling Peaks", "Hateno", "Lake", "Faron")


def categories(row: dict) -> set[str]:
    """Exact categories of a row. The CSV stores them as one "|"-separated
    string: a substring test would make "Divine Beast Heart" a Divine Beast."""
    return {name for name in row["category"].split("|") if name}


def requirements(row: dict) -> tuple[tuple[tuple[str, ...], int], ...]:
    """What reaching a location takes: groups that must all be met, each by one
    of its items, `count` times. Outside the Great Plateau, the Paraglider; then
    its row of data/logic.csv. In its runes and extra, "|" separates what is all
    needed and "/" the ways of which one is enough ("Magnesis/Stasis"). A player
    may always do more than the logic asks (elixirs instead of armour): the logic
    only promises what it can rely on."""
    logic = LOGIC[row["name"]]
    groups = [] if row["region"] == "Great Plateau" else [(("Paraglider",), 1)]
    groups += [(names, 1) for names in CLIMATES[logic["climate"]]]
    runes = logic["runes"]
    groups += [(tuple(group.split("/")), 1) for group in
               (RUNES if runes == "all" else () if runes in ("", "none") else runes.split("|"))]
    for item in filter(None, logic["extra"].split("|")):
        names, _, count = item.partition(":")
        if names not in MAPS.values():          # maps: map_keys()
            groups.append((tuple(names.split("/")), int(count or 1)))
    return tuple(groups)


def map_keys(row: dict) -> tuple[str, ...]:
    """The maps a location asks for when the maps are region keys: its region's,
    but for a tower and the mapless regions, then any its logic.csv extra names
    (a quest that goes through another region)."""
    own = () if row["region"] in MAPLESS_REGIONS or "Tower" in categories(row) else (MAPS[row["region"]],)
    extra = tuple(name for name in LOGIC[row["name"]]["extra"].split("|") if name in MAPS.values())
    return own + tuple(name for name in extra if name not in own)


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
    regions = {row["region"] for row in LOCATIONS}
    if set(MAPS) != regions - MAPLESS_REGIONS:
        raise ValueError(f"the maps differ from the regions: {sorted(set(MAPS) ^ (regions - MAPLESS_REGIONS))}")
    for row in LOCATIONS:
        logic = LOGIC[row["name"]]
        if logic["region"] != row["region"]:
            raise ValueError(f"{row['name']}: data/logic.csv says {logic['region']}, the locations {row['region']}")
        if logic["climate"] not in CLIMATES:
            raise ValueError(f"{row['name']}: unknown climate {logic['climate']!r}")
        runes = logic["runes"]
        if runes not in ("", "none", "all") and not set(runes.replace("/", "|").split("|")) <= set(RUNES):
            raise ValueError(f"{row['name']}: unknown runes {runes!r}")
        unknown = required_items(row) - items - events
        if unknown:
            raise ValueError(f"{row['name']}: unknown requirement {sorted(unknown)}")


def _check_weapons() -> None:
    """WEAPONS names exactly the items of the Weapon category."""
    weapons = {row["name"] for row in ITEMS if "Weapon" in row.get("category", ())}
    if set(WEAPON_LEVELS) != weapons or sum(len(names) for _, _, names in WEAPONS.values()) != len(weapons):
        raise ValueError(f"WEAPONS differs from the Weapon items: {sorted(set(WEAPON_LEVELS) ^ weapons)[:5]}")


_check_logic()
_check_weapons()
