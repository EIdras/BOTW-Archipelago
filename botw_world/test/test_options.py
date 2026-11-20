from BaseClasses import ItemClassification, LocationProgressType
from Fill import distribute_items_restrictive
from Options import OptionError
from worlds.AutoWorld import call_all

from . import BotwTestBase
from .. import BotwWorld
from .test_tracker import generate
from ..catalog import (ALL_SHRINES, CHEST_ID_BASE, CHESTS, FILLER, KOROK_ID_BASE, KOROKS, LOCATIONS, MAPS,
                       QUEST_ID_BASE, QUESTS, RUNES, TRAPS, WEAPONS, map_keys, requirements)

# The filler of the default options: 159 locations, 119 declared items, 14 maps.
FILLER_SLOTS = 26


class TestWithoutShops(BotwTestBase):
    def test_no_shop_or_stall_location_by_default(self) -> None:
        names = {location.name for location in self.multiworld.get_locations(self.player)}
        self.assertFalse(names & self.world.location_name_groups["Beedle Shops"])
        self.assertFalse(names & self.world.location_name_groups["Stalls"])


class TestWithShops(BotwTestBase):
    options = {"beedle_shop_items": 2, "stall_items": 28}

    def test_every_shop_and_stall_location_exists_and_has_a_price(self) -> None:
        names = {location.name for location in self.multiworld.get_locations(self.player)}
        shops = self.world.location_name_groups["Beedle Shops"] | self.world.location_name_groups["Stalls"]
        self.assertEqual(len(shops), 60)
        self.assertLessEqual(shops, names)
        self.assertEqual(len(self.world.shop_prices), 60)
        self.assertTrue(all(20 <= price <= 200 and price % 5 == 0 for price in self.world.shop_prices.values()))


class TestOneItemPerShop(BotwTestBase):
    options = {"beedle_shop_items": 1}

    def test_half_of_beedles_shop_locations(self) -> None:
        self.assertEqual(len(self.world.shop_prices), 16)


class TestSomeStallItems(BotwTestBase):
    options = {"stall_items": 9}

    def test_the_stall_items_are_spread_two_at_most_on_a_stall(self) -> None:
        stalls = self.world.location_name_groups["Stalls"]
        names = {location.name for location in self.multiworld.get_locations(self.player)} & stalls
        self.assertEqual(len(names), 9)
        self.assertEqual(len(self.world.shop_prices), 9)
        per_stall = {}
        for name in names:
            stall = name.rsplit(" Item ", 1)[0]
            per_stall[stall] = per_stall.get(stall, 0) + 1
        self.assertLessEqual(max(per_stall.values()), 2)


class TestDeathLink(BotwTestBase):
    options = {"death_link": True}

    def test_slot_data_carries_death_link(self) -> None:
        self.assertIs(self.world.fill_slot_data()["death_link"], True)


class TestDeathLinkOffByDefault(BotwTestBase):
    def test_slot_data_carries_death_link(self) -> None:
        self.assertIs(self.world.fill_slot_data()["death_link"], False)


class TestNoTrapsByDefault(BotwTestBase):
    def test_the_pool_has_no_trap(self) -> None:
        self.assertEqual([item.name for item in self.multiworld.itempool if item.trap], [])


class TestEveryFillerATrap(BotwTestBase):
    options = {"trap_percentage": 100}

    def test_the_filler_becomes_traps_of_the_default_weights(self) -> None:
        pool = [item.name for item in self.multiworld.itempool]
        self.assertFalse(set(pool) & {name for _, items in FILLER.values() for name in items})
        traps = [item for item in self.multiworld.itempool if item.trap]
        self.assertEqual(len(traps), FILLER_SLOTS)
        # Drawn at random, of equal weights: every kind may not come up in 26
        # draws, but nearly always four of them.
        names = {item.name for item in traps}
        self.assertLessEqual(names, {"Weapon Shatter", "Blood Moon", "Rupoor", "Hearts Down", "Strip Down",
                                     "Cucco Swarm", "Downpour", "Yiga Ambush", "Paranoia"})
        self.assertGreaterEqual(len(names), 4)
        self.assertEqual(len(pool), 159)


class TestFiller(BotwTestBase):
    def test_the_filler_is_drawn_from_every_family(self) -> None:
        fillers = {name: family for family, (_, items) in FILLER.items() for name in items}
        drawn = [item for item in self.multiworld.itempool if item.name in fillers]
        self.assertEqual(len(drawn), FILLER_SLOTS)
        # Filler, but for the amiibo's weapons: useful.
        treasures = set(WEAPONS["treasure"][2])
        self.assertTrue(all(item.classification == (ItemClassification.useful if item.name in treasures
                                                    else ItemClassification.filler) for item in drawn))
        # 2000 draws: every family and every weapon group, near their weights.
        names = [self.world.get_filler_item_name() for _ in range(2000)]
        for family, (weight, _items) in FILLER.items():
            share = sum(fillers[name] == family for name in names) / len(names)
            self.assertAlmostEqual(share, weight / 100, delta=0.04, msg=family)
        groups = sum(weight for weight, _level, _weapons in WEAPONS.values())
        for group, (weight, _level, weapons) in WEAPONS.items():
            share = sum(name in weapons for name in names) / len(names)
            self.assertAlmostEqual(share, FILLER["weapons"][0] / 100 * weight / groups, delta=0.02, msg=group)


class TestOneTrapOnly(BotwTestBase):
    options = {"trap_percentage": 50, "trap_weights": {"Rupoor": 3, "Blood Moon": 0}}

    def test_only_the_weighted_trap_comes_up(self) -> None:
        names = [item.name for item in self.multiworld.itempool if item.trap]
        self.assertEqual(set(names), {"Rupoor"})
        self.assertEqual(len(names), round(FILLER_SLOTS * 50 / 100))
        fillers = {name for _, items in FILLER.values() for name in items}
        self.assertEqual(len([item for item in self.multiworld.itempool if item.name in fillers]),
                         FILLER_SLOTS - len(names))


class TestDivineBeastGoal(BotwTestBase):
    options = {"goal": "divine_beasts"}


class TestShrineGoal(BotwTestBase):
    options = {"goal": "shrines", "goal_shrines": 120}


class TestBikeAnywhereOffByDefault(BotwTestBase):
    def test_the_slot_data_tells_the_pack_builder(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["bike_anywhere"], 0)


class TestBikeAnywhere(BotwTestBase):
    options = {"bike_anywhere": True}

    def test_the_slot_data_tells_the_pack_builder(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["bike_anywhere"], 1)


class TestCutsceneSkipOffByDefault(BotwTestBase):
    def test_the_slot_data_tells_the_pack_builder(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["cutscene_skip"], 0)


class TestCutsceneSkip(BotwTestBase):
    options = {"cutscene_skip": True}

    def test_the_slot_data_tells_the_pack_builder(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["cutscene_skip"], 1)


class TestChestSanityOffByDefault(BotwTestBase):
    def test_no_chest_location(self) -> None:
        locations = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertFalse(locations & {row["name"] for row in CHESTS})
        self.assertEqual(self.world.fill_slot_data()["chest_sanity"], 0)
        self.assertEqual(self.world.fill_slot_data()["client_schema"], 12)


class TestChestSanityCheckOnly(BotwTestBase):
    options = {"chest_sanity": "check_only"}

    def test_the_chests_are_locations_the_pack_leaves_alone(self) -> None:
        locations = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertLessEqual({row["name"] for row in CHESTS}, locations)
        slot_data = self.world.fill_slot_data()
        self.assertEqual((slot_data["chest_sanity"], slot_data["client_schema"]), (1, 13))


class TestChestSanity(BotwTestBase):
    options = {"chest_sanity": "ap_items", "trap_percentage": 100}

    def test_every_chest_is_an_excluded_location(self) -> None:
        chests = [loc for loc in self.multiworld.get_locations(self.player) if loc.name in self.world.
                  location_name_groups["Chests"]]
        self.assertEqual(len(chests), len(CHESTS))
        self.assertEqual({loc.progress_type for loc in chests}, {LocationProgressType.EXCLUDED})
        self.assertEqual({loc.address - CHEST_ID_BASE for loc in chests}, {row["number"] for row in CHESTS})
        self.assertEqual(self.world.fill_slot_data()["chest_sanity"], 2)

    def test_a_chest_after_every_shrine_waits_for_them(self) -> None:
        row = next(r for r in CHESTS if ALL_SHRINES in r["requires"])
        names = {name for names, _count in requirements(row) for name in names}
        self.assertLessEqual({f"Cleared - {name}" for name in self.world.location_name_groups["Shrines"]}, names)
        self.assertNotIn(ALL_SHRINES, names)

    def test_a_shrine_chest_asks_its_shrine_and_every_rune(self) -> None:
        row = next(r for r in CHESTS if r.get("dungeon") == "Jee Noh Shrine")
        shrine = next(r for r in LOCATIONS if r["name"] == row["dungeon"])
        self.assertLessEqual(set(requirements(shrine)), set(requirements(row)))
        self.assertLessEqual({((rune,), 1) for rune in RUNES}, set(requirements(row)))
        self.assertIn(row["name"], self.world.location_name_groups["Shrine Chests"])

    def test_a_divine_beast_chest_asks_its_beast(self) -> None:
        row = next(r for r in CHESTS if r.get("dungeon") == "Divine Beast Vah Ruta")
        self.assertIn((("Zora Set",), 1), requirements(row))
        self.assertIn(row["name"], self.world.location_name_groups["Divine Beast Chests"])
        self.assertNotIn(row["name"], self.world.location_name_groups["Shrine Chests"])

    def test_the_chests_bring_filler_not_traps(self) -> None:
        traps = [item for item in self.multiworld.itempool if item.trap]
        self.assertEqual(len(traps), FILLER_SLOTS)
        self.assertEqual(len(self.multiworld.itempool), 159 + len(CHESTS))

    def test_a_chest_asks_what_its_place_does(self) -> None:
        state = self.multiworld.state
        buried = next(row for row in CHESTS if row["kind"] == "Buried" and not row["heat"]
                      and row["region"] != "Great Plateau")
        location = self.multiworld.get_location(buried["name"], self.player)
        self.collect_by_name(["Paraglider", MAPS[buried["region"]]])
        self.assertFalse(location.can_reach(state))
        self.collect_by_name(["Magnesis"])
        self.assertTrue(location.can_reach(state))


class TestChestProgression(BotwTestBase):
    options = {"chest_sanity": "ap_items", "chest_progression": True}

    def test_the_chests_the_map_describes_may_hold_progression(self) -> None:
        excluded = {loc.name for loc in self.multiworld.get_locations(self.player)
                    if loc.progress_type == LocationProgressType.EXCLUDED}
        self.assertEqual(excluded & self.world.location_name_groups["Chests"],
                         {row["name"] for row in CHESTS if row["no_progression"]})
        self.assertEqual(len(CHESTS) - len(excluded), 1339)

    def test_a_gerudo_town_chest_asks_for_the_gerudo_set(self) -> None:
        town = [row for row in CHESTS if "Gerudo Set" in row["requires"]]
        self.assertEqual(len(town), 4)
        self.assertTrue(all(row["name"].startswith("Gerudo Town - ") for row in town))
        self.assertIn((("Gerudo Set",), 1), requirements(town[0]))

    def test_no_buried_chest_holds_progression_in_the_first_half(self) -> None:
        moved = 0
        for seed in range(1, 6):        # a seed may have no buried chest in the first half
            self.world_setup(seed)
            distribute_items_restrictive(self.multiworld)
            call_all(self.multiworld, "post_fill")
            spheres = BotwWorld.spheres(self.multiworld)
            buried = [location for sphere in spheres[:len(spheres) // 2] for location in sphere
                      if location.player == self.player and location.name in self.world.location_name_groups
                      ["Buried Chests"]]
            moved += sum(location.item.advancement for location in buried)
            call_all(self.multiworld, "finalize_multiworld")
            with self.subTest(seed=seed):
                self.assertEqual([location.name for location in buried if location.item.advancement], [])
                self.assertTrue(self.multiworld.can_beat_game())
                self.assertTrue(all(location.item.location is location
                                    for location in self.multiworld.get_filled_locations()))
        self.assertGreater(moved, 0)


class TestChestProgressionRegionLock(BotwTestBase):
    options = {"chest_sanity": "check_only", "chest_progression": True, "region_lock": True}

    def test_a_chest_waits_for_its_regions_map(self) -> None:
        row = next(r for r in CHESTS if r["region"] == "Hateno" and not r["requires"] and not r.get("dungeon"))
        location = self.multiworld.get_location(row["name"], self.player)
        self.collect_by_name(["Paraglider", *(name for name in MAPS.values() if name != MAPS["Hateno"])])
        self.assertFalse(location.can_reach(self.multiworld.state))
        self.collect_by_name([MAPS["Hateno"]])
        self.assertTrue(location.can_reach(self.multiworld.state))

    def test_chest_progression_needs_chest_sanity(self) -> None:
        with self.assertRaises(OptionError):
            generate({"chest_progression": True})


class TestShrineChestItems(BotwTestBase):
    options = {"chest_sanity": "ap_items", "shrine_chest_items": True}

    def test_the_slot_data_tells_the_pack_builder(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["shrine_chest_items"], 1)

    def test_shrine_chest_items_needs_ap_items(self) -> None:
        for options in ({"shrine_chest_items": True}, {"chest_sanity": "check_only", "shrine_chest_items": True}):
            with self.subTest(options=options), self.assertRaises(OptionError):
                generate(options)


class TestKorokSanityOffByDefault(BotwTestBase):
    def test_no_korok_location(self) -> None:
        locations = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertFalse(locations & self.world.location_name_groups["Koroks"])
        self.assertNotIn("korok_locations", self.world.fill_slot_data())


class TestKorokSanity(BotwTestBase):
    options = {"korok_sanity": True, "korok_count": 40, "korok_local_filler": 0, "chest_sanity": "check_only",
               "trap_percentage": 100}

    def test_korok_count_koroks_drawn_are_excluded_locations(self) -> None:
        koroks = [loc for loc in self.multiworld.get_locations(self.player)
                  if loc.name in self.world.location_name_groups["Koroks"]]
        self.assertEqual(len(koroks), 40)
        self.assertEqual({loc.progress_type for loc in koroks}, {LocationProgressType.EXCLUDED})
        slot_data = self.world.fill_slot_data()
        self.assertEqual((slot_data["korok_count"], slot_data["client_schema"], slot_data["world_schema"]),
                         (40, 14, 8))
        self.assertEqual(slot_data["korok_locations"], sorted(loc.address for loc in koroks))
        self.assertTrue(all(KOROK_ID_BASE < loc.address <= KOROK_ID_BASE + len(KOROKS) for loc in koroks))

    def test_they_bring_no_more_traps(self) -> None:
        with_koroks = generate(self.options)
        without = generate({"chest_sanity": "check_only", "trap_percentage": 100})
        self.assertEqual(sum(item.name in TRAPS for item in with_koroks.itempool),
                         sum(item.name in TRAPS for item in without.itempool))
        self.assertEqual(len(with_koroks.itempool), len(without.itempool) + 40)

    def test_a_koroks_puzzle_is_in_its_rule(self) -> None:
        for item in ("Magnesis", "Progressive Remote Bomb", "Gerudo Set"):
            row = next(row for row in KOROKS if row["requires"] == [item])
            self.assertIn(((item,), 1), requirements(row))
        hylia = next(row for row in KOROKS if row["name"] == "Mount Hylia - Korok 4")
        self.assertIn((("Paraglider",), 1), requirements(hylia))

    def test_universal_tracker_finds_the_seeds_koroks(self) -> None:
        passed = BotwWorld.interpret_slot_data(self.world.fill_slot_data())
        again = generate({}, passthrough=passed, seed=7)
        names = {loc.name for loc in again.get_locations(1) if loc.name in self.world.location_name_groups["Koroks"]}
        self.assertEqual(names, {row["name"] for row in self.world.koroks})


class TestKorokLocalFiller(BotwTestBase):
    options = {"korok_sanity": True, "korok_count": 40, "korok_local_filler": 50, "chest_sanity": "check_only",
               "trap_percentage": 100}

    def test_that_share_of_the_koroks_hold_filler_of_this_world(self) -> None:
        koroks = [loc for loc in self.multiworld.get_locations(self.player)
                  if loc.name in self.world.location_name_groups["Koroks"]]
        local = [loc for loc in koroks if loc.locked]
        self.assertEqual(len(local), 20)
        self.assertTrue(all(loc.item.player == self.player and not loc.item.advancement
                            and loc.item.name not in TRAPS for loc in local))

    def test_only_the_others_add_to_the_pool(self) -> None:
        without = generate({"chest_sanity": "check_only", "trap_percentage": 100})
        self.assertEqual(len(generate(self.options).itempool), len(without.itempool) + 20)

    def test_the_default_keeps_most_of_them_local(self) -> None:
        world = generate({"korok_sanity": True, "korok_count": 100}).worlds[1]
        self.assertEqual(sum(world.get_location(row["name"]).locked for row in world.koroks), 95)


class TestKorokProgression(BotwTestBase):
    options = {"korok_sanity": True, "korok_count": 900, "korok_local_filler": 0, "korok_progression": True}

    def test_the_koroks_whose_puzzle_the_items_solve_may_hold_progression(self) -> None:
        excluded = {loc.name for loc in self.multiworld.get_locations(self.player)
                    if loc.progress_type == LocationProgressType.EXCLUDED}
        self.assertEqual(excluded & self.world.location_name_groups["Koroks"],
                         {row["name"] for row in KOROKS if row["no_progression"]})
        distribute_items_restrictive(self.multiworld)
        koroks = [self.multiworld.get_location(row["name"], self.player) for row in KOROKS]
        self.assertTrue(any(loc.item.advancement for loc in koroks))
        self.assertFalse(any(loc.item.advancement for loc in koroks if loc.name in excluded))
        self.assertTrue(self.multiworld.can_beat_game())

    def test_korok_progression_needs_korok_sanity(self) -> None:
        with self.assertRaises(OptionError):
            generate({"korok_progression": True})


class TestQuestSanityOffByDefault(BotwTestBase):
    def test_no_quest_location_by_default(self) -> None:
        locations = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertFalse(locations & self.world.location_name_groups["Quests"])
        self.assertNotEqual(self.world.fill_slot_data()["client_schema"], 15)


class TestSideQuestSanity(BotwTestBase):
    options = {"side_quest_sanity": True, "trap_percentage": 100}

    def test_the_side_quests_are_excluded_locations(self) -> None:
        quests = [loc for loc in self.multiworld.get_locations(self.player)
                  if loc.name in self.world.location_name_groups["Quests"]]
        self.assertEqual({loc.name for loc in quests}, self.world.location_name_groups["Side Quests"])
        self.assertEqual(len(quests), 73)
        self.assertEqual({loc.progress_type for loc in quests}, {LocationProgressType.EXCLUDED})
        self.assertTrue(all(QUEST_ID_BASE < loc.address <= QUEST_ID_BASE + 155 for loc in quests))
        slot_data = self.world.fill_slot_data()
        self.assertEqual((slot_data["side_quest_sanity"], slot_data["shrine_quest_sanity"],
                          slot_data["client_schema"], slot_data["world_schema"]), (1, 0, 15, 8))

    def test_they_bring_no_more_traps(self) -> None:
        with_quests = generate(self.options)
        without = generate({"trap_percentage": 100})
        self.assertEqual(sum(item.name in TRAPS for item in with_quests.itempool),
                         sum(item.name in TRAPS for item in without.itempool))
        self.assertEqual(len(with_quests.itempool), len(without.itempool) + 73)

    def test_a_side_quests_place_is_in_its_rule(self) -> None:
        town = next(row for row in QUESTS if row["name"] == "Gerudo Town - The Thunder Helm")
        self.assertIn((("Gerudo Set",), 1), requirements(town))
        mine = next(row for row in QUESTS if row["name"] == "Southern Mine - Fireproof Lizard Roundup")
        self.assertTrue(mine["heat"])
        self.assertNotEqual(requirements(mine), requirements({**mine, "heat": False}))

    def test_universal_tracker_finds_the_seeds_quests(self) -> None:
        passed = BotwWorld.interpret_slot_data(self.world.fill_slot_data())
        again = generate({}, passthrough=passed, seed=7)
        names = {loc.name for loc in again.get_locations(1) if loc.name in self.world.location_name_groups["Quests"]}
        self.assertEqual(names, self.world.location_name_groups["Side Quests"])


class TestShrineQuestSanity(BotwTestBase):
    options = {"shrine_quest_sanity": True}

    def test_the_shrine_quests_are_excluded_locations_with_their_shrines_logic(self) -> None:
        quests = [loc for loc in self.multiworld.get_locations(self.player)
                  if loc.name in self.world.location_name_groups["Quests"]]
        self.assertEqual({loc.name for loc in quests}, self.world.location_name_groups["Shrine Quests"])
        self.assertEqual(len(quests), 42)
        self.assertEqual({loc.progress_type for loc in quests}, {LocationProgressType.EXCLUDED})
        shrines = {row["name"]: row for row in LOCATIONS}
        for row in QUESTS:
            if row["kind"] == "Shrine":
                self.assertEqual(requirements(row), requirements(shrines[row["shrine"]]))
                self.assertEqual(map_keys(row), map_keys(shrines[row["shrine"]]))
        self.assertEqual(self.world.fill_slot_data()["client_schema"], 15)


class TestCutsceneRemoved(BotwTestBase):
    options = {"cutscene_skip": "removed"}

    def test_the_slot_data_tells_the_pack_builder(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["cutscene_skip"], 2)
