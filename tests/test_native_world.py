"""Integration tests against the official AP core (not test doubles).

Prepare it with tools/prepare_ap_runtime.py before running this suite; the
world's copy in it is refreshed from botw_world/ first.
"""
import json
from argparse import Namespace
from pathlib import Path
import sys
import tempfile
import unittest

RUNTIME = Path(__file__).resolve().parents[1] / ".build/ap-runtime"


@unittest.skipUnless((RUNTIME / "BaseClasses.py").is_file(), "prepare official AP runtime first")
class NativeWorldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.prepare_ap_runtime import sync_world
        sync_world(RUNTIME)             # the current sources, not a stale copy
        sys.path.insert(0, str(RUNTIME))
        import worlds
        if worlds.failed_world_loads:
            raise RuntimeError(f"world import failures: {worlds.failed_world_loads}")

    def make_world(self, seed=0, players=1, **options):
        from BaseClasses import MultiWorld, CollectionState
        from worlds.botw import BotwWorld
        mw = MultiWorld(players)
        mw.set_seed(seed, name=f"BOTW-test-{seed}")
        mw.player_name = {p: f"Tester{p}" for p in mw.player_ids}
        for p in mw.player_ids:
            mw.game[p] = BotwWorld.game
        args = Namespace()
        for name, kind in BotwWorld.options_dataclass.type_hints.items():
            setattr(args, name, {p: kind.from_any(options.get(name, kind.default)) for p in mw.player_ids})
        mw.set_options(args)
        mw.state = CollectionState(mw)
        for phase in ("generate_early", "create_regions", "create_items", "set_rules"):
            for world in mw.worlds.values():
                getattr(world, phase)()
        return mw

    def test_plateau_altar_needs_its_rune_but_terminal_does_not(self):
        from worlds.botw.catalog import PLATEAU_RUNES
        mw = self.make_world()
        for shrine, rune in PLATEAU_RUNES.items():
            self.assertFalse(mw.get_location(shrine, 1).can_reach(mw.state))
        self.assertTrue(mw.get_location("Magnesis Terminal", 1).can_reach(mw.state))
        mw.state.collect(mw.worlds[1].create_item("Magnesis"))
        self.assertTrue(mw.get_location("Oman Au Shrine", 1).can_reach(mw.state))
        self.assertFalse(mw.get_location("Ja Baij Shrine", 1).can_reach(mw.state))

    def test_master_sword_requires_ten_extra_hearts(self):
        mw = self.make_world()
        world = mw.worlds[1]
        mw.state.collect(world.create_item("Paraglider"))
        for _ in range(9):
            mw.state.collect(world.create_item("Heart Container"))
        self.assertFalse(mw.get_location("Master Sword Pedestal", 1).can_reach(mw.state))
        mw.state.collect(world.create_item("Heart Container"))
        self.assertTrue(mw.get_location("Master Sword Pedestal", 1).can_reach(mw.state))

    def test_beast_heart_needs_its_beast_freed_and_is_not_a_beast(self):
        mw = self.make_world(goal_type=1, divine_beasts_required=4)
        world = mw.worlds[1]
        self.assertNotIn("Vah Ruta Heart Container", world.location_name_groups["Divine Beasts"])
        self.assertEqual(len(world.location_name_groups["Divine Beast Hearts"]), 4)
        with self.assertRaises(KeyError):
            mw.get_location("Freed - Vah Ruta Heart Container", 1)
        from worlds.botw.catalog import LOCATIONS, requirements
        row = next(r for r in LOCATIONS if r["name"] == "Vah Ruta Heart Container")
        self.assertIn("Freed - Divine Beast Vah Ruta", requirements(row))
        heart = mw.get_location("Vah Ruta Heart Container", 1)
        for name in ("Paraglider", "Magnesis", "Remote Bomb", "Stasis"):
            mw.state.collect(world.create_item(name))
        mw.state.sweep_for_advancements()
        self.assertFalse(heart.can_reach(mw.state))   # beast not freeable without Cryonis
        mw.state.collect(world.create_item("Cryonis"))
        mw.state.sweep_for_advancements()
        self.assertTrue(mw.state.has("Freed - Divine Beast Vah Ruta", 1))
        self.assertTrue(heart.can_reach(mw.state))

    def test_full_item_state_reaches_every_location(self):
        for goal in range(3):
            mw = self.make_world(goal_type=goal, shrines_required=120)
            state = mw.get_all_state(False)
            self.assertEqual(len(mw.get_unfilled_locations(1)), 152)
            self.assertTrue(all(loc.can_reach(state) for loc in mw.get_locations()))

    def test_beedle_and_stall_items_are_locations_of_their_options(self):
        from Fill import distribute_items_restrictive
        for beedle, stall in ((0, 1), (2, 2)):
            mw = self.make_world(seed=7, beedle_shop_items=beedle, stall_shop_items=stall)
            expected = 152 + 16 * beedle + 14 * stall
            self.assertEqual(len(mw.get_unfilled_locations(1)), expected)
            names = {loc.name for loc in mw.get_locations()}
            self.assertEqual("Kakariko Village - Arrow Stall Item 2" in names, stall == 2)
            distribute_items_restrictive(mw)
            self.assertTrue(mw.can_beat_game())
            with tempfile.TemporaryDirectory() as temp:
                mw.worlds[1].generate_output(temp)
                manifest = json.loads(next(Path(temp).glob("*.apbotw.json")).read_text(
                    encoding="utf-8"))
            self.assertEqual(len(manifest["placements"]), expected)
            self.assertEqual(len(manifest["shops"]), 16 * beedle + 14 * stall)
            self.assertEqual(manifest["slot_data"]["world_schema"], 4)
            self.assertEqual(manifest["slot_data"]["stall_shop_items"], stall)
            stalls = [row for row in manifest["shops"] if row["location_id"] >= 186]
            self.assertEqual(len(stalls), 14 * stall)
            self.assertTrue(all(20 <= row["price"] <= 200 for row in manifest["shops"]))

    def test_seed_fill_solo_and_multiworld(self):
        from Fill import distribute_items_restrictive
        for players in (1, 2):
            for seed in range(20):
                mw = self.make_world(seed=seed, players=players, goal_type=seed % 3,
                                     shrines_required=120, divine_beasts_required=4)
                distribute_items_restrictive(mw)
                self.assertFalse(mw.get_unfilled_locations())
                self.assertTrue(mw.can_beat_game(), (players, seed))
                with tempfile.TemporaryDirectory() as temp:
                    for world in mw.worlds.values():
                        world.generate_output(temp)
                    files = list(Path(temp).glob("*.apbotw.json"))
                    self.assertEqual(len(files), players)
                    for path in files:
                        manifest = json.loads(path.read_text(encoding="utf-8"))
                        self.assertEqual(len(manifest["placements"]), 152)


if __name__ == "__main__":
    unittest.main()
