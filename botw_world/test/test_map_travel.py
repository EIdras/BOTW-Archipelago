"""Map Travel Points: a map received opens the travel point of a shrine of its
region; with Region Lock, a region is in the logic with its map alone."""
import unittest

from Options import OptionError

from . import BotwTestBase
from .test_maps import filled
from .test_tracker import generate
from ..catalog import LOCATIONS, LOGIC, MAPS, NEIGHBOURS, TRAVEL_SHRINES, TRAVEL_TERMINALS, categories


class TestTravelShrines(unittest.TestCase):
    def test_each_map_opens_a_shrine_of_its_region(self) -> None:
        regions = {row["name"]: row["region"] for row in LOCATIONS if "Shrine" in categories(row)}
        self.assertEqual(set(TRAVEL_SHRINES), set(MAPS))
        for region, shrine in TRAVEL_SHRINES.items():
            self.assertEqual(regions[shrine], region)

    def test_each_travel_shrine_names_its_terminal(self) -> None:
        self.assertEqual(set(TRAVEL_TERMINALS), set(TRAVEL_SHRINES.values()))
        self.assertEqual(len(set(TRAVEL_TERMINALS.values())), len(TRAVEL_TERMINALS))

    def test_a_travel_shrine_stands_open_in_a_mild_climate(self) -> None:
        for shrine in TRAVEL_SHRINES.values():
            with self.subTest(shrine=shrine):
                self.assertEqual(LOGIC[shrine]["climate"], "none")
                self.assertEqual(LOGIC[shrine]["extra"], "")


class TestTravelWithRegionLock(BotwTestBase):
    options = {"region_lock": True, "map_travel_points": True, "early_map": "none"}

    def test_a_far_region_opens_with_its_map_and_the_paraglider(self) -> None:
        self.collect_by_name("Hateno Map")
        self.assertFalse(self.can_reach_region("Hateno"))
        self.collect_by_name("Paraglider")
        self.assertTrue(self.can_reach_region("Hateno"))

    def test_a_tower_still_needs_its_map(self) -> None:
        self.collect_by_name(["Paraglider", "Central Map"])
        self.assertFalse(self.can_reach_location("Woodland Tower"))
        self.collect_by_name("Woodland Map")
        self.assertTrue(self.can_reach_location("Woodland Tower"))

    def test_the_slot_data_names_each_maps_shrine(self) -> None:
        data = self.world.fill_slot_data()
        self.assertTrue(data["map_travel_points"])
        flags = {row["name"]: row["gamedata_flag"] for row in LOCATIONS}
        self.assertEqual(data["travel_shrines"], {MAPS[region]: [flags[shrine].removeprefix("Clear_"),
                                                                 TRAVEL_TERMINALS[shrine]]
                                                  for region, shrine in TRAVEL_SHRINES.items()})

    def test_the_early_map_may_be_any(self) -> None:
        drawn = {next(iter(generate({**self.options, "early_map": "any"}, seed=seed).local_early_items[1]))
                 for seed in range(20)}
        self.assertTrue(drawn - {MAPS[region] for region in NEIGHBOURS["Great Plateau"]})

    def test_the_fill_completes_the_game_with_each_early_map(self) -> None:
        for seed in range(5):
            for choice in ("none", "gentle", "any"):
                with self.subTest(early_map=choice, seed=seed):
                    multiworld = filled({**self.options, "early_map": choice}, seed)
                    self.assertTrue(multiworld.fulfills_accessibility())


class TestTravelWithoutRegionLock(BotwTestBase):
    options = {"map_travel_points": True}

    def test_the_logic_is_unchanged(self) -> None:
        self.collect_by_name("Paraglider")
        self.assertTrue(self.can_reach_region("Hateno"))
        self.assertTrue(self.can_reach_location("Woodland Tower"))

    def test_the_maps_must_be_items(self) -> None:
        with self.assertRaises(OptionError):
            generate({"map_travel_points": True, "tower_maps": "vanilla"})
