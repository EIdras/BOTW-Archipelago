"""DeathLink: the pack's entry (botw_patch/death_link.py) and the client's
two directions (BotwClientRuntime._deathlink_tick)."""
import asyncio
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
import zlib

import oead

from botw_client import death_cause, runtime as runtime_module
from botw_client.ap_journal import death_link_line
from botw_client.native_delivery import CemuNativeDeliveryBackend, NativeDeliveryCatalog
from botw_client.protocol import DeathLinkEvent
from botw_client.runtime import BotwClientRuntime
from botw_patch import death_link
from botw_patch.delivery_flow import QUIET_EVENT_INFO
from botw_patch.events import read_flow
from botw_patch.resources import unpack

CONTENT = Path(os.environ.get("BOTW_TEST_CONTENT", str(
    Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content")))


@unittest.skipUnless((CONTENT / "Pack/TitleBG.pack").is_file(), "Wii U update dump absent")
class EntryTests(unittest.TestCase):
    def test_the_entry_runs_one_lethal_damage_on_the_player(self):
        title = oead.Sarc(unpack((CONTENT / "Pack/TitleBG.pack").read_bytes()))
        raw = bytes(title.get_file("EventFlow/OperationGuide.bfevfl").data)
        out, _ = death_link.add_entry(raw)
        chart = read_flow(out).flowchart
        (entry,) = [e for e in chart.entry_points if e.name == death_link.ENTRY]
        mark = entry.main_event.v.data
        self.assertEqual((str(mark.actor.v.identifier), str(mark.actor_action.v)),
                         ("EventSystemActor", "Demo_FlagON"))
        self.assertEqual(dict(mark.params.data), {"FlagName": "APDeathLinkKill", "IsWaitFinish": True})
        hit = mark.nxt.v.data
        self.assertEqual((str(hit.actor.v.identifier), str(hit.actor_action.v)),
                         ("GameROMPlayer", "Demo_ApplyDamage"))
        self.assertEqual(dict(hit.params.data), {"IsWaitFinish": True, "Value": 1000})
        alive = hit.nxt.v.data
        self.assertEqual(str(alive.actor_query.v), "ComparePlayerHeart")
        self.assertEqual(dict(alive.params.data), {"Threshold": 1})
        # Survived: the flag goes off. Dead: no case, the flag stays set.
        self.assertEqual(set(alive.cases), {1})
        clear = alive.cases[1].v.data
        self.assertEqual((str(clear.actor_action.v), dict(clear.params.data)),
                         ("Demo_FlagOFF", {"FlagName": "APDeathLinkKill", "IsWaitFinish": True}))
        self.assertIsNone(clear.nxt.v)
        with self.assertRaises(ValueError):
            death_link.add_entry(out)

    def test_the_flag_is_a_volatile_bool(self):
        boot = oead.Sarc(unpack((CONTENT / "Pack/Bootup.pack").read_bytes()))
        out, _ = death_link.add_flag(bytes(boot.get_file(death_link.GAMEDATA).data))
        archive = oead.Sarc(unpack(out))
        found = [dict(entry) for f in archive.get_files() if f.name.startswith("/bool_data_")
                 for entry in oead.byml.from_binary(bytes(f.data))["bool_data"]
                 if entry["DataName"] == "APDeathLinkKill"]
        self.assertEqual(len(found), 1)
        self.assertEqual((found[0]["IsSave"], int(found[0]["InitValue"])), (False, 0))

    def test_attacker_names_come_from_the_game_texts(self):
        names = death_link.attacker_names((CONTENT / death_link.MESSAGES).read_bytes())
        self.assertEqual(names["Enemy_Bokoblin_Junior"], "Bokoblin")
        self.assertEqual(names["Enemy_Lynel_Senior"], "White-Maned Lynel")
        self.assertTrue(all(name.isprintable() for name in names.values()))

    def test_the_entry_is_a_background_event(self):
        boot = oead.Sarc(unpack((CONTENT / "Pack/Bootup.pack").read_bytes()))
        raw = bytes(boot.get_file(death_link.EVENT_INFO).data)
        out, _ = death_link.add_event_info(raw)
        info = oead.byml.from_binary(unpack(out))
        self.assertEqual(dict(info["OperationGuide<APDeathLink>"]), QUIET_EVENT_INFO)


class JournalTests(unittest.TestCase):
    def test_line(self):
        self.assertEqual(death_link_line("Alice", "Alice fell {2}"),
                         "{0}DeathLink{/}: Alice fell (2)")
        self.assertEqual(death_link_line("Alice", ""), "{0}DeathLink{/}: Alice died")


class BackendTests(unittest.TestCase):
    def backend(self, directory, catalog_extra, native_return=1):
        import json
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

    def test_the_death_entry_is_requested_from_its_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            backend, calls = self.backend(directory, {"death_link": {
                "entry": "APDeathLink", "flow": "OperationGuide"}})
            self.assertIs(backend.request_death(), True)
            self.assertEqual(calls, [("OperationGuide", "APDeathLink")])

    def test_a_refused_request_is_asked_again_and_an_old_pack_has_none(self):
        with tempfile.TemporaryDirectory() as directory:
            backend, _ = self.backend(directory, {"death_link": {
                "entry": "APDeathLink", "flow": "OperationGuide"}}, native_return=0)
            self.assertIs(backend.request_death(), False)
        with tempfile.TemporaryDirectory() as directory:
            backend, calls = self.backend(directory, {})
            self.assertIsNone(backend.request_death())
            self.assertEqual(calls, [])

    def test_the_flag_is_read_from_the_live_game_data(self):
        with tempfile.TemporaryDirectory() as directory:
            backend, _ = self.backend(directory, {"death_link": {
                "entry": "APDeathLink", "flow": "OperationGuide", "flag": "APDeathLinkKill"}})
            values = {}
            backend.game.live = SimpleNamespace(get=lambda h, kind: values.get((h, kind)))
            self.assertIsNone(backend.killed_by_death_link())      # unreadable
            values[(zlib.crc32(b"APDeathLinkKill"), "bool")] = 1
            self.assertIs(backend.killed_by_death_link(), True)
        with tempfile.TemporaryDirectory() as directory:
            backend, _ = self.backend(directory, {"death_link": {
                "entry": "APDeathLink", "flow": "OperationGuide"}})
            backend.game.live = SimpleNamespace(get=lambda h, kind: 1)
            self.assertIsNone(backend.killed_by_death_link())      # no flag in the pack


class CauseTests(unittest.TestCase):
    NAMES = {"Enemy_Bokoblin_Junior": "Bokoblin", "Enemy_Octarock": "Octorok",
             "Enemy_Lynel_Senior": "White-Maned Lynel"}

    def text(self, cause, raw=None, killer=None):
        return death_cause.death_text("Zelda", cause, raw, killer, self.NAMES)

    def test_texts(self):
        self.assertEqual(self.text(0, 0, "Enemy_Bokoblin_Junior"), "Zelda was slain by a Bokoblin")
        self.assertEqual(self.text(0, 0, "Enemy_Octarock"), "Zelda was slain by an Octorok")
        self.assertEqual(self.text(0, 0, None), "Zelda died in Hyrule")
        self.assertEqual(self.text(0, 0, "Unknown_Actor"), "Zelda died in Hyrule")
        self.assertEqual(self.text(0, 1, None), "Zelda died of the heat")
        self.assertEqual(self.text(4, 5), "Zelda burned to death")
        self.assertEqual(self.text(1, 2), "Zelda froze to death")
        self.assertEqual(self.text(8, 9), "Zelda fell to their death")
        self.assertEqual(self.text(7, 0x10008), "Zelda drowned")
        self.assertEqual(self.text(9, 0x20000, "RemoteBomb"), "Zelda was caught in their own bomb blast")
        self.assertEqual(self.text(9, 0x20000, "Enemy_Bokoblin_Junior"),
                         "Zelda was blown up by a Bokoblin")
        self.assertEqual(self.text(9, 0x20000, None), "Zelda was blown up")
        self.assertEqual(self.text(None), "Zelda died in Hyrule")

    def test_the_attacker_is_read_through_player_info(self):
        memory = {0x10463F38: (0x20000000).to_bytes(4, "big"),
                  0x20000030: (0x30000000).to_bytes(4, "big"),
                  0x30000974: (0x31000000).to_bytes(4, "big"),
                  0x31000000: b"Enemy_Bokoblin_Junior\0garbage"}

        def read(guest, size):
            return memory.get(guest, b"")[:size] or None

        actor = death_cause.player(read)
        self.assertEqual(actor, 0x30000000)
        self.assertEqual(death_cause.attacker(read, actor), "Enemy_Bokoblin_Junior")
        memory[0x30000974] = bytes(4)                 # cleared (fire, reload)
        self.assertIsNone(death_cause.attacker(read, actor))
        memory[0x20000030] = bytes(4)                 # no player
        self.assertIsNone(death_cause.player(read))


class Game:
    def __init__(self):
        self.dead = False
        self.safe = True

    def is_dead(self):
        return self.dead

    def safe_for_delivery(self):
        return self.safe


class RuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.game = Game()
        self.runtime = BotwClientRuntime(
            "localhost:1", "Player", state_path=Path(self.directory.name) / "state.json",
            log=lambda _: None,
            game_factory=lambda: self.game, tip_factory=object)
        self.runtime.state = self.runtime.state_store.select("seed", 0, 1)
        self.ap = SimpleNamespace(deathlinks=asyncio.Queue(), death_link_enabled=True,
                                  connected=True, slot_name="Player", send_death=AsyncMock())
        self.runtime.ap = self.ap
        self.requests = []
        self.result = True
        self.flag = False                 # the entry's APDeathLinkKill

        def request_death():
            self.requests.append(time.monotonic())
            if self.result is True:
                self.flag = True          # the entry marks its death...
                self.game.dead = True     # ...and the game kills Link at once
            return self.result

        self.runtime.deliveries = SimpleNamespace(backend=SimpleNamespace(
            request_death=request_death, killed_by_death_link=lambda: self.flag,
            death_cause=lambda slot: f"{slot} fell to their death"))

    async def asyncTearDown(self):
        self.directory.cleanup()

    async def tick(self, times=1):
        for _ in range(times):
            await self.runtime._deathlink_tick()

    async def receive(self, timestamp=10.0, cause="Alice fell"):
        await self.ap.deathlinks.put(DeathLinkEvent(timestamp, "Alice", cause))

    async def test_a_death_is_sent_once_on_its_edge(self):
        await self.tick()
        self.game.dead = True
        await self.tick(3)
        self.ap.send_death.assert_awaited_once_with("Player fell to their death")

    async def test_dead_at_startup_is_not_a_death(self):
        self.game.dead = True
        await self.tick(2)
        self.ap.send_death.assert_not_awaited()

    async def test_a_death_offline_is_sent_when_ap_comes_back(self):
        await self.tick()
        self.ap.connected = False
        self.game.dead = True
        await self.tick()
        self.ap.send_death.assert_not_awaited()
        self.assertEqual(self.runtime.state["pending_outgoing_death"], "Player fell to their death")
        self.ap.connected = True
        await self.tick()
        self.ap.send_death.assert_awaited_once_with("Player fell to their death")
        self.assertFalse(self.runtime.state["pending_outgoing_death"])

    async def test_a_received_death_is_announced_then_kills_without_echo(self):
        await self.tick()
        await self.receive()
        with patch.object(runtime_module, "DEATHLINK_LEAD_SECONDS", 0.0):
            await self.tick()                       # announced
            self.assertEqual(self.runtime._journal_notes,
                             [("{0}DeathLink{/}: Alice fell", None)])
            self.assertEqual(self.requests, [])
            await self.tick()                       # killed
            await self.tick(2)                      # dead: not sent back
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.runtime.state["pending_deathlinks"], [])
        self.ap.send_death.assert_not_awaited()

    async def test_the_announcement_waits_for_a_safe_moment(self):
        await self.tick()
        self.game.safe = False
        await self.receive()
        await self.tick(2)
        self.assertEqual(self.runtime._journal_notes, [])
        self.assertEqual(len(self.runtime.state["pending_deathlinks"]), 1)

    async def test_a_refused_request_keeps_the_death(self):
        self.result = False
        await self.tick()
        await self.receive()
        with patch.object(runtime_module, "DEATHLINK_LEAD_SECONDS", 0.0):
            await self.tick(2)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(len(self.runtime.state["pending_deathlinks"]), 1)

    async def test_a_pack_without_the_entry_drops_the_death(self):
        self.result = None
        await self.tick()
        await self.receive()
        with patch.object(runtime_module, "DEATHLINK_LEAD_SECONDS", 0.0):
            await self.tick(3)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.runtime.state["pending_deathlinks"], [])

    async def test_deaths_received_while_waiting_are_one_death(self):
        await self.tick()
        self.game.safe = False
        await self.receive(10.0)
        await self.receive(11.0, "Bob burned")
        await self.tick()
        self.assertEqual([e["cause"] for e in self.runtime.state["pending_deathlinks"]],
                         ["Bob burned"])

    async def test_an_old_death_is_dropped(self):
        await self.tick()
        self.runtime.state["pending_deathlinks"] = [{
            "time": 1.0, "source": "Alice", "cause": "", "received_at": time.time() - 3600}]
        await self.tick()
        self.assertEqual(self.runtime.state["pending_deathlinks"], [])
        self.assertEqual(self.requests, [])

    async def test_nothing_happens_without_death_link(self):
        self.ap.death_link_enabled = False
        await self.tick()
        await self.receive()
        self.game.dead = True
        await self.tick(2)
        self.assertEqual(self.runtime.state["pending_deathlinks"], [])
        self.ap.send_death.assert_not_awaited()

    async def kill(self):
        await self.tick()
        await self.receive()
        with patch.object(runtime_module, "DEATHLINK_LEAD_SECONDS", 0.0):
            await self.tick(2)                      # announced, killed

    async def test_the_flag_keeps_the_death_from_echoing_whatever_the_time(self):
        with patch.object(runtime_module, "DEATHLINK_ECHO_SECONDS", 0.0):
            await self.kill()
            await self.tick()                       # dead, the flag set
        self.ap.send_death.assert_not_awaited()

    async def test_a_later_natural_death_is_sent(self):
        await self.kill()
        await self.tick()                           # dead of the DeathLink
        self.game.dead, self.flag = False, False    # reloaded: the flag is gone
        await self.tick()
        self.game.dead = True                       # dies again, on its own
        await self.tick()
        self.ap.send_death.assert_awaited_once_with("Player fell to their death")

    async def test_a_flag_left_set_by_a_survival_counts_only_for_a_while(self):
        self.flag = True
        self.result = "survived"                    # Mipha saved Link, flag left set
        await self.kill()
        with patch.object(runtime_module, "DEATHLINK_FLAG_SECONDS", 0.0), \
                patch.object(runtime_module, "DEATHLINK_ECHO_SECONDS", 0.0):
            self.game.dead = True
            await self.tick()
        self.ap.send_death.assert_awaited_once()

    async def test_a_death_right_after_the_request_is_ours_whatever_the_flag(self):
        self.flag = False                           # read as unset (seen in a room)
        await self.kill()
        await self.tick()                           # dead in the same seconds
        self.ap.send_death.assert_not_awaited()

    async def test_a_pack_without_the_flag_falls_back_on_the_time(self):
        self.runtime.deliveries.backend.killed_by_death_link = lambda: None
        await self.kill()
        await self.tick()                           # within 5 s: not sent back
        self.ap.send_death.assert_not_awaited()
        self.game.dead = False
        await self.tick()
        with patch.object(runtime_module, "DEATHLINK_ECHO_SECONDS", 0.0):
            self.game.dead = True
            await self.tick()
        self.ap.send_death.assert_awaited_once()

if __name__ == "__main__":
    unittest.main()
