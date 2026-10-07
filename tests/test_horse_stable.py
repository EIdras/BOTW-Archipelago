"""A horse registered at the stables by the game's GameData setters."""
import struct
import unittest

from botw_client import horse_stable as stable
from botw_client.cucco_swarm import HEAP_HOLDER, NEW_IN_HEAP

BLOCK, STRINGS = 0x40000000, 0x40008000


class FakeManager:
    """Guest memory and the GameData manager's handle, get and set calls."""

    def __init__(self, actors):
        self.memory = {}
        self.arrays = {flag: [""] * 6 for flag in stable.FIELDS}
        self.arrays["Horse_ActorName"][:len(actors)] = actors
        self.handles = {}
        self.sets = []
        self.put(stable.MANAGER, struct.pack(">I", 0x3F000000))
        self.put(HEAP_HOLDER, struct.pack(">I", 0x30000000))
        self.put(0x30000010, struct.pack(">I", 0x31000000))

    def put(self, address, data):
        for offset, byte in enumerate(data):
            self.memory[address + offset] = byte

    def read(self, address, size):
        return bytes(self.memory.get(address + i, 0) for i in range(size))

    def text(self, safestring):
        pointer = struct.unpack(">I", self.read(safestring, 4))[0]
        return self.read(pointer, 0x40).split(b"\0", 1)[0].decode("utf-8")

    def call(self, address, *args):
        if address == NEW_IN_HEAP:
            return BLOCK
        if address == stable.HANDLE:
            return self.handles.setdefault(self.text(args[1]), len(self.handles) + 1)
        flag = next(name for name, handle in self.handles.items() if handle == args[1])
        if address == stable.GET:
            raw = self.arrays[flag][args[2]].encode("utf-8") + b"\0"
            self.put(STRINGS, raw)
            self.put(args[0], struct.pack(">I", STRINGS))
            return 1
        if address == stable.SET:
            self.arrays[flag][args[2]] = self.text(args[0])
            self.sets.append(flag)
            return 1
        raise AssertionError(f"unexpected call {address:#x}")

    def register(self):
        return stable.register(self.read, self.put, self.call, "GameRomHorseEpona", "Épona",
                               "Horse_Link_Mane", "GameRomHorseSaddle_06", "GameRomHorseReins_06")


class RegisterTests(unittest.TestCase):
    def test_epona_goes_in_the_first_free_slot_her_actor_last(self):
        game = FakeManager(["GameRomHorse00", ""])
        self.assertEqual(game.register(), "registered")
        self.assertEqual([game.arrays[flag][1] for flag in stable.FIELDS],
                         ["Épona", "Horse_Link_Mane", "GameRomHorseSaddle_06",
                          "GameRomHorseReins_06", "GameRomHorseEpona"])
        # A slot is taken only once all is written.
        self.assertEqual(game.sets[-1], "Horse_ActorName")
        self.assertEqual(game.arrays["Horse_ActorName"][0], "GameRomHorse00")

    def test_a_registered_epona_is_not_written_twice(self):
        game = FakeManager(["GameRomHorse00", "GameRomHorseEpona"])
        self.assertEqual(game.register(), "already")
        self.assertEqual(game.sets, [])

    def test_full_stables_write_nothing(self):
        game = FakeManager(["GameRomHorse00"] * 5)
        self.assertEqual(game.register(), "full")
        self.assertEqual(game.sets, [])


if __name__ == "__main__":
    unittest.main()
