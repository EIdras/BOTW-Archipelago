from __future__ import annotations

import asyncio
import json
import zlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

from botw_client.items import load_item_map, validate_item_map
from botw_client.locations import (EXPECTED_LOCATION_COUNT, LocationTarget,
                                   LocationTracker, load_targets)
from botw_client.protocol import (ArchipelagoClient, LocationInfo, NetworkItem,
                                  decode_location_info, decode_network_item,
                                  server_url, server_urls)
from botw_client.runtime import (MESSAGE_MAX_CHARS, BotwClientRuntime, StateStore,
                                 event_settle_seconds)


ROOT = Path(__file__).resolve().parent.parent


class FakeMemory:
    def __init__(self, start, data):
        self.start = start
        self.data = bytearray(data)

    def read(self, address, size):
        offset = address - self.start
        return bytes(self.data[offset:offset + size])


class ClientDataTests(unittest.TestCase):
    def test_item_map_is_exact_and_all_flags_exist_with_expected_types(self):
        self.assertEqual(validate_item_map(), (35, 1))
        mapping = load_item_map()
        gamedata = json.loads((ROOT / "data" / "gamedata.json").read_text(
            encoding="utf-8"))
        types = {name: kind for kind, name in gamedata.values()}
        for name, entry in mapping.items():
            delivery = entry["delivery"]
            if delivery["kind"] == "flags":
                for flag, _ in delivery["writes"]:
                    self.assertEqual(types.get(flag), "bool", (name, flag))
            elif delivery["kind"] in ("counter", "counter_at_least"):
                self.assertEqual(types.get(delivery["flag"]), delivery["type"],
                                 (name, delivery["flag"]))

    def test_locations_are_complete_unique_and_match_gamedata(self):
        targets = load_targets()
        self.assertEqual(len(targets), EXPECTED_LOCATION_COUNT)
        self.assertEqual(len({target.name for target in targets}), EXPECTED_LOCATION_COUNT)
        self.assertEqual(len({target.hash_u32 for target in targets}), EXPECTED_LOCATION_COUNT)
        gamedata = json.loads((ROOT / "data" / "gamedata.json").read_text(
            encoding="utf-8"))
        by_name = {name: int(hash_value) & 0xFFFFFFFF
                   for hash_value, (_, name) in gamedata.items()}
        for target in targets:
            if target.optional:     # custom shop flags: crc32 of their own name
                self.assertEqual(zlib.crc32(target.flag.encode()), target.hash_u32)
                continue
            self.assertEqual(by_name.get(target.flag), target.hash_u32,
                             target.name)

    def test_terminal_checks_are_distinct_from_received_rune_flags(self):
        targets = {target.name: target for target in load_targets()}
        mapping = load_item_map()
        pairs = {
            "Magnesis Terminal": "Magnesis",
            "Remote Bombs Terminal": "Remote Bomb",
            "Stasis Terminal": "Stasis",
            "Cryonis Terminal": "Cryonis",
        }
        for location, item in pairs.items():
            check_flag = targets[location].flag
            received_flags = {mapping[item]["delivery"]["flag"]}
            self.assertNotIn(check_flag, received_flags)

    def test_native_world_ids_are_append_only(self):
        world = json.loads((ROOT / "botw_world" / "data" /
                            "locations.json").read_text(encoding="utf-8"))
        self.assertEqual([entry["id"] for entry in world], list(range(1, 214)))
        self.assertEqual([entry["name"] for entry in world],
                         [target.name for target in load_targets()])
        hearts = {entry["name"]: entry["gamedata_flag"] for entry in world
                  if entry["category"] == "Divine Beast Heart"}
        self.assertEqual(hearts, {
            "Vah Ruta Heart Container": "Get_HeartUtuwa_Water",
            "Vah Rudania Heart Container": "Get_HeartUtuwa_Fire",
            "Vah Medoh Heart Container": "Get_HeartUtuwa_Wind",
            "Vah Naboris Heart Container": "Get_HeartUtuwa_Electric"})
        items = json.loads((ROOT / "botw_world" / "data" /
                            "items.json").read_text(encoding="utf-8"))
        self.assertEqual(next(i for i in items if i["name"] == "Heart Container")["count"], 17)

    def test_location_tracker_reads_one_contiguous_span(self):
        data = (b"\x00\x00\x00\x0a\x00\x00\x00\x00"
                b"\x00\x00\x00\x14\x00\x00\x00\x01")
        process = FakeMemory(100, data)
        targets = [LocationTarget("A", "FlagA", 10),
                   LocationTarget("B", "FlagB", 20)]
        tracker = LocationTracker(process, {10: 100, 20: 108}, targets)
        self.assertEqual(tracker.poll(), ["B"])
        process.data[7] = 1
        self.assertEqual(tracker.poll(), ["A"])

    def test_location_tracker_reports_missing_before_indexing_it(self):
        target = LocationTarget("A", "FlagA", 10)
        with self.assertRaisesRegex(RuntimeError, "FlagA"):
            LocationTracker(FakeMemory(0, b""), {}, [target])

    def test_location_tracker_falls_back_to_live_bool_object(self):
        class Live:
            base = 100
            index = {"bool": {10: 20}}

        process = FakeMemory(100, bytes(28))
        process.data[27] = 3  # value bit at base + object + 7
        target = LocationTarget("A", "FlagA", 10)
        tracker = LocationTracker(process, {}, [target], live=Live())
        self.assertEqual(tracker.poll(), ["A"])


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    def test_url_and_network_item_decoders(self):
        self.assertEqual(server_url("localhost:38281"), "ws://localhost:38281")
        self.assertEqual(server_urls("archipelago.gg:38281"),
                         ["wss://archipelago.gg:38281", "ws://archipelago.gg:38281"])
        self.assertEqual(server_urls("ws://127.0.0.1:38281"), ["ws://127.0.0.1:38281"])
        self.assertEqual(server_urls("wss://archipelago.gg:1234"), ["wss://archipelago.gg:1234"])
        self.assertEqual(decode_network_item([1, 2, 3, 4]), NetworkItem(1, 2, 3, 4))
        self.assertEqual(decode_network_item(
            {"item": 1, "location": 2, "player": 3}), NetworkItem(1, 2, 3, 0))
        self.assertEqual(decode_location_info([1, 2, 3, 4]),
                         LocationInfo(1, 2, 3, 4))

    async def test_connected_accepts_archipelago_named_tuple_json(self):
        client = ArchipelagoClient("localhost:38281", "Simon", log=lambda _: None)
        sent = []

        async def fake_send(*commands):
            sent.extend(commands)

        client.send = fake_send
        client.seed_name = "seed"
        await client._packet({
            "cmd": "Connected", "team": 0, "slot": 1,
            "players": [[0, 1, "Simon", "Simon"]],
            "slot_info": {"1": ["Simon", "Manual_Breath of the Wild_Simon", 0, []]},
            "checked_locations": [7], "slot_data": {"death_link": True},
        })
        self.assertTrue(client.connected)
        self.assertEqual(client.players, {1: "Simon"})
        self.assertEqual(client.sender(NetworkItem(1, 2, 1, 0)),
                         ("Simon", "Manual_Breath of the Wild_Simon"))
        self.assertEqual(sent[0]["cmd"], "GetDataPackage")
        self.assertEqual(sent[1], {"cmd": "ConnectUpdate",
                                   "tags": ["AP", "DeathLink"]})

    async def test_scouts_messages_and_deathlink_are_structured(self):
        client = ArchipelagoClient("localhost:38281", "Simon", log=lambda _: None)
        client._scout_expected = {2}
        await client._packet({"cmd": "LocationInfo", "locations": [[1, 2, 3, 4]]})
        self.assertEqual(client.scouted_locations[2], LocationInfo(1, 2, 3, 4))
        self.assertTrue(client.scout_event.is_set())
        await client._packet({
            "cmd": "PrintJSON", "type": "Chat", "data": [
                {"text": "Alice", "type": "player_id", "color": "magenta"},
                {"text": ": hello", "type": "text"}]})
        message = client.messages.get_nowait()
        self.assertEqual(message.text, "Alice: hello")
        self.assertEqual(message.kind, "Chat")
        self.assertEqual(message.nodes[0]["color"], "magenta")
        await client._packet({
            "cmd": "Bounced", "tags": ["DeathLink"],
            "data": {"time": 12.5, "source": "Alice", "cause": "fell"}})
        death = client.deathlinks.get_nowait()
        self.assertEqual((death.source, death.cause), ("Alice", "fell"))
        # Same timestamp is a replay, not a second death.
        await client._packet({
            "cmd": "Bounced", "tags": ["DeathLink"],
            "data": {"time": 12.5, "source": "Alice", "cause": "fell"}})
        self.assertTrue(client.deathlinks.empty())

    async def test_index_zero_replaces_the_full_received_inventory(self):
        client = ArchipelagoClient("localhost:38281", "Simon", log=lambda _: None)
        client.received_items = {
            0: NetworkItem(1, 2, 3, 0),
            1: NetworkItem(4, 5, 6, 0),
        }
        await client._packet({"cmd": "ReceivedItems", "index": 0,
                              "items": [[7, 8, 9, 0]]})
        self.assertEqual(client.received_items,
                         {0: NetworkItem(7, 8, 9, 0)})

    async def test_outgoing_deathlink_uses_bounce_and_updates_latch(self):
        client = ArchipelagoClient("localhost:38281", "Simon", log=lambda _: None)
        client.death_link_enabled = True
        sent = []

        async def fake_send(*commands):
            sent.extend(commands)

        client.send = fake_send
        await client.send_death("Simon fell")
        self.assertEqual(sent[0]["cmd"], "Bounce")
        self.assertEqual(sent[0]["tags"], ["DeathLink"])
        self.assertEqual(sent[0]["data"]["cause"], "Simon fell")
        self.assertEqual(client.last_death_link, sent[0]["data"]["time"])

    @unittest.skipUnless(importlib.util.find_spec("aiohttp"), "aiohttp absent")
    async def test_websocket_handshake_and_data_package(self):
        from aiohttp import web

        received = []
        extensions = []

        async def handler(request):
            extensions.append(request.headers.get("Sec-WebSocket-Extensions", ""))
            websocket = web.WebSocketResponse(compress=15)
            await websocket.prepare(request)
            await websocket.send_json([{"cmd": "RoomInfo", "seed_name": "seed"}])
            received.extend(await websocket.receive_json())
            await websocket.send_json([{
                "cmd": "Connected", "team": 0, "slot": 1,
                "players": [[0, 1, "Simon", "Simon"]],
                "slot_info": {"1": ["Simon", "Manual_Breath of the Wild_Simon", 0, []]},
                "checked_locations": [],
            }])
            received.extend(await websocket.receive_json())
            await websocket.send_json([{
                "cmd": "DataPackage", "data": {"games": {
                    "Manual_Breath of the Wild_Simon": {
                        "item_name_to_id": {"Paraglider": 1},
                        "location_name_to_id": {"Tah Muhl Shrine": 2},
                    }
                }}
            }])
            async for _ in websocket:
                pass
            return websocket

        application = web.Application()
        application.router.add_get("/", handler)
        runner = web.AppRunner(application)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        client = ArchipelagoClient(f"127.0.0.1:{port}", "Simon",
                                   log=lambda _: None)
        try:
            await client.connect()
            # No scheme given: wss:// failed on this plain server, ws:// answered and is kept.
            self.assertEqual((client.url, client.urls),
                             (f"ws://127.0.0.1:{port}", [f"ws://127.0.0.1:{port}"]))
            await asyncio.wait_for(client.data_package_event.wait(), 2)
            self.assertEqual([packet["cmd"] for packet in received],
                             ["Connect", "GetDataPackage"])
            self.assertEqual(client.item_name_by_id, {1: "Paraglider"})
            self.assertIn("permessage-deflate", extensions[0])
            self.assertTrue(client.websocket.compress)
        finally:
            await client.close()
            await runner.cleanup()


class StateTests(unittest.TestCase):
    def test_state_is_scoped_by_seed_team_and_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = StateStore(path)
            first = store.select("seed", 0, 1)
            first["applied"].append(3)
            store.save()
            reopened = StateStore(path)
            self.assertEqual(reopened.select("seed", 0, 1)["applied"], [3])
            self.assertEqual(reopened.select("seed", 0, 2)["applied"], [])

    def test_state_is_also_scoped_by_data_package(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            store = StateStore(path)
            store.select("seed", 0, 1, "package-a")["applied"].append(4)
            store.save()
            reopened = StateStore(path)
            self.assertEqual(
                reopened.select("seed", 0, 1, "package-a")["applied"], [4])
            self.assertEqual(
                reopened.select("seed", 0, 1, "package-b")["applied"], [])


class RuntimeSafetyTests(unittest.IsolatedAsyncioTestCase):
    def test_ap_messages_are_single_and_truncated(self):
        self.assertEqual(BotwClientRuntime._message_pages("  short   text "),
                         ["short text"])
        pages = BotwClientRuntime._message_pages("x" * 100)
        self.assertEqual(len(pages), 1)
        self.assertEqual(len(pages[0]), MESSAGE_MAX_CHARS)
        self.assertTrue(pages[0].endswith("..."))

    def test_event_fallback_prioritizes_shrine_flow_and_defers_towers(self):
        self.assertLess(event_settle_seconds("Oman Au Shrine"), 1.0)
        self.assertGreater(event_settle_seconds("Great Plateau Tower"), 10.0)

    def test_game_cursor_requeues_items_after_save_rollback(self):
        class Game:
            cursor = (2, 0)

            def bind_ap_session(self, _token):
                return None

            def delivery_position(self):
                return self.cursor

        class AP:
            received_items = {
                index: NetworkItem(1, 100 + index, 1, 0)
                for index in range(4)
            }

        with tempfile.TemporaryDirectory() as directory:
            runtime = BotwClientRuntime(
                "localhost:38281", "Simon",
                state_path=Path(directory) / "state.json", log=lambda _: None)
            runtime.game = Game()
            runtime.ap = AP()
            runtime._session_token = 1
            runtime.state = runtime.state_store.select("seed", 0, 1, "package")
            runtime.state["applied"] = [0, 1, 2, 3]
            runtime._discover_received()
            self.assertEqual(runtime.state["applied"], [0, 1])
            self.assertEqual(runtime.state["apply_queue"], [2, 3])
            runtime.game.cursor = (0, 0)
            runtime._discover_received()
            self.assertEqual(runtime.state["applied"], [])
            self.assertEqual(runtime.state["apply_queue"], [0, 1, 2, 3])

    def test_external_state_fallback_keeps_client_usable_without_modded_gamedata(self):
        class Game:
            save_ledger_available = False

            def bind_ap_session(self, _token):
                return None

        class AP:
            received_items = {
                index: NetworkItem(1, 100 + index, 1, 0)
                for index in range(4)
            }

        with tempfile.TemporaryDirectory() as directory:
            runtime = BotwClientRuntime(
                "localhost:38281", "Simon",
                state_path=Path(directory) / "state.json", log=lambda _: None)
            runtime.game = Game()
            runtime.ap = AP()
            runtime._session_token = 1
            runtime.state = runtime.state_store.select("seed", 0, 1, "package")
            runtime.state["applied"] = [0, 1]
            runtime._discover_received()
            self.assertEqual(runtime.state["applied"], [0, 1])
            self.assertEqual(runtime.state["apply_queue"], [2, 3])
            self.assertEqual(runtime._delivery_position(), (2, 0))

    async def test_active_loop_sends_goal_and_always_disarms(self):
        class Cave:
            def __init__(self):
                self.disarmed = 0

            def sub_disarm(self):
                self.disarmed += 1

        class Game:
            def __init__(self):
                self.cave = Cave()
                self.blocks = []
                self.polls = 0
                self.cursor = (0, 0)

            def bind_ap_session(self, _token):
                return None

            def delivery_position(self):
                return self.cursor

            def set_delivery_position(self, index, step=0):
                self.cursor = (index, step)

            def healthy(self):
                return True

            def safe_for_delivery(self):
                return True

            def is_dead(self):
                return False

            def set_blocking(self, enabled):
                self.blocks.append(enabled)

            def poll_locations(self):
                self.polls += 1
                return ["Defeat Calamity Ganon"] if self.polls == 1 else []

        class AP:
            game = "Manual_Breath of the Wild_Simon"
            slot_data = {}
            connected = True
            received_items = {}
            checked_locations = set()
            location_id_by_name = {"Defeat Calamity Ganon": 145}
            scouted_locations = {145: LocationInfo(1, 145, 1, 0)}
            death_link_enabled = False

            def __init__(self):
                self.checks = []
                self.goals = 0
                self.messages = asyncio.Queue()
                self.deathlinks = asyncio.Queue()

            def item_name(self, item):
                return "Paraglider"

            async def send_checks(self, names):
                self.checks.extend(names)
                return []

            async def send_goal(self):
                self.goals += 1

        with tempfile.TemporaryDirectory() as directory:
            runtime = BotwClientRuntime(
                "localhost:38281", "Simon", state_path=Path(directory) / "state.json",
                log=lambda _: None)
            runtime.game = Game()
            runtime.ap = AP()
            runtime.state = runtime.state_store.select("seed", 0, 1)
            task = asyncio.create_task(runtime._active_loop())
            await asyncio.sleep(0.3)
            runtime.stop()
            await task
            self.assertEqual(runtime.ap.checks, ["Defeat Calamity Ganon"])
            self.assertEqual(runtime.ap.goals, 1)
            # Mailbox 0x0BADF00E makes this a selective Spirit Orb lease.
            self.assertIn(True, runtime.game.blocks)
            self.assertEqual(runtime.game.blocks[-1], False)
            self.assertGreater(runtime.game.cave.disarmed, 0)


if __name__ == "__main__":
    unittest.main()
