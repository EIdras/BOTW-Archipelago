import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import zlib

from botw_client.backend import DeliveryCommand, DeliveryStatus
from botw_client.native_delivery import CemuNativeDeliveryBackend
from botw_client.rune_selection import (
    FIELDS, SELECTION_GLOBAL, RuneSelectionSync, SyncOutcome,
    equip_requirement, read_state)
from tools.build_rune_selection_sync import (
    BRANCH_ANCHOR, DATA_ANCHOR, SERVICE_ANCHOR, patch_injection)

ROOT = Path(__file__).resolve().parents[1]
OBJECT = 0x43013700


class FakeGame:
    """Guest memory holding the selection object, plus the game's behaviour.

    ``request`` records the native call; reading the object applies a pending
    request the way 0x02A2DAC8 does (0x1D4 <- 0x1D0) once ``apply_after``
    reads have passed.
    """

    def __init__(self, equip=2, current=-1, requested=None, pointer=OBJECT,
                 answer=True, apply_after=2):
        self.equip = equip
        self.pointer = pointer
        self.words = {"requested": current if requested is None else requested,
                      "current": current, "previous": -1,
                      "flags_4c": 0, "flags_50": 0}
        self.answer = answer
        self.apply_after = apply_after
        self.requests = []
        self.reads = 0

    def read_u32(self, address):
        if address == SELECTION_GLOBAL:
            self.reads += 1
            if (self.words["requested"] != self.words["current"]
                    and self.reads > self.apply_after):
                self.words["previous"] = self.words["current"]
                self.words["current"] = self.words["requested"]
            return self.pointer
        for name, offset in FIELDS.items():
            if address == self.pointer + offset:
                return self.words[name] & 0xFFFFFFFF
        raise AssertionError(f"unexpected read {address:#x}")

    def request(self, rune_type):
        self.requests.append(rune_type)
        if self.answer is not False:  # None: the cave runs it after the delay
            self.words["requested"] = rune_type
        return self.answer

    def sync(self, **kwargs):
        clock = iter(i * 0.1 for i in range(10_000))
        return RuneSelectionSync(self.read_u32, lambda: self.equip, self.request,
                                 clock=lambda: next(clock), sleep=lambda _s: None,
                                 **kwargs)


class EquipRequirementTests(unittest.TestCase):
    def test_reads_the_rune_from_the_catalog_setter(self):
        step = {"mutations": [
            {"kind": "set_bool", "target": "IsGet_Obj_Magnetglove", "value": True},
            {"kind": "set_s32", "target": "PlayerEquipItemType", "value": 2}]}
        self.assertEqual(equip_requirement(step), 2)

    def test_steps_without_equip_setter_need_nothing(self):
        self.assertIsNone(equip_requirement({"mutations": [{"kind": "grant_actor"}]}))

    def test_rejects_values_that_are_not_delivered_runes(self):
        for values in ([7], [2, 3]):
            step = {"mutations": [{"kind": "set_s32", "target": "PlayerEquipItemType",
                                   "value": value} for value in values]}
            with self.assertRaises(ValueError):
                equip_requirement(step)


class ReadStateTests(unittest.TestCase):
    def test_absent_object_is_not_read(self):
        self.assertIsNone(read_state(FakeGame(pointer=0).read_u32))

    def test_values_the_game_never_stores_are_rejected(self):
        game = FakeGame(current=0x1234)
        self.assertIsNone(read_state(game.read_u32))

    def test_reads_signed_fields(self):
        state = read_state(FakeGame(current=-1).read_u32)
        self.assertEqual((state.requested, state.current, state.previous), (-1, -1, -1))


class ReconcileTests(unittest.TestCase):
    def test_first_rune_is_requested_then_applied_by_the_game(self):
        game = FakeGame(equip=2, current=-1)
        outcome = game.sync().reconcile(2)
        self.assertEqual(outcome.status, "synced")
        self.assertEqual(game.requests, [2])
        self.assertEqual(outcome.after.current, 2)
        self.assertTrue(outcome.ok)

    def test_the_master_cycle_is_selected_only_when_no_rune_is_in_hand(self):
        # Owned, nothing selected: no module to use until it is (measured, 07/10).
        game = FakeGame(equip=-1, current=-1)
        outcome = game.sync().select_if_none(6)
        self.assertEqual((outcome.status, game.requests, outcome.after.current), ("synced", [6], 6))
        # A rune in hand stays there.
        game = FakeGame(equip=2, current=2)
        outcome = game.sync().select_if_none(6)
        self.assertEqual((outcome.status, game.requests), ("kept", []))
        self.assertTrue(outcome.ok)

    def test_object_already_on_the_rune_is_left_alone(self):
        game = FakeGame(equip=3, current=3)
        self.assertEqual(game.sync().reconcile(3).status, "in_sync")
        self.assertEqual(game.requests, [])

    def test_pending_request_is_not_issued_twice(self):
        game = FakeGame(equip=2, current=-1, requested=2)  # inventory already asked
        outcome = game.sync().reconcile(2)
        self.assertEqual(outcome.status, "synced")
        self.assertEqual(game.requests, [])

    def test_later_player_choice_is_never_overwritten(self):
        game = FakeGame(equip=3, current=3)
        outcome = game.sync().reconcile(2)
        self.assertEqual(outcome.status, "mismatch")
        self.assertEqual(game.requests, [])

    def test_no_rune_and_absent_object_request_nothing(self):
        for game, status in ((FakeGame(equip=-1), "no_rune"),
                             (FakeGame(pointer=0), "unavailable")):
            self.assertEqual(game.sync().reconcile().status, status)
            self.assertEqual(game.requests, [])

    def test_refused_request_is_reported(self):
        game = FakeGame(answer=False)
        outcome = game.sync().reconcile(2)
        self.assertEqual(outcome.status, "refused")
        self.assertFalse(outcome.ok)

    def test_unanswered_request_still_waits_for_the_game(self):
        game = FakeGame(answer=None)
        outcome = game.sync().reconcile(2)
        self.assertEqual(outcome.status, "synced")
        self.assertEqual(game.requests, [2])

    def test_request_not_applied_in_time_stays_pending(self):
        game = FakeGame(apply_after=10**9)
        outcome = game.sync(apply_timeout=0.5).reconcile(2)
        self.assertEqual(outcome.status, "pending")
        self.assertFalse(outcome.ok)
        self.assertIn("waiting", outcome.summary())


class DeliveryIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.catalog = Path(temporary.name) / "catalog.json"
        setter = {"kind": "set_s32", "target": "PlayerEquipItemType", "value": 2}
        self.catalog.write_text(json.dumps({
            "schema": 1, "cursor": "(received_index << 8) | step", "flow": "Demo007_1",
            "items": {
                "Magnesis": {"variants": {"default": [{
                    "step": 0, "step_count": 1, "cursor_delta": 256, "entry": "APD_MAG",
                    "capacity_actor": None, "mutations": [
                        {"kind": "set_bool", "target": "IsGet_Obj_Magnetglove",
                         "value": True}, setter]}]}},
                "Broken": {"variants": {"default": [{
                    "step": 0, "step_count": 1, "cursor_delta": 256, "entry": "APD_BAD",
                    "capacity_actor": None, "mutations": [{**setter, "value": 9}]}]}},
                "Rupee": {"variants": {"default": [{
                    "step": 0, "step_count": 1, "cursor_delta": 256, "entry": "APD_RUP",
                    "capacity_actor": None, "mutations": [{"kind": "grant_actor"}]}]}},
            }}), encoding="utf-8")
        self.values = {self.flag("APSeedToken"): 123, self.flag("APReceivedCursor"): 256,
                       self.flag("APDeliveryRejectCounter"): 0}
        self.synced = []
        live = SimpleNamespace(get=lambda hash_u32, kind: self.values.get(hash_u32))

        def sync(expected):
            self.synced.append(expected)
            return SyncOutcome("synced", expected)
        self.game = SimpleNamespace(live=live, process=SimpleNamespace(pid=1),
                                    cave=object(), sync_rune_selection=sync)

    @staticmethod
    def flag(name):
        return zlib.crc32(name.encode()) & 0xFFFFFFFF

    def deliver(self, name, game=None):
        calls = []

        def request(*args, **kwargs):
            calls.append(kwargs["entry"])
            self.values[self.flag("APReceivedCursor")] = 512
            return {"native_return": 1}
        backend = CemuNativeDeliveryBackend(
            game or self.game, "seed", 2, 123, catalog=self.catalog, request=request,
            lock_factory=None, safe=lambda: True, commit_timeout=0.1, poll_seconds=0)
        return backend.deliver(DeliveryCommand("seed", 2, 1, name, 0, 1, 0)), calls

    def test_committed_rune_is_synced_and_stays_applied(self):
        result, calls = self.deliver("Magnesis")
        self.assertEqual(result.status, DeliveryStatus.APPLIED)
        self.assertEqual(calls, ["APD_MAG"])
        self.assertEqual(self.synced, [2])
        self.assertIn("synced", result.detail)

    def test_other_items_do_not_touch_the_selection(self):
        result, _ = self.deliver("Rupee")
        self.assertEqual(result.status, DeliveryStatus.APPLIED)
        self.assertEqual(self.synced, [])

    def test_malformed_setter_fails_before_any_native_call(self):
        with self.assertRaises(ValueError):
            self.deliver("Broken")
        self.assertEqual(self.values[self.flag("APReceivedCursor")], 256)

    def test_failing_sync_never_turns_a_commit_into_an_error(self):
        def broken(_expected):
            raise TypeError("lecture impossible")
        self.game.sync_rune_selection = broken
        result, _ = self.deliver("Magnesis")
        self.assertEqual(result.status, DeliveryStatus.APPLIED)
        self.assertIn("TypeError", result.detail)

    def test_game_without_the_capability_is_reported_not_fatal(self):
        game = SimpleNamespace(**{k: v for k, v in vars(self.game).items()
                                  if k != "sync_rune_selection"})
        result, _ = self.deliver("Magnesis", game)
        self.assertEqual(result.status, DeliveryStatus.APPLIED)
        self.assertIn("not synchronized", result.detail)


class InjectionTransformTests(unittest.TestCase):
    PARENT = (DATA_ANCHOR + "apProbe:\napCheckRune:\n" + BRANCH_ANCHOR
              + "    nop\n" + SERVICE_ANCHOR + "    nop\n")

    def test_transform_adds_fields_branch_and_service_once(self):
        patched = patch_injection(self.PARENT)
        self.assertEqual(patched.count("apCheckSel:"), 1)
        self.assertIn("beq   apCheckSel", patched)
        self.assertLess(patched.index("apSelResult:"), patched.index("apProbe:"))
        self.assertLess(patched.index("apCheckSel:"), patched.index("\napCheckNotify:"))
        self.assertIn("ori   r12, r12, 0xd6d4", patched)

    def test_transform_refuses_missing_or_repeated_anchors(self):
        with self.assertRaises(ValueError):
            patch_injection(self.PARENT.replace("beq   apCheckNotify", "beq   elsewhere"))
        with self.assertRaises(ValueError):
            patch_injection(patch_injection(self.PARENT))


if __name__ == "__main__":
    unittest.main()
