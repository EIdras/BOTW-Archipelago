"""The tower maps: items of the pool (tower_maps), region keys of the logic, the
map placed early (early_map), and Universal Tracker's out-of-logic view."""
from BaseClasses import CollectionState, ItemClassification

from . import BotwTestBase
from .test_tracker import generate
from ..catalog import GENTLE_REGIONS, LOCATIONS, MAPS, RUNES, categories, map_keys

STAND_IN = "Region Without Its Map"
# What the start reaches: the Great Plateau's rune terminals and its tower.
FIRST_LOCATIONS = {"Magnesis Terminal", "Remote Bombs Terminal", "Stasis Terminal", "Cryonis Terminal",
                   "Great Plateau Tower"}


def maps_of(multiworld):
    return sorted(item.name for item in multiworld.itempool if item.name in MAPS.values())


def filled(options, seed):
    from Fill import distribute_items_restrictive
    from worlds.AutoWorld import call_all
    multiworld = generate(options, seed=seed)
    distribute_items_restrictive(multiworld)
    call_all(multiworld, "post_fill")
    return multiworld


class TestRegionKeysByDefault(BotwTestBase):
    def test_fourteen_maps_in_the_pool_a_gentle_one_early(self) -> None:
        self.assertEqual(self.multiworld.precollected_items[self.player], [])
        self.assertEqual(maps_of(self.multiworld), sorted(MAPS.values()))
        early = self.multiworld.local_early_items[self.player]
        self.assertEqual(len(early), 1)
        self.assertIn(next(iter(early)), {MAPS[region] for region in GENTLE_REGIONS})
        self.assertTrue(all(self.world.create_item(name).classification == ItemClassification.progression
                            for name in MAPS.values()))

    def test_a_region_is_in_logic_with_its_map(self) -> None:
        self.collect_by_name(["Paraglider", *RUNES])
        self.assertTrue(self.can_reach_location("Hebra Tower"))          # a tower needs no map
        self.assertFalse(self.can_reach_location("Rin Oyaa Shrine"))
        self.collect_by_name("Hebra Map")
        self.assertTrue(self.can_reach_location("Rin Oyaa Shrine"))

    def test_the_plateau_needs_no_map(self) -> None:
        self.collect_by_name(list(RUNES))
        self.assertTrue(self.can_reach_location("Oman Au Shrine"))

    def test_a_divine_beast_and_its_event_need_the_map(self) -> None:
        self.collect_by_name(["Paraglider", *RUNES])
        self.assertFalse(self.can_reach_location("Divine Beast Vah Medoh"))
        self.assertFalse(self.can_reach_location("Freed - Divine Beast Vah Medoh"))
        self.collect_by_name("Tabantha Map")
        self.assertTrue(self.can_reach_location("Freed - Divine Beast Vah Medoh"))


class TestTheEarlyMapIsOnThePlateau(BotwTestBase):
    def test_the_fill_puts_it_at_one_of_the_first_locations(self) -> None:
        for seed in range(40, 50):
            for options in ({}, {"beedle_shop_items": 2, "stall_items": 28}, {"early_map": "any"}):
                with self.subTest(seed=seed, options=options):
                    multiworld = filled(options, seed)
                    (early,) = multiworld.local_early_items[1]
                    spots = [loc.name for loc in multiworld.get_locations(1) if loc.item and loc.item.name == early]
                    self.assertEqual(len(spots), 1)
                    self.assertIn(spots[0], FIRST_LOCATIONS)


class TestQuestsThroughOtherRegions(BotwTestBase):
    options = {"stall_items": 28, "early_map": "none"}

    def test_tarrey_towns_arrow_stall_needs_the_maps_of_its_recruits(self) -> None:
        self.collect_by_name(["Paraglider", *RUNES, "Flamebreaker Set", "Akkala Map", "Eldin Map", "Wasteland Map"])
        self.assertFalse(self.can_reach_location("Tarrey Town - Arrow Stall Item 1"))
        self.collect_by_name("Tabantha Map")
        self.assertTrue(self.can_reach_location("Tarrey Town - Arrow Stall Item 1"))

    def test_shoqa_tatone_needs_the_camera_and_the_guardians(self) -> None:
        self.collect_by_name(["Paraglider", "Lake Map", "Hateno Map"])
        self.assertFalse(self.can_reach_location("Shoqa Tatone Shrine"))
        self.collect_by_name("Central Map")
        self.assertTrue(self.can_reach_location("Shoqa Tatone Shrine"))

    def test_every_keyed_location_names_maps_of_the_pool(self) -> None:
        names = set(MAPS.values())
        for row in LOCATIONS:
            self.assertLessEqual(set(map_keys(row)), names, row["name"])
            if "Tower" in categories(row) or row["region"] in ("Great Plateau", "Hyrule Castle"):
                self.assertEqual(map_keys(row), (), row["name"])


class TestUniversalTrackerOutOfLogic(BotwTestBase):
    def test_the_stand_in_reaches_every_region_but_counts_as_no_map(self) -> None:
        item = self.world.create_item(STAND_IN)
        self.assertEqual(item.code, None)
        self.assertTrue(item.advancement)
        self.assertEqual(self.world.glitches_item_name, STAND_IN)
        self.collect_by_name(["Paraglider", *RUNES])
        self.assertFalse(self.can_reach_location("Rin Oyaa Shrine"))
        self.collect(item)
        self.assertTrue(self.can_reach_location("Rin Oyaa Shrine"))
        self.assertFalse(self.multiworld.state.has("Hebra Map", self.player))


class TestNoEarlyMap(BotwTestBase):
    options = {"early_map": "none", "beedle_shop_items": 2, "stall_items": 28}

    def test_all_fourteen_maps_anywhere(self) -> None:
        self.assertEqual(self.multiworld.local_early_items[self.player], {})
        self.assertEqual(maps_of(self.multiworld), sorted(MAPS.values()))


class TestAnyEarlyMap(BotwTestBase):
    options = {"early_map": "any", "accessibility": "minimal"}

    def test_one_map_early(self) -> None:
        early = self.multiworld.local_early_items[self.player]
        self.assertEqual(len(early), 1)
        self.assertIn(next(iter(early)), MAPS.values())


class TestMapsAsItemsOnly(BotwTestBase):
    options = {"tower_maps": "items"}

    def test_maps_are_useful_and_the_logic_has_no_key(self) -> None:
        self.assertEqual(maps_of(self.multiworld), sorted(MAPS.values()))
        self.assertTrue(all(self.world.create_item(name).classification == ItemClassification.useful
                            for name in MAPS.values()))
        self.collect_by_name(["Paraglider", *RUNES])
        self.assertTrue(self.can_reach_location("Rin Oyaa Shrine"))


class TestVanillaMaps(BotwTestBase):
    options = {"tower_maps": "vanilla"}

    def test_no_map_anywhere(self) -> None:
        self.assertEqual(maps_of(self.multiworld), [])
        self.assertEqual(self.multiworld.local_early_items[self.player], {})
        self.collect_by_name(["Paraglider", *RUNES])
        self.assertTrue(self.can_reach_location("Rin Oyaa Shrine"))
        self.assertEqual(self.world.fill_slot_data()["tower_maps"], 0)


class TestManySeeds(BotwTestBase):
    """Region keys with every shop and stall, or no early map: the fill places everything, seed after seed."""
    options = {"beedle_shop_items": 2, "stall_items": 28}

    def test_the_fill_succeeds_on_more_seeds(self) -> None:
        for seed in range(20, 30):
            for options in ({"beedle_shop_items": 2, "stall_items": 28}, {"early_map": "none"},
                            {"early_map": "any", "accessibility": "minimal"}):
                with self.subTest(seed=seed, options=options):
                    multiworld = filled(options, seed)
                    self.assertTrue(multiworld.can_beat_game(CollectionState(multiworld)))


class TestRegenerationWithoutMaps(BotwTestBase):
    def test_a_seed_from_before_the_maps_regenerates_without_them(self) -> None:
        slot_data = generate().worlds[1].fill_slot_data()
        del slot_data["tower_maps"]
        again = generate(passthrough=slot_data, seed=5)
        self.assertEqual(again.worlds[1].options.tower_maps.value, 0)
        self.assertEqual(maps_of(again), [])

    def test_a_seed_with_maps_regenerates_them(self) -> None:
        slot_data = generate().worlds[1].fill_slot_data()
        again = generate(passthrough=slot_data, seed=5)
        self.assertEqual(again.precollected_items[1], [])
        self.assertEqual(maps_of(again), sorted(MAPS.values()))
