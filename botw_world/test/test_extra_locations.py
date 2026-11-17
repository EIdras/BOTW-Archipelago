"""The chests and bosses (shrine_chests, field_chests, boss_kills), the bonus items
and the Progressive Horse."""
from collections import Counter

from . import BotwTestBase
from .test_tracker import generate
from ..catalog import ITEMS, LOCATIONS, categories

EXTRA = {"Shrine Chest", "Chest", "Boss"}
BONUS = Counter({row["name"]: int(row.get("count", 1)) for row in ITEMS if row.get("bonus")})


class TestNoneByDefault(BotwTestBase):
    def test_no_chest_or_boss_and_some_bonus_items(self) -> None:
        names = {location.name for location in self.multiworld.get_locations(self.player)}
        for group in ("Shrine Chests", "Field Chests", "Bosses"):
            self.assertFalse(names & self.world.location_name_groups[group])
        self.assertEqual(self.world.fill_slot_data()["extra_locations"], [])
        pool = Counter(item.name for item in self.multiworld.itempool)
        self.assertEqual(pool["Progressive Horse"], 5)
        self.assertEqual((pool["Epona"], pool["Master Cycle Zero"]), (0, 0))
        self.assertTrue(0 < sum(pool[name] for name in BONUS) < sum(BONUS.values()))


class TestDrawn(BotwTestBase):
    options = {"shrine_chests": 20, "field_chests": 100, "boss_kills": 10}

    def test_each_option_draws_its_count(self) -> None:
        locations = {location.address for location in self.multiworld.get_locations(self.player)}
        rows = {row["id"]: row for row in LOCATIONS}
        drawn = Counter(next(iter(categories(rows[i]) & EXTRA)) for i in locations if i in rows
                        and categories(rows[i]) & EXTRA)
        self.assertEqual(drawn, {"Shrine Chest": 20, "Chest": 100, "Boss": 10})
        self.assertEqual(sorted(self.world.extra_locations),
                         sorted(i for i in locations if i in rows and categories(rows[i]) & EXTRA))
        slot = self.world.fill_slot_data()
        self.assertEqual((slot["client_schema"], slot["world_schema"]), (13, 6))
        self.assertEqual(slot["extra_locations"], sorted(self.world.extra_locations))

    def test_every_bonus_item_once_there_is_room(self) -> None:
        pool = Counter(item.name for item in self.multiworld.itempool)
        self.assertEqual({name: pool[name] for name in BONUS}, dict(BONUS))

    def test_no_goal_counts_a_chest(self) -> None:
        self.assertFalse(self.world.location_name_groups["Shrines"] & self.world.location_name_groups["Shrine Chests"])


class TestNormalModeChests(BotwTestBase):
    options = {"field_chests": 1312}

    def test_no_master_mode_chest_in_normal_mode(self) -> None:
        from ..catalog import MASTER_MODE_ONLY
        self.assertEqual(len(MASTER_MODE_ONLY), 118)
        self.assertFalse(self.world.extra_locations & MASTER_MODE_ONLY)
        from ..catalog import NEVER_DRAWN
        self.assertEqual(len(self.world.extra_locations), 1312 - len(MASTER_MODE_ONLY | NEVER_DRAWN))
        self.assertFalse(self.world.fill_slot_data()["master_mode"])


class TestMasterModeChests(BotwTestBase):
    options = {"field_chests": 1312, "master_mode": True}

    def test_every_chest_in_master_mode(self) -> None:
        from ..catalog import MASTER_MODE_ONLY
        from ..catalog import NEVER_DRAWN
        self.assertLessEqual(MASTER_MODE_ONLY - NEVER_DRAWN, self.world.extra_locations)
        self.assertEqual(len(self.world.extra_locations), 1312 - len(NEVER_DRAWN))
        self.assertTrue(self.world.fill_slot_data()["master_mode"])


class TestChestLogic(BotwTestBase):
    options = {"field_chests": 1312, "master_mode": True}

    def test_never_drawn_and_all_shrines(self) -> None:
        from BaseClasses import CollectionState
        from ..catalog import NEVER_DRAWN
        self.assertEqual(len(NEVER_DRAWN), 36)
        self.assertFalse(self.world.extra_locations & NEVER_DRAWN)
        self.assertEqual(len(self.world.extra_locations), 1312 - 36)
        temple = next(r for r in LOCATIONS if "once all 120 shrines" in r["notes"])
        location = self.multiworld.get_location(temple["name"], self.player)
        state = CollectionState(self.multiworld)
        for item in self.multiworld.itempool:
            if item.advancement:
                state.collect(item, True)
        shrines = [loc for loc in self.multiworld.get_locations(self.player) if loc.name.startswith("Cleared - ")]
        self.assertEqual(len(shrines), 120)
        for shrine in shrines[:-1]:
            state.collect(shrine.item, True)
        self.assertFalse(location.can_reach(state))
        state.collect(shrines[-1].item, True)
        self.assertTrue(location.can_reach(state))


class TestTrackerRegenerates(BotwTestBase):
    options = {"field_chests": 30, "boss_kills": 5}

    def test_the_same_chests_and_bosses_from_the_slot_data(self) -> None:
        slot = self.world.fill_slot_data()
        again = generate(passthrough=slot, seed=99).worlds[1]
        self.assertEqual(again.extra_locations, self.world.extra_locations)
