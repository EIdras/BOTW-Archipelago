"""The Master Sword's pedestal closed when its sword was taken without the pull:
the pack's entry (botw_patch/pedestal.py) and the client's request
(BotwClientRuntime._close_pedestal, _pedestal_tick)."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import unittest

import oead

from botw_client.native_delivery import CemuNativeDeliveryBackend, NativeDeliveryCatalog
from botw_client.runtime import BotwClientRuntime
from botw_patch import pedestal
from botw_patch.delivery_flow import QUIET_EVENT_INFO
from botw_patch.events import read_flow
from botw_patch.resources import unpack

CONTENT = Path(os.environ.get("BOTW_TEST_CONTENT", str(
    Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content")))
ENTRY = {"entry": pedestal.ENTRY, "flow": pedestal.FLOW_NAME, "flags": list(pedestal.FLAGS)}


@unittest.skipUnless((CONTENT / "Pack/TitleBG.pack").is_file(), "Wii U update dump absent")
class EntryTests(unittest.TestCase):
    def test_the_entry_sets_the_pulls_flags_in_turn(self):
        title = oead.Sarc(unpack((CONTENT / "Pack/TitleBG.pack").read_bytes()))
        raw = bytes(title.get_file("EventFlow/OperationGuide.bfevfl").data)
        out, _ = pedestal.add_entry(raw)
        chart = read_flow(out).flowchart
        (entry,) = [e for e in chart.entry_points if e.name == pedestal.ENTRY]
        event, flags = entry.main_event.v, []
        while event is not None:
            self.assertEqual((str(event.data.actor.v.identifier), str(event.data.actor_action.v)),
                             ("EventSystemActor", "Demo_FlagON"))
            flags.append(dict(event.data.params.data))
            event = event.data.nxt.v
        self.assertEqual(flags, [{"FlagName": f, "IsWaitFinish": True} for f in pedestal.FLAGS])
        with self.assertRaises(ValueError):
            pedestal.add_entry(out)

    def test_the_entry_is_a_background_event(self):
        boot = oead.Sarc(unpack((CONTENT / "Pack/Bootup.pack").read_bytes()))
        out, _ = pedestal.add_event_info(bytes(boot.get_file(pedestal.EVENT_INFO).data))
        info = oead.byml.from_binary(unpack(out))
        self.assertEqual(dict(info["OperationGuide<APClosePedestal>"]), QUIET_EVENT_INFO)


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
                                            request=request, lock_factory=None)
        backend._state = lambda: (7, 0, 0)
        return backend, calls

    def test_the_entry_is_requested_from_its_flow_and_an_old_pack_has_none(self):
        with tempfile.TemporaryDirectory() as directory:
            backend, calls = self.backend(directory, {"pedestal": ENTRY})
            self.assertEqual(backend.catalog.pedestal_entry(),
                             (pedestal.FLOW_NAME, pedestal.ENTRY, pedestal.FLAGS))
            self.assertIs(backend.request_pedestal_close(), True)
            self.assertEqual(calls, [("OperationGuide", "APClosePedestal")])
        with tempfile.TemporaryDirectory() as directory:
            backend, calls = self.backend(directory, {"pedestal": ENTRY}, native_return=0)
            self.assertIs(backend.request_pedestal_close(), False)
        with tempfile.TemporaryDirectory() as directory:
            backend, calls = self.backend(directory, {})
            self.assertIsNone(backend.request_pedestal_close())
            self.assertEqual(calls, [])


class Game:
    def __init__(self):
        self.flags = {flag: False for flag in pedestal.FLAGS}
        self.live_writes = []

    def master_sword_pedestal_open(self, flags):
        return not all(self.flags[flag] for flag in flags)

    def close_master_sword_pedestal(self):
        self.live_writes.append("Get_MasterSword_Finish")
        return True


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
        self.result, self.requests = True, 0

        def request_pedestal_close():
            self.requests += 1
            if self.result is True:
                self.game.flags = dict.fromkeys(self.game.flags, True)
            return self.result

        self.catalog = SimpleNamespace(pedestal_entry=lambda: (pedestal.FLOW_NAME, pedestal.ENTRY,
                                                               pedestal.FLAGS))
        self.runtime.deliveries = SimpleNamespace(backend=SimpleNamespace(
            catalog=self.catalog, request_pedestal_close=request_pedestal_close))
        self.now = 100.0
        # The runtime's clock only: asyncio keeps the real one.
        clock = patch("botw_client.runtime.time", SimpleNamespace(monotonic=lambda: self.now))
        clock.start()
        self.addCleanup(clock.stop)

    async def asyncTearDown(self):
        self.directory.cleanup()

    async def test_an_open_pedestal_is_closed_by_the_entry_once(self):
        await self.runtime._close_pedestal()
        await self.runtime._pedestal_tick()
        self.assertEqual(self.requests, 1)
        self.now += 10
        await self.runtime._pedestal_tick()
        self.assertIsNone(self.runtime._pedestal_flags)
        self.assertTrue(any("closed" in line for line in self.logs))
        self.assertEqual(self.game.live_writes, [])
        await self.runtime._pedestal_tick()
        self.assertEqual(self.requests, 1)

    async def test_a_closed_pedestal_asks_nothing(self):
        self.game.flags = dict.fromkeys(self.game.flags, True)
        await self.runtime._close_pedestal()
        await self.runtime._pedestal_tick()
        self.assertEqual((self.requests, self.logs), (0, []))
        self.assertIsNone(self.runtime._pedestal_flags)

    async def test_a_request_not_placed_and_one_that_did_not_run_are_asked_again(self):
        self.result = False
        await self.runtime._close_pedestal()
        await self.runtime._pedestal_tick()
        await self.runtime._pedestal_tick()             # too soon
        self.assertEqual(self.requests, 1)
        self.now += 2
        self.result = None                              # taken, but the flags stay unset
        await self.runtime._pedestal_tick()
        self.assertEqual(self.requests, 2)
        self.now += 10
        self.result = True
        await self.runtime._pedestal_tick()
        self.assertEqual(self.requests, 3)

    async def test_deliveries_go_first(self):
        self.runtime.state["apply_queue"].append(5)
        await self.runtime._close_pedestal()
        await self.runtime._pedestal_tick()
        self.assertEqual(self.requests, 0)

    async def test_a_pack_without_the_entry_writes_live(self):
        self.catalog.pedestal_entry = lambda: None
        await self.runtime._close_pedestal()
        self.assertEqual(self.game.live_writes, ["Get_MasterSword_Finish"])
        self.assertIsNone(self.runtime._pedestal_flags)


if __name__ == "__main__":
    unittest.main()
