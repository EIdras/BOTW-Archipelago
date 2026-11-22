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
        # No Master Sword on its owner's Great Plateau.
        self.assertFalse([location.name for location in placed if location.item.name == "Master Sword"
                          and location.parent_region.name == "Great Plateau"
                          and location.player == location.item.player])


class TestMasterSwordOffThePlateau(unittest.TestCase):
    """Unless weapon_order is anywhere, no location of a player's Great Plateau
    takes that player's Master Sword."""

    def test_the_plateau_refuses_it_but_anywhere(self) -> None:
        for order, taken in (("smoothed", False), ("loosely_smoothed", False), ("anywhere", True)):
            with self.subTest(order):
                multiworld = setup_multiworld(BotwWorld, options={"weapon_order": order})
                world = multiworld.worlds[1]
                sword = world.create_item("Master Sword")
                plateau = world.get_region("Great Plateau").locations
                self.assertEqual({location.item_rule(sword) for location in plateau}, {taken})
                # Another item still goes there.
                self.assertTrue(all(location.item_rule(world.create_item("Paraglider")) for location in plateau))

    def test_another_players_sword_goes_there(self) -> None:
        # Ruling it out too, with both swords refused on both plateaus, fails some fills.
        multiworld = setup_multiworld([BotwWorld, BotwWorld])
        swords = {player: multiworld.worlds[player].create_item("Master Sword") for player in (1, 2)}
        for player, other in ((1, 2), (2, 1)):
            with self.subTest(plateau=player):
                plateau = multiworld.worlds[player].get_region("Great Plateau").locations
                self.assertFalse(any(location.item_rule(swords[player]) for location in plateau))
                self.assertTrue(all(location.item_rule(swords[other]) for location in plateau))

    def test_the_fill_puts_it_elsewhere(self) -> None:
        # Seed 3 put it on the Stasis Terminal before the rule.
        multiworld = setup_multiworld(BotwWorld, seed=3)
        fill(multiworld)
        sword = next(location for location in multiworld.get_filled_locations() if location.item.name == "Master Sword")
        self.assertNotEqual(sword.parent_region.name, "Great Plateau")
        self.assertTrue(multiworld.can_beat_game(multiworld.state))
