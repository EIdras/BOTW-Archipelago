from collections import Counter
import unittest

from Fill import distribute_items_restrictive
from test.general import setup_multiworld
from worlds.AutoWorld import call_all

from . import BotwTestBase
from .. import BotwWorld
from ..catalog import WEAPON_LEVELS

# Every shop and stall location: about 26 weapons drawn.
SHOPS = {"beedle_shop_items": 2, "stall_items": 28}


def fill(multiworld) -> None:
    """The fill, then the stages after it: weapon_order runs in finalize_multiworld."""
    distribute_items_restrictive(multiworld)
    call_all(multiworld, "post_fill")
    call_all(multiworld, "finalize_multiworld")


def weapon_levels(multiworld, player: int) -> list[list[int]]:
    """The levels of a player's ordered weapons, sphere by sphere."""
    out = []
    for sphere in multiworld.get_spheres():
        if not sphere:
            break
        out.append(sorted(WEAPON_LEVELS[location.item.name] for location in sphere
                          if location.item.player == player and WEAPON_LEVELS.get(location.item.name)))
    return [levels for levels in out if levels]


class TestSmoothedWeapons(BotwTestBase):
    options = SHOPS

    def test_the_weaker_weapons_come_first(self) -> None:
        fill(self.multiworld)
        spheres = weapon_levels(self.multiworld, self.player)
        self.assertGreater(sum(map(len, spheres)), 5)
        for earlier, later in zip(spheres, spheres[1:]):
            self.assertLessEqual(earlier[-1], later[0])


class TestLooselySmoothedWeapons(BotwTestBase):
    options = {**SHOPS, "weapon_order": "loosely_smoothed"}

    def test_a_weapon_moves_by_less_than_three_levels(self) -> None:
        fill(self.multiworld)
        spheres = weapon_levels(self.multiworld, self.player)
        for index, earlier in enumerate(spheres):
            for later in spheres[index + 1:]:
                self.assertLess(earlier[-1] - later[0], 2 * BotwWorld.WEAPON_LEVEL_SPREAD)


class TestWeaponsAnywhere(BotwTestBase):
    options = {**SHOPS, "weapon_order": "anywhere"}

    def test_the_fill_placement_stays(self) -> None:
        distribute_items_restrictive(self.multiworld)
        call_all(self.multiworld, "post_fill")
        before = {location.name: location.item.name for location in self.multiworld.get_filled_locations()}
        call_all(self.multiworld, "finalize_multiworld")
        after = {location.name: location.item.name for location in self.multiworld.get_filled_locations()}
        self.assertEqual(before, after)


class TestTwoWorldsSmoothed(unittest.TestCase):
    """Two Breath of the Wild players: each one's weapons, wherever they landed,
    ordered by the spheres of the whole multiworld."""

    def test_each_players_weapons_are_ordered(self) -> None:
        multiworld = setup_multiworld([BotwWorld, BotwWorld], options=SHOPS)
        distribute_items_restrictive(multiworld)
        call_all(multiworld, "post_fill")
        before = Counter((location.item.player, location.item.name)
                         for location in multiworld.get_filled_locations())
        call_all(multiworld, "finalize_multiworld")
        for player in (1, 2):
            spheres = weapon_levels(multiworld, player)
            self.assertGreater(sum(map(len, spheres)), 5)
            for earlier, later in zip(spheres, spheres[1:]):
                self.assertLessEqual(earlier[-1], later[0])
        # Only the placements changed: the same items, each in one location.
        placed = multiworld.get_filled_locations()
        self.assertEqual(Counter((location.item.player, location.item.name) for location in placed), before)
        self.assertTrue(all(location.item.location is location for location in placed))
        self.assertEqual(len({id(location.item) for location in placed}), len(placed))
