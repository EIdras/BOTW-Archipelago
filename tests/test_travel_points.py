"""A shrine's travel point opened by the game's GameData setters."""
import struct
import unittest

from botw_client import travel_points as travel
from botw_client.cucco_swarm import HEAP_HOLDER, NEW_IN_HEAP
from tools import build_poptracker as poptracker

BLOCK = 0x40000000
TERMINAL = "MainField_DgnObj_EntranceTerminal_A_01_742860559"
SHRINES = [("MapTower_06", "Dungeon058", TERMINAL),
           ("MapTower_13", "Dungeon039", "MainField_DgnObj_EntranceTerminal_A_01_4206609530")]


class FakeGame:
    """Guest memory, the live flags and the GameData manager's calls."""

    def __init__(self, **flags):
        self.memory = {}
        self.flags = {"IsGet_PlayerStole2": 1, "MapTower_06": 1, "Open_Dungeon058": 0,
                      "Location_Dungeon058": 0, TERMINAL: 0, **flags}
        self.handles = {}
        self.sets = []
        self.refuse = None
        self.put(travel.MANAGER, struct.pack(">I", 0x3F000000))
        self.put(HEAP_HOLDER, struct.pack(">I", 0x30000000))
        self.put(0x30000010, struct.pack(">I", 0x31000000))

    def put(self, address, data):
        for offset, byte in enumerate(data):
            self.memory[address + offset] = byte

    def read(self, address, size):
        return bytes(self.memory.get(address + i, 0) for i in range(size))

    def get(self, flag, kind):
        return self.flags.get(flag)

    def call(self, address, *args):
        if address == NEW_IN_HEAP:
            return BLOCK
        if address in travel.HANDLES.values():
            pointer = struct.unpack(">I", self.read(args[1], 4))[0]
            name = self.read(pointer, 0x80).split(b"\0", 1)[0].decode("ascii")
            return self.handles.setdefault(name, len(self.handles) + 1)
        if address in travel.SETTERS.values():
            flag = next(name for name, handle in self.handles.items() if handle == args[1])
            if flag == self.refuse:
                return 0
            self.flags[flag] = args[0]
            self.sets.append(flag)
            return 1
        raise AssertionError(f"unexpected call {address:#x}")

    def open(self, shrine="Dungeon058", terminal=TERMINAL):
        return travel.open_point(self.read, self.put, self.call, self.get, shrine, terminal)


class DueTests(unittest.TestCase):
    def test_a_map_held_opens_its_shrine(self):
        self.assertEqual(travel.due(FakeGame().get, SHRINES), ("Dungeon058", TERMINAL))

    def test_nothing_before_the_paraglider(self):
        self.assertIsNone(travel.due(FakeGame(IsGet_PlayerStole2=0).get, SHRINES))

    def test_nothing_for_a_map_not_held_or_a_point_open(self):
        self.assertIsNone(travel.due(FakeGame(MapTower_06=0).get, SHRINES))
        self.assertIsNone(travel.due(FakeGame(Open_Dungeon058=1).get, SHRINES))
        # Unreadable: not due.
        self.assertIsNone(travel.due(FakeGame(Open_Dungeon058=None).get, SHRINES))


class OpenTests(unittest.TestCase):
    def test_the_terminal_first_open_last(self):
        game = FakeGame()
        self.assertEqual(game.open(), "opened")
        self.assertEqual(game.sets, [TERMINAL, "Location_Dungeon058", "Open_Dungeon058"])

    def test_a_visited_shrine_keeps_its_visits(self):
        game = FakeGame(Location_Dungeon058=3)
        self.assertEqual(game.open(), "opened")
        self.assertEqual(game.sets, [TERMINAL, "Open_Dungeon058"])
        self.assertEqual(game.flags["Location_Dungeon058"], 3)

    def test_an_open_point_is_not_written(self):
        game = FakeGame(Open_Dungeon058=1)
        self.assertEqual(game.open(), "already")
        self.assertEqual(game.sets, [])

    def test_a_refused_write_leaves_the_point_closed(self):
        game = FakeGame()
        game.refuse = "Location_Dungeon058"
        self.assertEqual(game.open(), "write Location_Dungeon058")
        self.assertEqual(game.flags["Open_Dungeon058"], 0)
        # Asked again, the opening is done whole.
        game.refuse = None
        self.assertEqual(game.open(), "opened")


UPDATE = poptracker.update_content()


@unittest.skipUnless(UPDATE is not None and (UPDATE / "Pack/Bootup.pack").is_file(), "update absent")
class GameDataTests(unittest.TestCase):
    def test_each_travel_shrine_stands_clear_of_the_other_regions(self):
        # Warped there, Link must not land in a closed neighbour's fog nor
        # message: Dunba Taag stood 21 m from Tabantha.
        import json
        from botw_client.region_border import Areas
        from botw_client.region_return import CLEAR
        from tools.map_regions import area_regions, map_towers
        grid = map_towers(UPDATE)
        areas = Areas(grid, area_regions(grid))
        positions = json.loads(poptracker.POSITIONS.read_text(encoding="utf-8"))
        for region, shrine in poptracker.catalog().TRAVEL_SHRINES.items():
            x, z = positions[shrine]
            self.assertEqual(region, areas.region_at(x, z), shrine)
            self.assertIsNone(areas.nearest(x, z, set(areas.regions) - {region}, CLEAR), shrine)

    def test_the_game_lets_the_client_write_each_travel_flag(self):
        # The game's setters refuse a flag a program may not write (Jee Noh's
        # Location_ is one): the world picks shrines whose three flags it may.
        import oead
        from botw_patch.resources import unpack
        boot = oead.Sarc((UPDATE / "Pack/Bootup.pack").read_bytes())
        found = {}
        for file in oead.Sarc(unpack(bytes(boot.get_file("GameData/gamedata.ssarc").data))).get_files():
            for key, entries in oead.byml.from_binary(bytes(file.data)).items():
                kind = {"bool_data": "bool", "s32_data": "s32"}.get(key)
                for entry in entries if kind else ():
                    found[str(entry["DataName"])] = (kind, bool(entry["IsProgramWritable"]))
        cat = poptracker.catalog()
        names = {row["name"]: row["gamedata_flag"].removeprefix("Clear_") for row in cat.LOCATIONS}
        for shrine, terminal in cat.TRAVEL_TERMINALS.items():
            with self.subTest(shrine=shrine):
                self.assertEqual(found.get(f"Location_{names[shrine]}"), ("s32", True))
                self.assertEqual(found.get(f"Open_{names[shrine]}"), ("bool", True))
                self.assertEqual(found.get(terminal), ("bool", True))


class ClientTravelTests(unittest.IsolatedAsyncioTestCase):
    def runtime(self, slot_data, outcomes):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from botw_client.runtime import BotwClientRuntime
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.lines, self.asked = [], []
        game = SimpleNamespace(item_map={"Ridgeland Map": {"delivery": {"kind": "map", "flag": "MapTower_06"}}})
        runtime = BotwClientRuntime("unused:1", "test", state_path=Path(temporary.name) / "state.json",
                                    game_factory=lambda: game, log=self.lines.append)
        runtime.game = game
        runtime.ap = SimpleNamespace(slot_data=slot_data)

        def opener(shrines):
            self.asked.append(shrines)
            return outcomes.pop(0)
        runtime.deliveries = SimpleNamespace(backend=SimpleNamespace(open_travel_point=opener))
        return runtime

    async def test_each_map_held_opens_its_shrine_one_at_a_time(self):
        runtime = self.runtime({"travel_shrines": {"Ridgeland Map": ["Dungeon058", TERMINAL]}},
                               [("Dungeon058", "opened"), None])
        await runtime._travel_tick()
        self.assertEqual(self.asked, [[("MapTower_06", "Dungeon058", TERMINAL)]])
        self.assertEqual(self.lines, ["travel point opened: Dungeon058"])
        # The game shows the shrine's name before the next.
        await runtime._travel_tick()
        self.assertEqual(len(self.asked), 1)

    async def test_a_wait_is_not_logged_a_failure_once(self):
        runtime = self.runtime({"travel_shrines": {"Ridgeland Map": ["Dungeon058", TERMINAL]}},
                               [("Dungeon058", "an entry running"), ("Dungeon058", "write Open_Dungeon058"),
                                ("Dungeon058", "write Open_Dungeon058")])
        for _ in range(3):
            runtime._travel_retry_after = 0.0
            await runtime._travel_tick()
        self.assertEqual(self.lines, ["travel point of Dungeon058 not opened yet (write Open_Dungeon058)"])

    async def test_a_failure_waits_and_lets_the_others_go_first(self):
        hateno = "MainField_DgnObj_EntranceTerminal_A_01_4206609530"
        runtime = self.runtime({"travel_shrines": {"Hateno Map": ["Dungeon039", hateno],
                                                   "Ridgeland Map": ["Dungeon058", TERMINAL]}},
                               [("Dungeon039", "write Open_Dungeon039"), ("Dungeon058", "opened")])
        runtime.game.item_map["Hateno Map"] = {"delivery": {"kind": "map", "flag": "MapTower_13"}}
        await runtime._travel_tick()
        await runtime._travel_tick()
        self.assertEqual(len(self.asked), 1)
        runtime._travel_retry_after = 0.0
        await runtime._travel_tick()
        self.assertEqual([shrine for _, shrine, _ in self.asked[1]], ["Dungeon058", "Dungeon039"])

    async def test_nothing_without_the_option(self):
        runtime = self.runtime({}, [])
        await runtime._travel_tick()
        self.assertEqual(self.asked, [])


if __name__ == "__main__":
    unittest.main()
