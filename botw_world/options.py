"""Player options of the Breath of the Wild world."""
from dataclasses import dataclass

from Options import (Choice, DeathLink, OptionCounter, OptionGroup, PerGameCommonOptions, Range,
                     StartInventoryPool, Toggle)

from .catalog import TRAPS


class Goal(Choice):
    """What finishes the game. Calamity Ganon must always be defeated; the shrines and
    Divine Beasts goals also require a number of cleared shrines or freed Divine Beasts.
    The sanctum of Hyrule Castle stays sealed until every requirement of the seed is
    met (with Master Sword Before Ganon and Runes Before Ganon): entering it sends Link
    back, and the Archipelago journal says what is missing."""
    display_name = "Goal"
    option_ganon = 0
    option_divine_beasts = 1
    option_shrines = 2
    default = 0


class ShrinesRequired(Range):
    """Shrines to clear before Ganon, with the shrines goal."""
    display_name = "Required Shrines"
    range_start = 1
    range_end = 120
    default = 40


class BeastsRequired(Range):
    """Divine Beasts to free before Ganon, with the Divine Beasts goal."""
    display_name = "Required Divine Beasts"
    range_start = 1
    range_end = 4
    default = 4


class MasterSwordBeforeGanon(Toggle):
    """The sanctum opens only once the Master Sword has been received."""
    display_name = "Master Sword Before Ganon"
    default = 0


class RunesBeforeGanon(Toggle):
    """The sanctum opens only once the four runes (Magnesis, Remote Bomb, Stasis,
    Cryonis) have been received."""
    display_name = "Runes Before Ganon"
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
    """Share of the filler, the items that would be Rupee Bundles, that become traps,
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
    goal_type: Goal
    shrines_required: ShrinesRequired
    divine_beasts_required: BeastsRequired
    ganon_master_sword: MasterSwordBeforeGanon
    ganon_runes: RunesBeforeGanon
    beedle_shop_items: BeedleShopItems
    stall_items: StallItems
    death_link: DeathLink
    trap_percentage: TrapPercentage
    trap_weights: TrapWeights


OPTION_GROUPS = [
    OptionGroup("Goal", [Goal, ShrinesRequired, BeastsRequired, MasterSwordBeforeGanon, RunesBeforeGanon]),
    OptionGroup("Shops", [BeedleShopItems, StallItems]),
    OptionGroup("Traps", [TrapPercentage, TrapWeights]),
]

# What the sanctum asks before Ganon, ready made (the options page's presets; a
# YAML sets the same options by hand). Easy: everything the game offers first;
# Hard: Ganon whenever Link likes, as in the game.
PRESETS = {
    "Easy": {"goal_type": "divine_beasts", "divine_beasts_required": 4,
             "ganon_master_sword": True, "ganon_runes": True},
    "Medium": {"goal_type": "divine_beasts", "divine_beasts_required": 2,
               "ganon_master_sword": True, "ganon_runes": True},
    "Hard": {"goal_type": "ganon", "ganon_master_sword": False, "ganon_runes": False},
}
