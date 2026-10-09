"""Player options of the Breath of the Wild world."""
from dataclasses import dataclass

from Options import (Choice, DeathLink, OptionCounter, OptionGroup, PerGameCommonOptions, Range,
                     StartInventoryPool, Toggle)

from .catalog import TRAPS


class Goal(Choice):
    """What finishes your game.
    ganon: defeat Calamity Ganon, in Hyrule Castle's sanctum (see the Sanctum options).
    divine_beasts: free the four Divine Beasts.
    shrines: clear the number of shrines of Goal Shrines."""
    display_name = "Goal"
    option_ganon = 0
    option_divine_beasts = 1
    option_shrines = 2
    default = 0


class GoalShrines(Range):
    """The shrines to clear, with the shrines goal."""
    display_name = "Goal Shrines"
    range_start = 1
    range_end = 120
    default = 60


class SanctumDivineBeasts(Range):
    """Hyrule Castle's sanctum, where Ganon waits, stays sealed until this many
    Divine Beasts are freed (entering it sends Link back; the Archipelago journal
    says what is missing). 0: not asked."""
    display_name = "Sanctum: Divine Beasts"
    range_start = 0
    range_end = 4
    default = 2


class SanctumShrines(Range):
    """The sanctum stays sealed until this many shrines are cleared. 0: not asked."""
    display_name = "Sanctum: Shrines"
    range_start = 0
    range_end = 120
    default = 0


class SanctumMasterSword(Toggle):
    """The sanctum stays sealed until the Master Sword is received."""
    display_name = "Sanctum: Master Sword"
    default = 1


class SanctumRunes(Toggle):
    """The sanctum stays sealed until the four runes (Magnesis, Remote Bomb, Stasis,
    Cryonis) are received."""
    display_name = "Sanctum: Runes"
    default = 1


class BeedleShopItems(Range):
    """Items of Beedle's stock that become Archipelago locations, at each of his
    16 shops (the 15 stables and Kara Kara Bazaar). They are listed first,
    priced by the seed; seeing them in his list hints them. 0: no shop."""
    display_name = "Beedle Shop Items"
    range_start = 0
    range_end = 2
    default = 0


class StallItems(Range):
    """Items on the 3D stalls of the villages (Kakariko, Hateno, Rito, Goron,
    Zora's Domain, Gerudo Town, Kara Kara, Korok Forest, Lurelin, Tarrey Town)
    that become Archipelago locations, spread at random over their 14 stalls,
    2 at most on one stall: some stalls have none, others one or two. The
    Archipelago medallion replaces one copy of an item the stall sells in
    several, priced by the seed; once bought it never comes back. 0: none."""
    display_name = "Stall Items"
    range_start = 0
    range_end = 28
    default = 0


class WeaponOrder(Choice):
    """How the weapons of the filler are spread over the game, wherever they land
    in the multiworld (the jokes, a Soup Ladle or a Pot Lid, always come anywhere).
    smoothed: the weaker first, the stronger as the game goes on, the amiibo's
    treasures last.
    loosely_smoothed: the same order, with some chance: a weapon may come a level
    earlier or later, never a treasure among the first.
    anywhere: wherever the fill put them, a treasure on the Great Plateau too."""
    display_name = "Weapon Order"
    option_anywhere = 0
    option_loosely_smoothed = 1
    option_smoothed = 2
    default = 2


class TowerMaps(Choice):
    """The map of each region, revealed in the game by its tower.
    vanilla: as in the game, a tower reveals its region's map.
    items: the 14 maps (all but the Great Plateau's) are items: a map received
    reveals its region with the game's own animation, and a tower no longer
    reveals it (climbing a tower still counts as its location, and opens its
    travel point). The logic does not change.
    region_keys: the maps are items, and a region's locations are in the logic once
    its map is received, as are the locations whose quest goes through another
    region with that region's map too. Nothing is locked in the game: a location
    done without its map counts all the same. The towers, the Great Plateau and
    Calamity Ganon need no map."""
    display_name = "Tower Maps"
    option_vanilla = 0
    option_items = 1
    option_region_keys = 2
    default = 2


class StartingMap(Choice):
    """With Tower Maps on items or region_keys, a map Link starts with.
    none: no map; until one comes, the towers are all the logic outside the Great
    Plateau.
    gentle: one of the regions the game leads to first: Dueling Peaks, Hateno,
    Lake or Faron.
    any: any of the 14 maps.
    A given map is started with by start_inventory instead (for example
    "Hateno Map": 1), with Starting Map on none."""
    display_name = "Starting Map"
    option_none = 0
    option_gentle = 1
    option_any = 2
    default = 1


class TrapPercentage(Range):
    """Share of the filler (arrows, elixirs, weapons, gems and rupees) that becomes traps,
    chosen among the traps of Trap Weights. 0: no trap. A trap strikes when it is
    received: Weapon Shatter breaks the weapon in Link's hand, Blood Moon calls a
    Blood Moon at once, Rupoor takes up to 100 rupees, Hearts Down takes up
    to two hearts (never the last quarter), Strip Down puts Link's weapon, shield,
    bow and armor back in the pouch, and Cucco Swarm sends the angry cuccos' swarm,
    which can kill (such a death is not sent as a DeathLink)."""
    display_name = "Trap Percentage"
    range_start = 0
    range_end = 100
    default = 0


class TrapWeights(OptionCounter):
    """How likely each trap is compared with the others: a trap of weight 2 comes up
    twice as often as one of weight 1. A trap left out of the list, or of weight 0,
    never comes up."""
    display_name = "Trap Weights"
    valid_keys = frozenset(TRAPS)
    min = 0
    default = {name: 1 for name in TRAPS}


@dataclass
class BotwOptions(PerGameCommonOptions):
    start_inventory_from_pool: StartInventoryPool
    goal: Goal
    goal_shrines: GoalShrines
    sanctum_divine_beasts: SanctumDivineBeasts
    sanctum_shrines: SanctumShrines
    sanctum_master_sword: SanctumMasterSword
    sanctum_runes: SanctumRunes
    beedle_shop_items: BeedleShopItems
    stall_items: StallItems
    death_link: DeathLink
    weapon_order: WeaponOrder
    tower_maps: TowerMaps
    starting_map: StartingMap
    trap_percentage: TrapPercentage
    trap_weights: TrapWeights


OPTION_GROUPS = [
    OptionGroup("Goal", [Goal, GoalShrines]),
    OptionGroup("Hyrule Castle's Sanctum",
                [SanctumDivineBeasts, SanctumShrines, SanctumMasterSword, SanctumRunes]),
    OptionGroup("Shops", [BeedleShopItems, StallItems]),
    OptionGroup("Weapons", [WeaponOrder]),
    OptionGroup("Maps", [TowerMaps, StartingMap]),
    OptionGroup("Traps", [TrapPercentage, TrapWeights]),
]

# What the sanctum asks before Ganon, ready made (the options page's presets; a
# YAML sets the same options by hand). The defaults are Medium.
PRESETS = {
    "Easy": {"sanctum_divine_beasts": 4, "sanctum_shrines": 0,
             "sanctum_master_sword": True, "sanctum_runes": True},
    "Medium": {"sanctum_divine_beasts": 2, "sanctum_shrines": 0,
               "sanctum_master_sword": True, "sanctum_runes": True},
    "Hard": {"sanctum_divine_beasts": 0, "sanctum_shrines": 0,
             "sanctum_master_sword": False, "sanctum_runes": False},
}
