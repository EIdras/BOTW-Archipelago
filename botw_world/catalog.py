"""Explicit, append-only IDs and the logic, independent of AP imports."""
import csv
import json
from importlib.resources import files

GAME = "Breath of the Wild"
# The project's version, written into each seed's slot data for the client to compare.
WORLD_VERSION = json.loads(files(__package__).joinpath("archipelago.json").read_text(encoding="utf-8"))["world_version"]
LOCATIONS = json.loads(files(__package__).joinpath("data/locations.json").read_text(encoding="utf-8"))
ITEMS = json.loads(files(__package__).joinpath("data/items.json").read_text(encoding="utf-8"))
RUNES = ("Magnesis", "Progressive Remote Bomb", "Progressive Stasis", "Cryonis")
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
# The maps an early_map of "gentle" draws from: the regions the game itself
# leads to first, from the Plateau to Kakariko, Hateno and Lake Hylia.
GENTLE_REGIONS = ("Dueling Peaks", "Hateno", "Lake", "Faron")
# Where two regions touch on the game's map, and the border's length in world
# units (data/region_borders.json, from tools/map_regions.py). With region_lock,
# the logic enters a region from its neighbours.
BORDERS = json.loads(files(__package__).joinpath("data/region_borders.json").read_text(encoding="utf-8"))
# The borders of the game's map the logic does not cross, and why. Where only one
# way is hard, the easy one opens nothing the region's other borders do not.
CLOSED_BORDERS = {
    frozenset({"Akkala", "Woodland"}): "a line of stray cells of Akkala's area on the Woodland-Eldin border, "
                                       "outside the playable area",
    frozenset({"Gerudo", "Tabantha"}): "mostly outside the playable area, across a deep ravine: no way the game leads",
    frozenset({"Central", "Gerudo"}): "Central to Gerudo means climbing the whole ravine under the Gerudo Highlands",
    frozenset({"Hebra", "Ridgeland"}): "Ridgeland to Hebra takes a glide over a chasm, then a climb that wants "
                                       "more stamina than the logic counts",
}
OPEN_BORDERS = tuple(tuple(row["regions"]) for row in BORDERS if frozenset(row["regions"]) not in CLOSED_BORDERS)
# {region: its neighbours}, across the open borders.
NEIGHBOURS = {name: frozenset(other for pair in OPEN_BORDERS if name in pair for other in pair if other != name)
              for name in sorted({name for pair in OPEN_BORDERS for name in pair})}
# The shrine whose travel point a region's map opens with map_travel_points: one
# near where the region begins, open from the start: its terminal is the plain
# one, not the one of the shrines a quest raises (Kam Urog, Sheem Dagoze...), and
# the game lets a program write its flags (IsProgramWritable: not Jee Noh's Location_).
TRAVEL_SHRINES = {
    "Akkala": "Ze Kasho Shrine", "Central": "Kaam Ya'tak Shrine", "Dueling Peaks": "Bosh Kala Shrine",
    "Eldin": "Tah Muhl Shrine", "Faron": "Shoda Sah Shrine", "Gerudo": "Kuh Takkar Shrine",
    "Hateno": "Myahm Agana Shrine", "Hebra": "Rin Oyaa Shrine", "Lake": "Ya Naga Shrine",
    "Lanayru": "Kaya Wan Shrine", "Ridgeland": "Mogg Latan Shrine", "Tabantha": "Tena Ko'sah Shrine",
    "Wasteland": "Kay Noh Shrine", "Woodland": "Monya Toma Shrine",
}
# The flag a travel shrine's terminal sets once activated, with Open_ and Location_
# of the shrine: its actor and HashId in the map's units, as the client opens it.
TRAVEL_TERMINALS = {shrine: f"MainField_DgnObj_EntranceTerminal_A_01_{hash_id}" for shrine, hash_id in {
    "Ze Kasho Shrine": 4290992176, "Kaam Ya'tak Shrine": 2263739210, "Bosh Kala Shrine": 2462652737,
    "Tah Muhl Shrine": 1379190536, "Shoda Sah Shrine": 1797433301, "Kuh Takkar Shrine": 3572795101,
    "Myahm Agana Shrine": 4206609530, "Rin Oyaa Shrine": 2536831938, "Ya Naga Shrine": 2041042482,
    "Kaya Wan Shrine": 2501247945, "Mogg Latan Shrine": 742860559, "Tena Ko'sah Shrine": 3614581704,
    "Kay Noh Shrine": 3305154705, "Monya Toma Shrine": 3304413740,
}.items()}
# A region inside another's area, entered from it: Ganon's sanctum stands in Central's.
INNER_REGIONS = {"Hyrule Castle": "Central"}


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
    areas = regions - set(INNER_REGIONS)
    if {name for row in BORDERS for name in row["regions"]} != areas or not set(INNER_REGIONS.values()) <= areas:
        raise ValueError("data/region_borders.json and INNER_REGIONS differ from the regions")
    if not set(CLOSED_BORDERS) <= {frozenset(row["regions"]) for row in BORDERS}:
        raise ValueError("a closed border is not a border of data/region_borders.json")
    shrines = {row["name"]: row for row in LOCATIONS if "Shrine" in categories(row)}
    if set(TRAVEL_SHRINES) != set(MAPS) or any(
            name not in shrines or shrines[name]["region"] != region for region, name in TRAVEL_SHRINES.items()):
        raise ValueError("TRAVEL_SHRINES names a shrine of each map's region")
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
