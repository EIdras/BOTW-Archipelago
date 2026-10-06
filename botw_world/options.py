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


class TrapPercentage(Range):
    """Share of the filler (arrows, elixirs, gems and rupees) that becomes traps,
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
    trap_percentage: TrapPercentage
    trap_weights: TrapWeights


OPTION_GROUPS = [
    OptionGroup("Goal", [Goal, GoalShrines]),
    OptionGroup("Hyrule Castle's Sanctum",
                [SanctumDivineBeasts, SanctumShrines, SanctumMasterSword, SanctumRunes]),
    OptionGroup("Shops", [BeedleShopItems, StallItems]),
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
