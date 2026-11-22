"""The client's side of chest_sanity: the chests' locations; with ap_items, their
AP items taken out of the pouch by the pack's entries (botw_patch/chests.py),
once a chest's flag rises and, as a safety net, when the pouch still holds one;
with check_only, and for a shrine's chest, which keeps its treasure, the client's
window for what an opened chest sent."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from botw_client.locations import CHEST_NUMBERS, CHESTS_SENT_WITH, chest_number
from botw_client.native_delivery import CemuNativeDeliveryBackend, NativeDeliveryCatalog
from botw_client.runtime import CHEST_HOLD_SECONDS, BotwClientRuntime
from botw_patch import chests

ENTRY = {"flow": chests.QUIET_FLOW, "entry_prefix": chests.ENTRY + "_", "id_base": chests.CHEST_ID_BASE,
         "held": [list(held) for held in chests.HELD]}


class CatalogueTests(unittest.TestCase):
    def test_a_pouch_item_names_its_chest(self):
        self.assertEqual(chest_number("AP_Chest_0007"), 7)
        self.assertEqual(chest_number(chests.actor(1190)), 1190)
        for name in ("AP_Chest", "AP_Chest_7", "AP_Chest_00x7", "AP_Shop_154", "Item_Ore_F"):
            with self.subTest(name=name):
                self.assertIsNone(chest_number(name))

    def test_a_chest_location_names_the_item_the_pack_put_in_its_chest(self):
        rows = json.loads((Path(__file__).resolve().parents[1] / "botw_world/data/chests.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(CHEST_NUMBERS, {row["name"]: row["number"] for row in rows})


class BackendTests(unittest.TestCase):
    def backend(self, directory, catalog_extra, native_return=1):
        path = Path(directory) / "catalog.json"
        path.write_text(json.dumps({"schema": 1, "flow": "Demo007_1", "items": {},
                                    "cursor": "(received_index << 8) | step",
                                    **catalog_extra}), encoding="utf-8")
        calls = []

        def request(process, cave, number, checkpoint, custom_text=False, *, flow, entry):
            calls.append((flow, entry))
            return {"native_return": native_return}

        game = SimpleNamespace(process=SimpleNamespace(pid=1), cave=None,
                               frame_tick=lambda: 100, safe_for_delivery=lambda: True)
        backend = CemuNativeDeliveryBackend(game, "seed", 1, 7, catalog=NativeDeliveryCatalog(path),
                                            request=request, lock_factory=None, in_world=lambda: True)
        backend._state = lambda: (7, 0, 0)
        return backend, calls

    def test_the_chests_entry_is_requested_and_a_pack_without_chests_has_none(self):
        with tempfile.TemporaryDirectory() as directory:
            backend, calls = self.backend(directory, {"chests": ENTRY})
            self.assertIs(backend.request_chest_removal(7), True)
            self.assertEqual(calls, [("OperationGuide", "APChestRemove_0007")])
        with tempfile.TemporaryDirectory() as directory:
            backend, _calls = self.backend(directory, {"chests": ENTRY}, native_return=0)
            self.assertIs(backend.request_chest_removal(7), False)
        with tempfile.TemporaryDirectory() as directory:
            backend, calls = self.backend(directory, {})
            self.assertIsNone(backend.request_chest_removal(7))
            self.assertEqual(calls, [])

    def test_the_catalog_says_which_chests_hold_their_item(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = self.backend(directory, {"chests": ENTRY})[0].catalog
            self.assertEqual([catalog.chest_holds_item(n) for n in (1, 1190, 1191, 1395, 1396, 1430, 1431)],
                             [True, True, False, False, True, True, False])
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(self.backend(directory, {})[0].catalog.chest_holds_item(7))


class Game:
    def __init__(self):
        self.pouch = []
        self.flags = []

    def pouch_chest_items(self):
        return [chest_number(name) for name in self.pouch]

    def poll_locations(self):
        flags, self.flags = self.flags, []
        return flags


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.game = Game()
        self.logs = []
        self.runtime = BotwClientRuntime(
            "localhost:1", "Player", state_path=Path(self.directory.name) / "state.json",
            log=self.logs.append, game_factory=lambda: self.game, tip_factory=object)
        self.runtime.game = self.game
        self.runtime.state = self.runtime.state_store.select("seed", 0, 1)
        self.result, self.requests, self.in_world = True, [], True

        def request_chest_removal(number):
            self.requests.append(number)
            if self.result is True and chests.actor(number) in self.game.pouch:
                self.game.pouch.remove(chests.actor(number))
            return self.result

        self.catalog = SimpleNamespace(chest_removal=lambda: (chests.QUIET_FLOW, chests.ENTRY + "_"),
                                       chest_holds_item=chests.holds_item)
        self.runtime.deliveries = SimpleNamespace(backend=SimpleNamespace(
            catalog=self.catalog, request_chest_removal=request_chest_removal, playing=lambda: self.in_world))
        self.now = 100.0
        clock = patch("botw_client.runtime.time", SimpleNamespace(monotonic=lambda: self.now))
        clock.start()
        self.addCleanup(clock.stop)

    async def asyncTearDown(self):
        self.directory.cleanup()

    def chest(self, number=7):
        return next(name for name, n in CHEST_NUMBERS.items() if n == number)

    async def test_an_opened_chest_is_checked_and_its_item_taken_out(self):
        name = self.chest()
        self.game.pouch, self.game.flags = [chests.actor(7)], [name]
        self.runtime.ap = SimpleNamespace(connected=False, location_id_by_name={name: 10007},
                                          scouted_locations={10007: object()}, checked_locations=set())
        await self.runtime._poll_locations()
        self.assertIn(name, self.runtime.state["pending_checks"])
        # The chest's own window showed its item: no window of the client's.
        self.assertEqual(self.runtime.state["location_display_queue"], [])
        await self.runtime._chest_tick()
        self.assertEqual((self.requests, self.game.pouch), ([7], []))
        await self.runtime._chest_tick()
        self.assertEqual(self.requests, [7])

    async def test_an_item_left_in_the_pouch_is_taken_out_after_the_hold(self):
        self.game.pouch = [chests.actor(12), "Item_Ore_F"]
        await self.runtime._chest_tick()
        self.assertEqual(self.requests, [])
        self.now += CHEST_HOLD_SECONDS
        await self.runtime._chest_tick()
        self.assertEqual((self.requests, self.game.pouch), ([12], ["Item_Ore_F"]))

    async def test_nothing_is_read_out_of_the_world_and_a_refused_request_is_asked_again(self):
        self.game.pouch, self.in_world = [chests.actor(12)], False
        self.now += 60
        await self.runtime._chest_tick()
        self.assertEqual(self.requests, [])
        self.in_world, self.result = True, False
        self.now += 3
        await self.runtime._chest_tick()            # first seen in the world
        self.now += CHEST_HOLD_SECONDS
        await self.runtime._chest_tick()
        await self.runtime._chest_tick()
        self.assertEqual(self.requests, [12, 12])
        self.result = True
        await self.runtime._chest_tick()
        self.assertEqual((self.requests, self.game.pouch), ([12, 12, 12], []))

    async def test_a_pack_without_chests_asks_nothing(self):
        self.catalog.chest_removal = lambda: None
        self.game.pouch = [chests.actor(12)]
        self.now += 60
        await self.runtime._chest_tick()
        self.assertEqual(self.requests, [])

    async def test_with_check_only_an_opened_chest_is_said_and_nothing_taken_out(self):
        # The pack left the chests alone: the client's window says what one sent.
        self.catalog.chest_removal = lambda: None
        name = self.chest()
        self.game.pouch, self.game.flags = [chests.actor(7)], [name]
        self.runtime.ap = SimpleNamespace(connected=False, location_id_by_name={name: 10007},
                                          scouted_locations={10007: object()}, checked_locations=set())
        await self.runtime._poll_locations()
        self.assertIn(name, self.runtime.state["pending_checks"])
        self.assertEqual(self.runtime.state["location_display_queue"], [10007])
        self.assertEqual(self.runtime._chest_removals, [])
        self.now += 60
        await self.runtime._chest_tick()
        self.assertEqual(self.requests, [])

    async def test_with_ap_items_a_shrine_chest_is_said_and_nothing_taken_out(self):
        # The pack left the shrines' chests alone: they keep their treasure.
        number = chests.CHEST_COUNT + 1
        name = self.chest(number)
        self.game.flags = [name]
        self.runtime.ap = SimpleNamespace(connected=False, location_id_by_name={name: 10000 + number},
                                          scouted_locations={10000 + number: object()}, checked_locations=set())
        await self.runtime._poll_locations()
        self.assertEqual(self.runtime.state["location_display_queue"], [10000 + number])
        self.assertEqual(self.runtime._chest_removals, [])

    async def test_open_chests_of_a_seed_without_them_are_not_said(self):
        self.runtime._session_locations = {"Paraglider"}
        self.game.flags = [self.chest(), self.chest(8)]
        await self.runtime._poll_locations()
        self.assertFalse(any("ignored" in line for line in self.logs))
        self.assertEqual(self.runtime.state["pending_checks"], [])

    def beast(self):
        beast = "Divine Beast Vah Ruta"
        ids = {beast: 140, **{name: 10000 + CHEST_NUMBERS[name] for name in CHESTS_SENT_WITH[beast]}}
        self.runtime.ap = SimpleNamespace(connected=False, location_id_by_name=ids,
                                          scouted_locations={i: object() for i in ids.values()},
                                          checked_locations=set())
        return beast, CHESTS_SENT_WITH[beast]

    async def test_a_freed_beast_sends_the_chests_left_inside_without_a_window(self):
        beast, inside = self.beast()
        self.assertEqual(len(inside), 7)
        self.game.flags = [inside[0]]           # opened before the beast was freed
        await self.runtime._poll_locations()
        queued = list(self.runtime.state["location_display_queue"])
        self.game.flags = [beast]
        await self.runtime._poll_locations()
        self.assertEqual(self.runtime.state["pending_checks"], [inside[0], beast, *inside[1:]])
        # The beast's own window, none for the chests left inside; only the opened
        # chest's item (ap_items: a beast's chest holds it) is taken out.
        self.assertEqual(len(self.runtime.state["location_display_queue"]), len(queued) + 1)
        self.assertEqual(self.runtime._chest_removals, [CHEST_NUMBERS[inside[0]]])
        self.game.flags = [beast, *inside[:1]]  # the next session's first read
        await self.runtime._poll_locations()
        self.assertEqual(len(self.runtime.state["pending_checks"]), 8)

    async def test_a_freed_beast_sends_no_chest_in_a_seed_without_them(self):
        beast, _inside = self.beast()
        self.runtime._session_locations = {beast}
        self.game.flags = [beast]
        await self.runtime._poll_locations()
        self.assertEqual(self.runtime.state["pending_checks"], [beast])
        self.assertFalse(any("left inside" in line for line in self.logs))


if __name__ == "__main__":
    unittest.main()
