import tempfile
import unittest
from pathlib import Path

from botw_client import gamedata_table
from botw_client.locations import (BOSS_NAMES, CHEST_NUMBERS, KOROK_NAMES, OFFERING_NAMES, QUEST_NAMES, SCHEMA_LOCATION_COUNTS,
                                   WORLD_SCHEMA, load_targets)
from botw_client.runtime import BotwClientRuntime, FatalClientError

HEARTS = ["Vah Ruta Heart Container", "Vah Rudania Heart Container",
          "Vah Medoh Heart Container", "Vah Naboris Heart Container"]

NEEDS_TABLE = unittest.skipUnless(gamedata_table.available(), "the GameData flag table is read from the game")


class CatalogueSchemaTests(unittest.TestCase):
    @NEEDS_TABLE
    def test_schemas_are_prefixes_of_the_append_only_catalogue(self):
        old, new = load_targets(world_schema=1), load_targets(world_schema=2)
        shops, stalls = load_targets(world_schema=3), load_targets(world_schema=4)
        upgrades, chests = load_targets(world_schema=5), load_targets(world_schema=6)
        koroks, quests, offerings = load_targets(world_schema=7), load_targets(world_schema=8), load_targets(world_schema=9)
        bosses = load_targets()
        self.assertEqual(WORLD_SCHEMA, 10)
        self.assertEqual((len(old), len(new), len(shops), len(stalls), len(upgrades)),
                         (SCHEMA_LOCATION_COUNTS[1], SCHEMA_LOCATION_COUNTS[2],
                          SCHEMA_LOCATION_COUNTS[3], SCHEMA_LOCATION_COUNTS[4],
                          SCHEMA_LOCATION_COUNTS[5]))
        self.assertEqual(chests[:len(upgrades)], upgrades)
        self.assertEqual(len(chests), SCHEMA_LOCATION_COUNTS[6] + len(CHEST_NUMBERS))
        self.assertEqual(koroks[:len(chests)], chests)
        self.assertEqual(len(koroks), len(chests) + len(KOROK_NAMES))
        self.assertEqual(quests[:len(koroks)], koroks)
        self.assertEqual(len(quests), len(koroks) + len(QUEST_NAMES))
        self.assertEqual(offerings[:len(quests)], quests)
        self.assertEqual([target.name for target in offerings[len(quests):]], list(OFFERING_NAMES))
        self.assertEqual(bosses[:len(offerings)], offerings)
        self.assertEqual({target.name for target in bosses[len(offerings):]}, set(BOSS_NAMES))
        self.assertEqual(len(bosses), len(offerings) + len(BOSS_NAMES))
        self.assertEqual(upgrades[:len(stalls)], stalls)
        # Purah's upgrades: saved bools of the mod's own; the Ballads' ends: the game's.
        self.assertEqual([(t.name.rsplit(" - ", 1)[-1], t.kind, t.optional) for t in upgrades[len(stalls):]], [
            ("Sheikah Sensor Upgrade", "bool", True), ("Remote Bomb Upgrade", "bool", True),
            ("Stasis Upgrade", "bool", True), ("Revali's Song", "bool", False),
            ("Mipha's Song", "bool", False), ("Daruk's Song", "bool", False),
            ("Urbosa's Song", "bool", False)])
        self.assertEqual(new[:len(old)], old)
        self.assertEqual(shops[:len(new)], new)
        self.assertEqual(stalls[:len(shops)], shops)
        self.assertEqual(old[-1].name, "Cryonis Terminal")
        self.assertEqual([target.name for target in new[len(old):]], HEARTS)
        self.assertTrue(all(t.optional and t.kind == "s32" for t in stalls[len(new):]))
        self.assertEqual(stalls[len(shops)].name, "Rito Village - General Stall Item 1")
        with self.assertRaises(ValueError):
            load_targets(world_schema=11)


class RuntimeSchemaTests(unittest.IsolatedAsyncioTestCase):
    def runtime(self, directory, game, slot_data=None, names=()):
        runtime = BotwClientRuntime("localhost:38281", "Player",
                                    state_path=Path(directory) / "state.json",
                                    log=lambda _: None)

        class AP:
            connected = False
            checked_locations = set()
            scouted_locations = set()
            received_items = {}

        runtime.ap = AP()
        runtime.ap.game = game
        runtime.ap.slot_data = slot_data or {}
        runtime.ap.location_id_by_name = {name: index for index, name in enumerate(names, 1)}
        return runtime

    def test_native_world_schema_comes_from_slot_data(self):
        with tempfile.TemporaryDirectory() as directory:
            for slot_data, expected in (({"world_schema": 2}, 2), ({"world_schema": 1}, 1),
                                        ({}, 1)):
                runtime = self.runtime(directory, "Breath of the Wild", slot_data)
                self.assertEqual(runtime._world_schema(), expected)
            with self.assertRaises(FatalClientError):
                self.runtime(directory, "Breath of the Wild", {"world_schema": 11})._world_schema()

    @NEEDS_TABLE
    def test_manual_schema_comes_from_its_data_package(self):
        old = [target.name for target in load_targets(world_schema=1)]
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.runtime(directory, "Manual_BOTW", names=old)._world_schema(), 1)
            self.assertEqual(self.runtime(directory, "Manual_BOTW",
                                          names=old + HEARTS)._world_schema(), 2)
            shops = [t.name for t in load_targets(world_schema=3)][len(old) + len(HEARTS):]
            self.assertEqual(self.runtime(directory, "Manual_BOTW",
                                          names=old + HEARTS + shops)._world_schema(), 3)
            stalls = [t.name for t in load_targets(world_schema=4)][len(old) + len(HEARTS) + len(shops):]
            self.assertEqual(self.runtime(directory, "Manual_BOTW",
                                          names=old + HEARTS + shops + stalls)._world_schema(), 4)
            upgrades = [t.name for t in load_targets(world_schema=5)][SCHEMA_LOCATION_COUNTS[4]:]
            self.assertEqual(self.runtime(directory, "Manual_BOTW",
                                          names=old + HEARTS + shops + stalls + upgrades)._world_schema(), 5)
            chests = [t.name for t in load_targets(world_schema=6)][SCHEMA_LOCATION_COUNTS[5]:]
            self.assertEqual(self.runtime(directory, "Manual_BOTW", names=old + HEARTS + shops + stalls
                                          + upgrades + chests)._world_schema(), 6)
            self.assertEqual(self.runtime(directory, "Manual_BOTW", names=old + HEARTS + shops + stalls
                                          + upgrades + chests + sorted(KOROK_NAMES))._world_schema(), 7)
            self.assertEqual(self.runtime(directory, "Manual_BOTW", names=old + HEARTS + shops + stalls + upgrades
                                          + chests + sorted(KOROK_NAMES) + sorted(QUEST_NAMES))._world_schema(), 8)
            self.assertEqual(self.runtime(directory, "Manual_BOTW", names=old + HEARTS + shops + stalls + upgrades
                                          + chests + sorted(KOROK_NAMES) + sorted(QUEST_NAMES)
                                          + list(OFFERING_NAMES))._world_schema(), 9)
            self.assertEqual(self.runtime(directory, "Manual_BOTW", names=old + HEARTS + shops + stalls + upgrades
                                          + chests + sorted(KOROK_NAMES) + sorted(QUEST_NAMES)
                                          + list(OFFERING_NAMES) + sorted(BOSS_NAMES))._world_schema(), 10)

    @NEEDS_TABLE
    async def test_a_check_absent_from_the_seed_is_not_sent(self):
        old = [target.name for target in load_targets(world_schema=1)]

        class Game:
            def poll_locations(self):
                return ["Vah Ruta Heart Container", "Great Plateau Tower"]

        with tempfile.TemporaryDirectory() as directory:
            logs = []
            runtime = self.runtime(directory, "Manual_BOTW", names=old)
            runtime.log = logs.append
            runtime.game = Game()
            runtime._session_locations = set(old)
            runtime.native_mode = True
            runtime.state = runtime.state_store.select("seed", 0, 1, "package")
            await runtime._poll_locations()
            self.assertEqual(runtime.state["pending_checks"], ["Great Plateau Tower"])
            self.assertTrue(any("Vah Ruta Heart Container" in line for line in logs))

    @NEEDS_TABLE
    async def test_a_korok_quest_offering_or_boss_found_in_a_seed_without_it_is_neither_sent_nor_said(self):
        old, korok, quest = [target.name for target in load_targets(world_schema=1)], min(KOROK_NAMES), min(QUEST_NAMES)
        offering, boss = OFFERING_NAMES[0], min(BOSS_NAMES)

        class Game:
            def poll_locations(self):
                return [korok, quest, offering, boss, "Great Plateau Tower"]

        with tempfile.TemporaryDirectory() as directory:
            logs = []
            runtime = self.runtime(directory, "Manual_BOTW", names=old)
            runtime.log = logs.append
            runtime.game = Game()
            runtime._session_locations = set(old)
            runtime.native_mode = True
            runtime.state = runtime.state_store.select("seed", 0, 1, "package")
            await runtime._poll_locations()
            self.assertEqual(runtime.state["pending_checks"], ["Great Plateau Tower"])
            self.assertFalse(any(korok in line or quest in line or offering in line or boss in line for line in logs))


if __name__ == "__main__":
    unittest.main()
