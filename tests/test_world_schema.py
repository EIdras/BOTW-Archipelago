import tempfile
import unittest
from pathlib import Path

from botw_client.locations import SCHEMA_LOCATION_COUNTS, WORLD_SCHEMA, load_targets
from botw_client.runtime import BotwClientRuntime, FatalClientError

HEARTS = ["Vah Ruta Heart Container", "Vah Rudania Heart Container",
          "Vah Medoh Heart Container", "Vah Naboris Heart Container"]


class CatalogueSchemaTests(unittest.TestCase):
    def test_schemas_are_prefixes_of_the_append_only_catalogue(self):
        old, new = load_targets(world_schema=1), load_targets(world_schema=2)
        shops, stalls = load_targets(world_schema=3), load_targets()
        self.assertEqual(WORLD_SCHEMA, 4)
        self.assertEqual((len(old), len(new), len(shops), len(stalls)),
                         (SCHEMA_LOCATION_COUNTS[1], SCHEMA_LOCATION_COUNTS[2],
                          SCHEMA_LOCATION_COUNTS[3], SCHEMA_LOCATION_COUNTS[4]))
        self.assertEqual(new[:len(old)], old)
        self.assertEqual(shops[:len(new)], new)
        self.assertEqual(stalls[:len(shops)], shops)
        self.assertEqual(old[-1].name, "Cryonis Terminal")
        self.assertEqual([target.name for target in new[len(old):]], HEARTS)
        self.assertTrue(all(t.optional and t.kind == "s32" for t in stalls[len(new):]))
        self.assertEqual(stalls[len(shops)].name, "Rito Village - General Stall Item 1")
        with self.assertRaises(ValueError):
            load_targets(world_schema=5)


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
                self.runtime(directory, "Breath of the Wild", {"world_schema": 9})._world_schema()

    def test_manual_schema_comes_from_its_data_package(self):
        old = [target.name for target in load_targets(world_schema=1)]
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.runtime(directory, "Manual_BOTW", names=old)._world_schema(), 1)
            self.assertEqual(self.runtime(directory, "Manual_BOTW",
                                          names=old + HEARTS)._world_schema(), 2)
            shops = [t.name for t in load_targets(world_schema=3)][len(old) + len(HEARTS):]
            self.assertEqual(self.runtime(directory, "Manual_BOTW",
                                          names=old + HEARTS + shops)._world_schema(), 3)
            stalls = [t.name for t in load_targets()][len(old) + len(HEARTS) + len(shops):]
            self.assertEqual(self.runtime(directory, "Manual_BOTW",
                                          names=old + HEARTS + shops + stalls)._world_schema(), 4)

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


if __name__ == "__main__":
    unittest.main()
