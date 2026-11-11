"""Region Lock: a region opens in the logic once its map is in and it borders a
region already in, as the game's map cuts them (data/region_borders.json)."""
import unittest

from Options import OptionError

from . import BotwTestBase
from .test_maps import filled
from .test_tracker import generate
from ..catalog import BORDERS, CLOSED_BORDERS, GENTLE_REGIONS, MAPS, NEIGHBOURS, OPEN_BORDERS

PLATEAU = "Great Plateau"


class TestBorders(unittest.TestCase):
    def test_a_border_joins_two_regions_of_the_map_once(self) -> None:
        pairs = [frozenset(row["regions"]) for row in BORDERS]
        self.assertTrue(all(len(pair) == 2 for pair in pairs))
        self.assertEqual(len(pairs), len(set(pairs)))
        self.assertEqual(set().union(*pairs), set(MAPS) | {PLATEAU})

    def test_neighbours_are_mutual(self) -> None:
        for name, others in NEIGHBOURS.items():
            for other in others:
                self.assertIn(name, NEIGHBOURS[other])

    def test_a_closed_border_is_not_crossed(self) -> None:
        for pair in CLOSED_BORDERS:
            first, second = sorted(pair)
            self.assertNotIn(second, NEIGHBOURS[first])

    def test_the_easy_way_across_a_closed_border_opens_nothing(self) -> None:
        # Gerudo to Central and Hebra to Ridgeland are easy, the other way not: with
        # them, no set of maps would open more.
        easy = (("Gerudo", "Central"), ("Hebra", "Ridgeland"))

        def reached(maps, ways=()):
            seen, todo = {PLATEAU}, [PLATEAU]
            while todo:
                here = todo.pop()
                for other in (NEIGHBOURS[here] | {b for a, b in ways if a == here}) & maps - seen:
                    seen.add(other)
                    todo.append(other)
            return seen

        regions = sorted(MAPS)
        for bits in range(1 << len(regions)):
            maps = {region for index, region in enumerate(regions) if bits >> index & 1}
            self.assertEqual(reached(maps, easy), reached(maps))

    def test_every_region_is_reached_from_the_plateau(self) -> None:
        reached, todo = {PLATEAU}, [PLATEAU]
        while todo:
            for other in NEIGHBOURS[todo.pop()] - reached:
                reached.add(other)
                todo.append(other)
        self.assertEqual(reached, set(MAPS) | {PLATEAU})


class TestRegionLock(BotwTestBase):
    options = {"region_lock": True, "early_map": "none", "stall_items": 28}

    def test_a_region_bordering_the_plateau_opens_with_its_map_and_the_paraglider(self) -> None:
        self.collect_by_name("Dueling Peaks Map")
        self.assertFalse(self.can_reach_region("Dueling Peaks"))
        self.collect_by_name("Paraglider")
        self.assertTrue(self.can_reach_region("Dueling Peaks"))

    def test_a_far_region_opens_through_its_neighbours(self) -> None:
        self.collect_by_name(["Paraglider", "Hateno Map"])
        self.assertFalse(self.can_reach_region("Hateno"))
        self.collect_by_name("Dueling Peaks Map")
        self.assertTrue(self.can_reach_region("Hateno"))

    def test_a_closed_border_leaves_a_region_to_its_other_neighbours(self) -> None:
        # Central-Gerudo is closed: Gerudo opens from the Wasteland.
        self.collect_by_name(["Paraglider", "Central Map", "Gerudo Map"])
        self.assertFalse(self.can_reach_region("Gerudo"))
        self.collect_by_name("Wasteland Map")
        self.assertTrue(self.can_reach_region("Gerudo"))

    def test_a_tower_needs_its_map(self) -> None:
        self.collect_by_name(["Paraglider", "Central Map"])
        self.assertFalse(self.can_reach_location("Woodland Tower"))
        self.collect_by_name("Woodland Map")
        self.assertTrue(self.can_reach_location("Woodland Tower"))

    def test_hyrule_castle_is_entered_from_central(self) -> None:
        self.collect_by_name("Paraglider")
        self.assertFalse(self.can_reach_region("Hyrule Castle"))
        self.collect_by_name("Central Map")
        self.assertTrue(self.can_reach_region("Hyrule Castle"))

    def test_a_quest_through_another_region_needs_to_reach_it(self) -> None:
        # Shoqa Tatone (Lake) goes through Hateno and Central, and Kakariko for Impa
        # (Dueling Peaks): Hateno reached by Faron is not enough without it.
        self.collect_by_name(["Paraglider", "Lake Map", "Hateno Map", "Central Map", "Faron Map"])
        self.assertTrue(self.can_reach_region("Hateno"))
        self.assertFalse(self.can_reach_location("Shoqa Tatone Shrine"))
        self.collect_by_name("Dueling Peaks Map")
        self.assertTrue(self.can_reach_location("Shoqa Tatone Shrine"))

    def test_the_slot_data_tells_the_lock_and_its_borders(self) -> None:
        data = self.world.fill_slot_data()
        self.assertTrue(data["region_lock"])
        self.assertEqual(data["region_borders"], [list(pair) for pair in OPEN_BORDERS])

    def test_universal_tracker_regenerates_the_lock(self) -> None:
        multiworld = generate(passthrough=self.world.fill_slot_data())
        self.assertTrue(multiworld.worlds[1].options.region_lock)
        self.assertFalse(multiworld.get_region("Hateno", 1).can_reach(multiworld.state))

    def test_the_early_map_borders_the_plateau(self) -> None:
        for choice, regions in (("gentle", set(GENTLE_REGIONS) & NEIGHBOURS[PLATEAU]),
                                ("any", NEIGHBOURS[PLATEAU])):
            for seed in range(10):
                with self.subTest(early_map=choice, seed=seed):
                    multiworld = generate({"region_lock": True, "early_map": choice}, seed=seed)
                    (early,) = multiworld.local_early_items[1]
                    self.assertIn(early, {MAPS[region] for region in regions})

    def test_the_fill_completes_the_game_with_each_early_map(self) -> None:
        for seed in range(5):
            for choice in ("none", "gentle", "any"):
                with self.subTest(early_map=choice, seed=seed):
                    multiworld = filled({"region_lock": True, "early_map": choice}, seed)
                    self.assertTrue(multiworld.fulfills_accessibility())

    def test_the_lock_needs_the_maps_as_region_keys(self) -> None:
        for maps in ("vanilla", "items"):
            with self.subTest(tower_maps=maps), self.assertRaises(OptionError):
                generate({"region_lock": True, "tower_maps": maps})


class TestWithoutRegionLock(BotwTestBase):
    def test_every_region_opens_from_the_plateau(self) -> None:
        self.collect_by_name("Paraglider")
        self.assertTrue(self.can_reach_region("Hateno"))
        self.assertTrue(self.can_reach_region("Hyrule Castle"))

    def test_the_slot_data_has_no_borders(self) -> None:
        data = self.world.fill_slot_data()
        self.assertFalse(data["region_lock"])
        self.assertNotIn("region_borders", data)
