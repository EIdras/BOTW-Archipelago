import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import zlib

from botw_client.backend import (
    BackendContractError,
    DeliveryCheckpoint,
    DeliveryCommand,
    DeliveryCoordinator,
    DeliveryResult,
    DeliveryStatus,
)
from botw_client.runtime import BotwClientRuntime, FatalClientError
from botw_client.native_delivery import (
    CemuNativeDeliveryBackend,
    NativeDeliveryCatalog,
)


def flag(name):
    return zlib.crc32(name.encode()) & 0xFFFFFFFF


class FakeLive:
    def __init__(self, values):
        self.values = values

    def get(self, hash_u32, kind):
        assert kind in ("s32", "bool")
        return self.values.get(hash_u32)


class NativeDeliveryBackendTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "catalog.json"
        self.path.write_text(json.dumps({
            "schema": 1,
            "cursor": "(received_index << 8) | step",
            "flow": "Demo007_1",
            "reject_counter": "APDeliveryRejectCounter",
            "unsupported": {"Manual": "manual"},
            "items": {
                "Core": {"variants": {"default": [{
                    "step": 0, "step_count": 1, "cursor_delta": 256,
                    "entry": "APD_CORE_00", "capacity_actor": "CoreActor",
                    "mutations": [{"kind": "grant_actor"}],
                }]}},
                "Progressive": {"variants": {
                    "0": [{"step": 0, "step_count": 1, "cursor_delta": 256,
                           "entry": "APD_TIER0", "capacity_actor": "Tier0",
                           "mutations": [{"kind": "grant_actor"}]}],
                    "1": [{"step": 0, "step_count": 1, "cursor_delta": 256,
                           "entry": "APD_TIER1", "capacity_actor": "Tier1",
                           "mutations": [{"kind": "grant_actor"}]}],
                }},
                "Set": {"variants": {"default": [
                    {"step": 0, "step_count": 2, "cursor_delta": 1,
                     "entry": "APD_SET_00", "capacity_actor": "Head",
                     "mutations": [{"kind": "grant_actor"}]},
                    {"step": 1, "step_count": 2, "cursor_delta": 255,
                     "entry": "APD_SET_01", "capacity_actor": "Body",
                     "mutations": [{"kind": "grant_actor"}]},
                ]}},
            },
        }), encoding="utf-8")
        self.values = {
            flag("APSeedToken"): 123,
            flag("APReceivedCursor"): 7 << 8,
            flag("APDeliveryRejectCounter"): 4,
            flag("SaveProhibition"): False,
        }
        self.game = SimpleNamespace(
            live=FakeLive(self.values), process=SimpleNamespace(pid=42),
            cave=object(), delivery_block_reason="busy")

    def backend(self, request, **kwargs):
        return CemuNativeDeliveryBackend(
            self.game, "seed", 2, 123, catalog=self.path, request=request,
            lock_factory=lambda _pid: _NullLock(), safe=lambda: True,
            commit_timeout=0.01, poll_seconds=0, **{"in_world": lambda: True, **kwargs})

    def add_binding(self, token=123):
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["binding"] = {
            "entry": "APBindSession", "seed_token": token,
            "requires_cursor": 0, "requires_token": 0,
        }
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_catalog_selects_progressive_tier_and_validates_substeps(self):
        catalog = NativeDeliveryCatalog(self.path)
        command = DeliveryCommand("seed", 2, 7, "Progressive", received_before=9)
        self.assertEqual(catalog.resolve(command)[1]["entry"], "APD_TIER1")
        command = DeliveryCommand("seed", 2, 7, "Set", step=1, step_count=2)
        self.assertEqual(catalog.resolve(command)[1]["cursor_delta"], 255)
        with self.assertRaisesRegex(KeyError, "manual"):
            catalog.steps("Manual")

    def test_acceptance_is_applied_only_after_exact_cursor_commit(self):
        def request(_process, _cave, _number, checkpoint, **kwargs):
            self.assertEqual(kwargs, dict(custom_text=False, flow="Demo007_1",
                                          entry="APD_CORE_00"))
            checkpoint({"status": "prepared"})
            self.values[flag("APReceivedCursor")] = 8 << 8
            return {"native_return": 1}

        command = DeliveryCommand("seed", 2, 7, "Core")
        result = DeliveryCoordinator(self.backend(request)).deliver(command)
        self.assertEqual((result.status, result.cursor),
                         (DeliveryStatus.APPLIED, 8 << 8))

    def test_next_request_waits_for_the_committed_event_to_close(self):
        # A step requested one frame after the previous commit was accepted
        # and never ran. The next request waits SETTLE_FRAMES game frames.
        from botw_client.native_delivery import SETTLE_FRAMES
        frame = [1000]
        self.game.frame_tick = lambda: frame[0]
        calls = []

        def request(_process, _cave, _number, checkpoint, **kwargs):
            calls.append(kwargs["entry"])
            checkpoint({"status": "prepared"})
            self.values[flag("APReceivedCursor")] += 1 if kwargs["entry"] == "APD_SET_00" else 255
            return {"native_return": 1}

        backend = self.backend(request)
        first = backend.deliver(DeliveryCommand("seed", 2, 7, "Set", step=0, step_count=2))
        self.assertEqual(first.status, DeliveryStatus.APPLIED)
        second = DeliveryCommand("seed", 2, 7, "Set", step=1, step_count=2)
        frame[0] += SETTLE_FRAMES - 1
        result = backend.deliver(second)
        self.assertEqual(result.status, DeliveryStatus.DEFERRED)
        self.assertIn("closing", result.detail)
        self.assertEqual(calls, ["APD_SET_00"])
        frame[0] += 1
        self.assertEqual(backend.deliver(second).status, DeliveryStatus.APPLIED)
        self.assertEqual(calls, ["APD_SET_00", "APD_SET_01"])

    def test_a_silent_twin_is_asked_in_its_own_flowchart(self):
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["items"]["Core"]["variants"]["default"][0].update(
            quiet_entry="APD_CORE_00Q", quiet_flow="OperationGuide")
        self.path.write_text(json.dumps(data), encoding="utf-8")
        calls = []

        def request(_process, _cave, _number, checkpoint, **kwargs):
            calls.append((kwargs["flow"], kwargs["entry"]))
            checkpoint({"status": "prepared"})
            self.values[flag("APReceivedCursor")] += 256
            return {"native_return": 1}

        backend = self.backend(request)
        backend.deliver(DeliveryCommand("seed", 2, 7, "Core", quiet=True))
        self.values[flag("APReceivedCursor")] = 7 << 8
        backend._committed_at = None
        backend.deliver(DeliveryCommand("seed", 2, 7, "Core"))
        self.assertEqual(calls, [("OperationGuide", "APD_CORE_00Q"),
                                 ("Demo007_1", "APD_CORE_00")])

    def test_a_filler_received_again_takes_its_silent_twin(self):
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["items"]["Core"]["variants"]["default"][0].update(
            quiet_entry="APD_CORE_00Q", quiet_flow="OperationGuide")
        self.path.write_text(json.dumps(data), encoding="utf-8")
        calls = []

        def request(_process, _cave, _number, checkpoint, **kwargs):
            calls.append((kwargs["flow"], kwargs["entry"]))
            checkpoint({"status": "prepared"})
            self.values[flag("APReceivedCursor")] += 256
            return {"native_return": 1}

        backend = self.backend(request)
        self.assertEqual(backend.deliver(DeliveryCommand("seed", 2, 7, "Core", pickup=True)).status,
                         DeliveryStatus.APPLIED)
        self.assertEqual(calls, [("OperationGuide", "APD_CORE_00Q")])

    def test_the_pickup_notification_is_asked_once_link_plays_again(self):
        # 04/10: from our entry, Demo_OpenPickup showed nothing; the game's
        # function, from the invoker with Link in the world, shows it.
        from botw_client.native_delivery import PICKUP_SETTLE_FRAMES, SAFESTRING_VTABLE, SHOW_PICKUP
        memory = {}

        class Cave:
            name_buf, call_n, call_ret = 0x1000, 0x2000, 0x2004

            def guest(self, host):
                return host + 0x10000000

            def call_pf(self, address, *args):
                memory["call"] = (address, args)
                memory[0x2000] = (1).to_bytes(4, "big")
                memory[0x2004] = (1).to_bytes(4, "big")

        class Process:
            pid = 42

            def write(self, address, data):
                memory[address] = data
                return True

            def read(self, address, size):
                return memory.get(address, bytes(size))

        self.game.process, self.game.cave = Process(), Cave()
        frame, playing = [100], [False]
        self.game.frame_tick = lambda: frame[0]
        backend = self.backend(None, in_world=lambda: playing[0])
        backend._committed_at = 100
        self.assertIs(backend.show_pickup("Item_Ore_J"), False)    # a menu, the entry closing
        playing[0], frame[0] = True, 100 + PICKUP_SETTLE_FRAMES
        self.assertIs(backend.show_pickup("Item_Ore_J"), True)
        name = 0x10001000
        self.assertEqual(memory["call"], (SHOW_PICKUP, (name + 0x38,)))
        self.assertEqual(memory[0x1000][:11], b"Item_Ore_J\0")
        self.assertEqual(memory[0x1000][0x38:], name.to_bytes(4, "big") + SAFESTRING_VTABLE.to_bytes(4, "big"))

    def test_rune_download_waits_for_a_pause_menu_built_at_once(self):
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["items"]["Core"]["variants"]["default"][0].update(
            capacity_actor=None, quiet_entry="APD_CORE_00Q", quiet_flow="OperationGuide",
            mutations=[{"kind": "rune_download"}, {"kind": "set_s32"}])
        self.path.write_text(json.dumps(data), encoding="utf-8")
        calls, ready = [], [(False, "map not loaded yet")]
        self.game.pause_menu_ready = lambda: ready[0]

        def request(_process, _cave, _number, checkpoint, **kwargs):
            calls.append(kwargs["entry"])
            checkpoint({"status": "prepared"})
            self.values[flag("APReceivedCursor")] += 256
            return {"native_return": 1}

        backend = self.backend(request)
        result = backend.deliver(DeliveryCommand("seed", 2, 7, "Core"))
        self.assertEqual(result.status, DeliveryStatus.DEFERRED)
        self.assertIn("map not loaded yet", result.detail)
        self.assertEqual(calls, [])
        # Given back after a reload: no download screen, no wait.
        self.assertEqual(backend.deliver(DeliveryCommand("seed", 2, 7, "Core", quiet=True)).status,
                         DeliveryStatus.APPLIED)
        self.values[flag("APReceivedCursor")] = 7 << 8
        backend._committed_at = None
        ready[0] = (True, "")
        self.assertEqual(backend.deliver(DeliveryCommand("seed", 2, 7, "Core")).status,
                         DeliveryStatus.APPLIED)
        self.assertEqual(calls, ["APD_CORE_00Q", "APD_CORE_00"])

    def test_status_item_is_asked_by_its_entry_without_cursor(self):
        data = json.loads(self.path.read_text(encoding="utf-8"))
        data["status_item"] = {"entry": "APStatusItem", "actor": "Obj_AP_Status"}
        self.path.write_text(json.dumps(data), encoding="utf-8")
        answers, calls = [0, 1], []

        def request(_process, _cave, _number, _checkpoint, **kwargs):
            calls.append(kwargs["entry"])
            return {"native_return": answers.pop(0)}

        backend = self.backend(request)
        cursor = self.values[flag("APReceivedCursor")]
        self.assertFalse(backend.request_status_item())      # refused: asked again
        self.assertTrue(backend.request_status_item())
        self.assertEqual(calls, ["APStatusItem", "APStatusItem"])
        self.assertEqual(self.values[flag("APReceivedCursor")], cursor)
        self.values[flag("APSeedToken")] = 999               # another save: not asked
        self.assertFalse(backend.request_status_item())
        self.assertEqual(len(calls), 2)

    def test_a_pack_without_status_item_asks_nothing(self):
        backend = self.backend(lambda *_a, **_k: self.fail("no request"))
        self.assertIsNone(backend.request_status_item())

    def test_capacity_rejection_keeps_cursor_and_reports_full(self):
        def request(*_args, **_kwargs):
            self.values[flag("APDeliveryRejectCounter")] += 1
            return {"native_return": 1}

        result = DeliveryCoordinator(self.backend(request)).deliver(
            DeliveryCommand("seed", 2, 7, "Core"))
        self.assertEqual(result.status, DeliveryStatus.INVENTORY_FULL)
        self.assertEqual(result.cursor, 7 << 8)

    def test_not_ready_and_explicit_refusal_are_safe_to_retry(self):
        calls = []
        backend = self.backend(lambda *_args, **_kwargs: calls.append(1))
        backend._safe = lambda: False
        command = DeliveryCommand("seed", 2, 7, "Core")
        self.assertEqual(DeliveryCoordinator(backend).deliver(command).status,
                         DeliveryStatus.DEFERRED)
        self.assertFalse(calls)

        backend = self.backend(lambda *_args, **_kwargs: {"native_return": 0})
        self.assertEqual(DeliveryCoordinator(backend).deliver(command).status,
                         DeliveryStatus.DEFERRED)

    def test_accepted_timeout_is_quarantined_without_second_call(self):
        calls = []
        def request(*_args, **_kwargs):
            calls.append(1)
            return {"native_return": 1}
        result = DeliveryCoordinator(self.backend(request)).deliver(
            DeliveryCommand("seed", 2, 7, "Core"))
        self.assertEqual(result.status, DeliveryStatus.UNCERTAIN)
        self.assertEqual(calls, [1])

    def test_a_window_left_open_or_a_running_entry_is_waited_for(self):
        # 04/10: a rupee's get window, closed late, ended the client after 30 s.
        # The wait counts only time with Link playing and no entry running.
        import time
        for busy in ("window", "guard"):
            with self.subTest(busy=busy):
                self.values[flag("APReceivedCursor")] = 7 << 8
                opened = []

                def closed():
                    """The player closes the window 0.2 s after the request (4 timeouts)."""
                    if opened and time.monotonic() - opened[0] > 0.2:
                        self.values[flag("APReceivedCursor")] = 8 << 8
                        self.values[flag("SaveProhibition")] = False
                        return True
                    return False

                def request(*_args, **_kwargs):
                    opened.append(time.monotonic())
                    self.values[flag("SaveProhibition")] = busy == "guard"
                    return {"native_return": 1}
                backend = self.backend(request, in_world=lambda: busy != "window" or closed())
                guard = backend._guard
                backend._guard = lambda: closed() and False or guard()
                backend.commit_timeout, backend.poll_seconds = 0.05, 0.005
                result = backend.deliver(DeliveryCommand("seed", 2, 7, "Core"))
                self.assertEqual(result.status, DeliveryStatus.APPLIED)
        self.values[flag("SaveProhibition")] = False

    def test_foreign_or_zero_token_never_submits(self):
        calls = []
        backend = self.backend(lambda *_args, **_kwargs: calls.append(1))
        for token in (0, 999):
            self.values[flag("APSeedToken")] = token
            result = DeliveryCoordinator(backend).deliver(
                DeliveryCommand("seed", 2, 7, "Core"))
            self.assertEqual(result.status, DeliveryStatus.SESSION_MISMATCH)
        self.assertFalse(calls)

    def test_binding_commits_zero_ledger_through_native_entry(self):
        self.add_binding()
        self.values[flag("APSeedToken")] = 0
        self.values[flag("APReceivedCursor")] = 0

        def request(_process, _cave, number, checkpoint, **kwargs):
            self.assertEqual(number, 0)
            self.assertEqual(kwargs, dict(
                custom_text=False, flow="Demo007_1", entry="APBindSession"))
            checkpoint({"status": "prepared"})
            self.values[flag("APSeedToken")] = 123
            return {"native_return": 1}

        result = self.backend(request).bind_session()
        self.assertEqual((result.status, result.cursor),
                         (DeliveryStatus.APPLIED, 0))

    def test_binding_refuses_foreign_or_nonempty_ledger_without_request(self):
        self.add_binding()
        calls = []
        for token, cursor in ((999, 0), (0, 1)):
            self.values[flag("APSeedToken")] = token
            self.values[flag("APReceivedCursor")] = cursor
            result = self.backend(lambda *_args, **_kwargs: calls.append(1)).bind_session()
            self.assertEqual(result.status, DeliveryStatus.SESSION_MISMATCH)
        self.assertFalse(calls)

    def test_binding_requires_matching_catalog_and_readiness(self):
        self.values[flag("APSeedToken")] = 0
        self.values[flag("APReceivedCursor")] = 0
        self.assertEqual(self.backend(lambda: None).bind_session().status,
                         DeliveryStatus.SESSION_MISMATCH)
        self.add_binding()
        backend = self.backend(lambda: None)
        backend._safe = lambda: False
        self.assertEqual(backend.bind_session().status, DeliveryStatus.DEFERRED)

    def test_the_title_screen_defers_the_binding_without_a_request(self):
        # Measured: on the title screen the delivery gate passes, and the binding
        # entry is accepted but never runs (no commit in 30 s, client stopped).
        self.add_binding()
        self.values[flag("APSeedToken")] = 0
        self.values[flag("APReceivedCursor")] = 0
        calls = []
        for in_world in (lambda: False, lambda: 1 / 0):
            result = self.backend(lambda *_args, **_kwargs: calls.append(1), in_world=in_world).bind_session()
            self.assertEqual((result.status, result.detail),
                             (DeliveryStatus.DEFERRED, "waiting for Link in the world"))
        self.assertFalse(calls)

    def test_foreign_catalog_blocks_even_an_already_bound_save(self):
        self.add_binding(token=999)
        calls = []
        backend = self.backend(lambda *_args, **_kwargs: calls.append(1))
        self.assertNotEqual((backend.checkpoint().seed, backend.checkpoint().slot),
                            ("seed", 2))
        self.assertEqual(backend.bind_session().status,
                         DeliveryStatus.SESSION_MISMATCH)
        self.assertEqual(DeliveryCoordinator(backend).deliver(
            DeliveryCommand("seed", 2, 7, "Core")).status,
            DeliveryStatus.SESSION_MISMATCH)
        self.assertFalse(calls)

    def test_binding_exception_after_prepare_is_quarantined_without_retry(self):
        self.add_binding()
        self.values[flag("APSeedToken")] = 0
        self.values[flag("APReceivedCursor")] = 0
        calls = []

        def request(_process, _cave, _number, checkpoint, **_kwargs):
            calls.append(1)
            checkpoint({"status": "prepared"})
            raise RuntimeError("lost acknowledgement")

        result = self.backend(request).bind_session()
        self.assertEqual(result.status, DeliveryStatus.UNCERTAIN)
        self.assertEqual(calls, [1])

    def test_impossible_native_cursor_is_a_contract_error(self):
        def request(*_args, **_kwargs):
            self.values[flag("APReceivedCursor")] += 2
            return {"native_return": 1}
        with self.assertRaises(BackendContractError):
            DeliveryCoordinator(self.backend(request)).deliver(
                DeliveryCommand("seed", 2, 7, "Set", step_count=2))


class _NullLock:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _RuntimeCatalog:
    def steps(self, name, received_before=0):
        if name == "Set":
            return [dict(step=0), dict(step=1)]
        return [dict(step=0, tier=received_before)]


class _RuntimeBackend:
    def __init__(self, cursor=(1 << 8) | 1):
        self.current = DeliveryCheckpoint("seed", 1, cursor)
        self.catalog = _RuntimeCatalog()
        self.commands = []

    def checkpoint(self):
        return self.current

    def checked_locations(self):
        return set()

    def deliver(self, command):
        self.commands.append(command)
        self.current = DeliveryCheckpoint("seed", 1, command.next_cursor)
        return SimpleNamespace(status=DeliveryStatus.APPLIED,
                               cursor=command.next_cursor, detail="")


class _BindingRuntimeBackend(_RuntimeBackend):
    def __init__(self, result):
        super().__init__(0)
        self.current = DeliveryCheckpoint("token:0", -1, 0)
        self.result = result
        self.bind_calls = 0

    def bind_session(self):
        self.bind_calls += 1
        if self.result.status in (DeliveryStatus.APPLIED,
                                  DeliveryStatus.ALREADY_APPLIED):
            self.current = DeliveryCheckpoint("seed", 1, self.result.cursor)
        return self.result


class NativeDeliveryRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.game = SimpleNamespace(
            delivery_block_reason="", safe_for_delivery=lambda: True)
        self.runtime = BotwClientRuntime(
            "unused:1", "test", state_path=Path(self.temporary.name) / "state.json",
            game_factory=lambda: self.game, native_delivery=True, log=lambda _line: None)
        self.runtime._session_identity = ("seed", 0, 1, "checksum")
        self.runtime.state = self.runtime.state_store.select(
            *self.runtime._session_identity)
        self.runtime.ap = SimpleNamespace(
            items_synchronized=True,
            received_items={
                0: SimpleNamespace(item=10),
                1: SimpleNamespace(item=11),
            },
            item_name=lambda item: "Set" if item.item == 11 else "Core",
        )
        self.backend = _RuntimeBackend()
        self.runtime.deliveries = DeliveryCoordinator(self.backend)

    async def test_saved_cursor_drives_projection_and_next_substep(self):
        self.runtime._discover_received()
        self.assertEqual(self.runtime.state["applied"], [0])
        self.assertEqual(self.runtime.state["apply_queue"], [1])
        self.assertEqual(self.runtime.state["steps"], {"1": 1})

        await self.runtime._apply_one_received_native()
        self.assertEqual(len(self.backend.commands), 1)
        command = self.backend.commands[0]
        self.assertEqual((command.index, command.step, command.step_count),
                         (1, 1, 2))
        self.assertEqual(self.runtime.state["applied"], [0, 1])
        self.assertEqual(self.runtime.state["apply_queue"], [])
        self.assertEqual(self.runtime.state["steps"], {})

    async def test_a_state_from_before_tracking_still_gives_back_silently(self):
        # A state saved before delivered_high existed, then the oldest
        # save loaded: its applied list is the last cursor it saw.
        self.runtime.state["applied"] = [0, 1]
        self.runtime.state.pop("delivered_high", None)
        self.backend.current = DeliveryCheckpoint("seed", 1, 0)
        self.runtime._discover_received()
        self.assertEqual(self.runtime.state["delivered_high"], 2)
        self.assertEqual(self.runtime.state["apply_queue"], [0, 1])

        await self.runtime._apply_one_received_native()
        self.assertTrue(self.backend.commands[0].quiet)

    async def test_joined_delivery_waits_for_its_native_presentation(self):
        self.runtime.native_presentations = True
        self.runtime._discover_received()

        await self.runtime._apply_one_received_native()
        self.assertFalse(self.backend.commands)

        self.runtime.state["presentation_completed"].append(1)
        await self.runtime._apply_one_received_native()
        self.assertEqual(len(self.backend.commands), 1)
        self.assertEqual(self.backend.commands[0].index, 1)

    async def recover_announcement(self, cursor, expected_steps):
        from botw_client.presentation_session import NativePresentationSession
        runtime = self.runtime
        runtime.native_presentations = True
        runtime.state['shown'] = [0]
        self.backend.current = DeliveryCheckpoint('seed', 1, cursor)
        self.game.item_map = {}
        runtime.ap.slot = 1
        runtime.ap.scouted_locations = {}
        runtime.ap.sender = lambda item: ('Other player', 'BOTW')
        runtime.ap.location_name = lambda location: str(location)
        for index, item in runtime.ap.received_items.items():
            item.player, item.location = 2, 200 + index
        runtime._discover_received()
        presentation = Mock()
        presentation.ready.return_value = True
        presentation.recovery_incarnation.return_value = 'old-cemu'
        presentation.submit.return_value = dict(status='accepted',session='old',generation=1)

        def open_session():
            session = NativePresentationSession(runtime.state_store.path,
                runtime._session_identity, self.game, backend=presentation)
            self.addCleanup(session.close)
            return session

        def advance(session):
            return session.advance(runtime.state, runtime.ap, self.game)

        session = open_session()
        self.assertEqual(advance(session)[0], 'accepted')
        session.close()  # Crash while the announcement was in flight.
        session = open_session()
        await runtime._apply_one_received_native()
        self.assertEqual(self.backend.commands, [])
        session.request_replay('received/1')
        self.assertEqual(advance(session)[0], 'uncertain')
        session.close()
        presentation.recovery_incarnation.return_value = 'new-cemu'
        presentation.submit.return_value = dict(status='accepted',session='new',generation=1)
        presentation.poll.return_value = dict(status='finished',session='new',generation=1)
        session = open_session()
        self.assertEqual(advance(session)[0], 'accepted')
        await runtime._apply_one_received_native()
        self.assertEqual(self.backend.commands, [])
        self.assertEqual(advance(session)[0], 'completed')
        await runtime._apply_one_received_native()
        self.assertEqual([c.step for c in self.backend.commands], expected_steps)
        self.assertTrue(all(c.index == 1 for c in self.backend.commands))
        # Lost client projection after a committed native grant is recovered
        # from the journal + save cursor, not by issuing another grant.
        session.close()
        runtime.state['presentation_completed'] = []
        runtime.state['apply_queue'] = [1]
        runtime._discover_received()
        session = open_session()
        advance(session)
        await runtime._apply_one_received_native()
        self.assertEqual([c.step for c in self.backend.commands], expected_steps)
        self.assertEqual(presentation.submit.call_count, 2)

    async def test_replayed_announcement_resumes_only_uncommitted_delivery_step(self):
        await self.recover_announcement((1 << 8) | 1, [1])

    async def test_replayed_announcement_never_regrants_item_past_saved_cursor(self):
        await self.recover_announcement(2 << 8, [])

    async def test_foreign_checkpoint_stops_before_queue_or_delivery(self):
        self.backend.current = DeliveryCheckpoint("other", 1, 0)
        with self.assertRaisesRegex(FatalClientError, "not bound"):
            self.runtime._discover_received()
        self.assertFalse(self.backend.commands)

    async def test_native_session_binding_gates_runtime_until_commit(self):
        backend = _BindingRuntimeBackend(
            DeliveryResult(DeliveryStatus.APPLIED, 0))
        self.runtime.deliveries = DeliveryCoordinator(backend)
        self.runtime._native_session_bound = False
        self.runtime.game.delivery_block_reason = 'native binding explicitly refused'
        self.assertTrue(await self.runtime._ensure_native_session())
        self.assertNotIn('refusee', self.runtime.game.delivery_block_reason)
        self.assertTrue(self.runtime._native_session_bound)
        self.assertEqual(backend.bind_calls, 1)
        self.assertTrue(await self.runtime._ensure_native_session())
        self.assertEqual(backend.bind_calls, 1)

    async def test_native_session_mismatch_stops_runtime(self):
        backend = _BindingRuntimeBackend(DeliveryResult(
            DeliveryStatus.SESSION_MISMATCH, 0, "foreign"))
        self.runtime.deliveries = DeliveryCoordinator(backend)
        self.runtime._native_session_bound = False
        with self.assertRaisesRegex(FatalClientError, "native binding refused"):
            await self.runtime._ensure_native_session()


if __name__ == "__main__":
    unittest.main()
