import struct
import unittest

from botw_client import item_drop
from botw_client.cucco_swarm import (CREATOR, HEAP_HOLDER, NEW_IN_HEAP, PACK_ADD, PACK_CTOR,
                                     PLAYER_INFO, REQUEST_CREATE)
from botw_client.delivery_plan import droppable


class FakeGame:
    """Guest memory as {address: bytes}, Link at (10, 20, 30) facing +x."""

    def __init__(self):
        self.memory = {}
        self.calls = []
        self.u32(PLAYER_INFO, 0x1000)
        self.u32(0x1000 + 0x30, 0x2000)
        self.u32(CREATOR, 0x3000)
        self.u32(HEAP_HOLDER, 0x4000)
        self.u32(0x4000 + 0x10, 0x5000)
        for axis, (place, forward) in enumerate(((10.0, 1.0), (20.0, 0.0), (30.0, 0.0))):
            self.write(0x2000 + item_drop.POSITION + 0x10 * axis, struct.pack(">f", place))
            self.write(0x2000 + item_drop.FORWARD + 0x10 * axis, struct.pack(">f", forward))

    def u32(self, address, value):
        self.write(address, value.to_bytes(4, "big"))

    def write(self, address, data):
        for offset, byte in enumerate(data):
            self.memory[address + offset] = byte

    def read(self, address, size):
        return bytes(self.memory.get(address + i, 0) for i in range(size))

    def call(self, address, *args):
        self.calls.append((address, args))
        return 0x9000 if address == NEW_IN_HEAP else 1


class ItemDropTests(unittest.TestCase):
    def test_the_item_is_created_by_link_above_his_feet(self):
        game = FakeGame()
        self.assertEqual(item_drop.drop(game.read, game.write, game.call, "Weapon_Bow_033"), "ok")
        self.assertEqual([address for address, _ in game.calls],
                         [NEW_IN_HEAP, PACK_CTOR, PACK_ADD, REQUEST_CREATE])
        _address, (creator, text, heap, handle, pack, *_rest) = game.calls[-1]
        self.assertEqual((creator, heap, handle, pack), (0x3000, 0x5000, 0, 0x9000))
        self.assertEqual(game.read(text, 15), b"Weapon_Bow_033\0")
        _address, (_pack, value, key, size, _align) = game.calls[2]
        self.assertEqual(size, 0xC)
        # Nothing in the pack's room, which the game builds the pack over.
        for address in (text, value, key):
            self.assertGreaterEqual(address, 0x9000 + item_drop.PACK_ROOM)
        key_text = int.from_bytes(game.read(key, 4), "big")
        self.assertEqual(game.read(key_text, 3), b"@P\0")
        at = struct.unpack(">fff", game.read(value, 12))
        self.assertEqual(at, (10.0 + item_drop.AHEAD, 20.0 + item_drop.UP, 30.0))

    def test_no_player_no_creation(self):
        game = FakeGame()
        game.u32(PLAYER_INFO, 0)
        self.assertEqual(item_drop.drop(game.read, game.write, game.call, "Weapon_Bow_033"), "player")
        self.assertEqual(game.calls, [])

    def test_only_the_kinds_measured_on_the_ground_drop(self):
        self.assertTrue(all(map(droppable, ("Weapon_Lsword_036", "Weapon_Bow_033",
                                            "Weapon_Shield_030", "Obj_ArrowBundle_A_01"))))
        self.assertFalse(any(map(droppable, ("Weapon_Sword_070", "Armor_044_Upper",
                                             "Animal_Insect_F", "Obj_DungeonClearSeal", None))))


if __name__ == "__main__":
    unittest.main()
