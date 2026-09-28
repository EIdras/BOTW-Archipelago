"""Player options of the Breath of the Wild world."""
from dataclasses import dataclass

from Options import Choice, DeathLink, OptionGroup, PerGameCommonOptions, Range, StartInventoryPool


class Goal(Choice):
    """What finishes the game. Calamity Ganon must always be defeated; the shrines and
    Divine Beasts goals also require a number of cleared shrines or freed Divine Beasts
    before the final fight counts."""
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


class BeedleShopItems(Range):
    """Items of Beedle's stock that become Archipelago locations, at each of his
    16 shops (the 15 stables and Kara Kara Bazaar). They are listed first,
    priced by the seed; seeing them in his list hints them. 0: no shop."""
    display_name = "Beedle Shop Items"
    range_start = 0
    range_end = 2
    default = 0


class StallShopItems(Range):
    """Items on the 3D stalls of the villages (Kakariko, Hateno, Rito, Goron,
    Zora's Domain, Gerudo Town, Kara Kara, Korok Forest, Lurelin, Tarrey Town)
    that become Archipelago locations, at each of their 14 stalls: the
    Archipelago medallion replaces one copy of an item the stall sells in
    several, priced by the seed; once bought it never comes back. 0: none."""
    display_name = "Stall Shop Items"
    range_start = 0
    range_end = 2
    default = 0


@dataclass
class BotwOptions(PerGameCommonOptions):
    start_inventory_from_pool: StartInventoryPool
    goal_type: Goal
    shrines_required: ShrinesRequired
    divine_beasts_required: BeastsRequired
    beedle_shop_items: BeedleShopItems
    stall_shop_items: StallShopItems
    death_link: DeathLink


OPTION_GROUPS = [
    OptionGroup("Goal", [Goal, ShrinesRequired, BeastsRequired]),
    OptionGroup("Shops", [BeedleShopItems, StallShopItems]),
]
