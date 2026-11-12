"""The safety net of an unrecorded shop purchase (botw_client/pouch_watch.py)."""
import asyncio
import struct
import unittest

from botw_client.pouch_watch import (HOLD_SECONDS, POUCH_HASH, POUCH_SIZE, SHOP_ITEMS, PouchMoved,
                                     PouchWatch, StrayShopItems)
from botw_client.shop_catalog import LOCATIONS as BEEDLE
from botw_client.stall_catalog import LOCATIONS as STALLS

HEAP = 0x30000000
HASH_AT = 0x138


class Memory:
    """A fake guest memory: TriggerParam, one array slot holding the pouch's
    PtrArray of string64 flag objects."""

    def __init__(self, names, slot=13):
        self.data = {}
        self.next = HEAP
        self.elements = [self.object(name) for name in names + [""] * (POUCH_SIZE - len(names))]
        pouch = self.array(self.elements)
        outer = self.array([self.alloc(0x40), pouch])
        self.tp = self.alloc(0x200)
        self.write(self.tp + 0x04 + 12 * slot, struct.pack(">III", *struct.unpack(">III", self.read(outer, 12))))

    def alloc(self, size):
        address, self.next = self.next, self.next + size + 0x10
        self.write(address, bytes(size))
        return address

    def write(self, address, raw):
        for i, byte in enumerate(raw):
            self.data[address + i] = byte

    def read(self, address, size):
        return bytes(self.data.get(address + i, 0) for i in range(size))

    def array(self, pointers):
        data = self.alloc(4 * len(pointers))
        self.write(data, struct.pack(f">{len(pointers)}I", *pointers))
        head = self.alloc(12)
        self.write(head, struct.pack(">III", len(pointers), len(pointers), data))
        return head

    def object(self, name):
        obj = self.alloc(0x200)
        self.set_name(obj, name)
        self.write(obj + HASH_AT, POUCH_HASH.to_bytes(4, "big"))
        return obj

    def set_name(self, obj, name):
        self.write(obj + HASH_AT - 0x40, name.encode().ljust(64, b"\0"))


class PouchWatchTests(unittest.TestCase):
    def test_the_pouch_is_found_and_read_up_to_its_first_empty_name(self):
        memory = Memory(["Weapon_Sword_002", "AP_Shop_203", "Item_Fruit_A"])
        watch = PouchWatch(memory.read, memory.tp)
        self.assertEqual(watch.names(), ["Weapon_Sword_002", "AP_Shop_203", "Item_Fruit_A"])

    def test_a_pouch_written_between_two_reads_is_not_trusted(self):
        memory = Memory(["Item_Fruit_A"])
        watch = PouchWatch(memory.read, memory.tp)
        reads = []

        def read(address, size):
            reads.append(address)
            if len(reads) == 3:     # the second pass sees another name
                memory.set_name(memory.elements[0], "Item_Fruit_B")
            return memory.read(address, size)

        watch.read = read
        self.assertIsNone(watch.names())

    def test_a_pouch_no_longer_where_it_was_is_found_again(self):
        memory = Memory(["Item_Fruit_A"])
        watch = PouchWatch(memory.read, memory.tp)
        memory.write(memory.elements[0] + HASH_AT, bytes(4))
        with self.assertRaises(PouchMoved):
            watch.names()

    def test_no_pouch_no_watch(self):
        memory = Memory([])
        memory.write(memory.tp + 0x04 + 12 * 13, bytes(12))
        with self.assertRaises(RuntimeError):
            PouchWatch(memory.read, memory.tp)

    def test_every_shop_item_is_known_by_its_actor(self):
        self.assertEqual(len(SHOP_ITEMS), len(BEEDLE) + len(STALLS))
        self.assertEqual(SHOP_ITEMS["AP_Shop_203"].name, "Kakariko Village - Arrow Stall Item 2")


class StrayShopItemsTests(unittest.TestCase):
    def test_an_item_left_unrecorded_is_due_after_the_hold(self):
        stray = StrayShopItems()
        self.assertEqual(stray.observe({203: 0}, 100.0, True), [])
        self.assertEqual(stray.observe({203: 0}, 100.0 + HOLD_SECONDS - 1, True), [])
        self.assertEqual(stray.observe({203: 0}, 100.0 + HOLD_SECONDS, True), [203])
        self.assertEqual(stray.since, {})

    def test_a_purchase_recorded_or_an_item_gone_starts_again(self):
        stray = StrayShopItems()
        stray.observe({203: 0}, 0.0, True)
        stray.observe({}, 5.0, True)                    # out of the pouch once
        self.assertEqual(stray.observe({203: 0}, 21.0, True), [])
        stray.observe({203: 1}, 30.0, True)             # recorded: the tracker sends it
        self.assertEqual(stray.observe({203: 0}, 50.0, True), [])
        stray.observe({203: None}, 60.0, True)          # flag unread
        self.assertEqual(stray.observe({203: 0}, 79.0, True), [])

    def test_only_the_time_link_spends_in_the_world_counts(self):
        # Beedle's list open for a minute holds the item until it is recorded.
        stray = StrayShopItems()
        stray.observe({203: 0}, 0.0, False)
        self.assertEqual(stray.observe({203: 0}, 60.0, False), [])
        self.assertEqual(stray.observe({203: 0}, 61.0, True), [])
        stray.observe({203: 0}, 70.0, False)            # a dialogue: starts again
        self.assertEqual(stray.observe({203: 0}, 75.0, True), [])
        self.assertEqual(stray.observe({203: 0}, 75.0 + HOLD_SECONDS, True), [203])


class RuntimeTests(unittest.TestCase):
    def runtime(self, found, *, checked=(), observed=(), seed=(203, 154), playing=True):
        from botw_client.runtime import BotwClientRuntime
        names = {location.id: location.name for location in SHOP_ITEMS.values()}

        class Ap:
            seed_locations = set(seed)
            checked_locations = set(checked)

            def location_name(self, location):
                return names[location]

        class Backend:
            def playing(self):
                return playing

        class Deliveries:
            backend = Backend()

        class Game:
            def pouch_shop_items(self):
                return found

        class Store:
            def save(self):
                pass

        runtime = BotwClientRuntime.__new__(BotwClientRuntime)
        runtime.ap, runtime.game, runtime.state_store = Ap(), Game(), Store()
        runtime.deliveries = Deliveries()
        runtime.state = {"observed_checks": list(observed), "pending_checks": []}
        runtime.lines = []
        runtime.log = runtime.lines.append
        runtime._stray_shop_items = StrayShopItems(hold=0.0)
        runtime._pouch_poll_after = 0.0
        runtime._queue_location_display = lambda name: None
        runtime.flushed = 0

        async def flush():
            runtime.flushed += 1

        runtime._flush_checks = flush
        return runtime

    def test_an_unrecorded_item_of_the_seed_sends_its_check(self):
        runtime = self.runtime({203: {"flag": 0, "shown": 1}})
        asyncio.run(runtime._poll_pouch())
        self.assertEqual(runtime.state["pending_checks"], ["Kakariko Village - Arrow Stall Item 2"])
        self.assertEqual(runtime.flushed, 1)
        self.assertTrue(any("left in the pouch" in line and "flag 0" in line for line in runtime.lines))

    def test_no_check_for_an_item_checked_recorded_or_not_of_the_seed(self):
        for found, kwargs in (({203: {"flag": 0, "shown": 1}}, {"checked": (203,)}),
                              ({203: {"flag": 0, "shown": 1}},
                               {"observed": ("Kakariko Village - Arrow Stall Item 2",)}),
                              ({203: {"flag": 1, "shown": 0}}, {}),
                              ({203: {"flag": None, "shown": None}}, {}),
                              ({203: {"flag": 0, "shown": 1}}, {"seed": (154,)}),
                              ({203: {"flag": 0, "shown": 1}}, {"playing": False}),
                              (None, {})):
            runtime = self.runtime(found, **kwargs)
            asyncio.run(runtime._poll_pouch())
            self.assertEqual(runtime.state["pending_checks"], [], (found, kwargs))


if __name__ == "__main__":
    unittest.main()
