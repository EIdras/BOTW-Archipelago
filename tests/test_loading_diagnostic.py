from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from tools.cemu import loading_diagnostic as loading
from tools.cemu import presentation_ready


class LoadingDiagnosticTests(unittest.TestCase):
    def test_presentation_diagnostic_names_screen_and_protection_blocks(self):
        flags = {
            "APReceivedCursor": 256, "APSeedToken": 1,
            "CarryProhibition": 1, "TrashProhibition": 0,
            "PlayFlashbackDemoProhibition": 0,
        }
        with patch("tools.cemu.getdemo_state.snapshot", return_value={
                "manager": 1, "screen": 0, "name": None,
                "activity": 255, "screen_active": False}), \
             patch("tools.cemu.menu_diagnostic.screens", return_value={}), \
             patch("tools.cemu.presentation_ready.presentation_gameplay_state",
                   return_value={"strict_ready": False, "hudless_ready": False,
                                 "ready": False, "screens": []}):
            result = presentation_ready.diagnose(
                Mock(), Mock(base=0), lambda: flags)
        self.assertFalse(result["ready"])
        self.assertEqual(result["reasons"], [
            "screen_catalog_not_gameplay", "protection:CarryProhibition"])

    def test_dialogue_markers_and_context_preserved_without_teleport_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            data = loading.capture(lambda: {"value": 1}, Mock(side_effect=["", "", "oui"]),
                Path(folder) / "trace.json", "dialogue", interval=100,
                instructions=[("dialogue_open", "open"), ("gameplay_after", "closed")],
                confirmation="closed?", confirmation_key="dialogue_completed_user_report", context="NPC")
        self.assertEqual([m["stage"] for m in data["user_markers"]], ["dialogue_open", "gameplay_after"])
        self.assertEqual(data["context_user_report"], "NPC")
        self.assertTrue(data["dialogue_completed_user_report"])
        self.assertNotIn("teleport_completed_user_report", data)

    def catalog(self):
        rows = [dict(index=i, pointer=0x40000000 + i * 1024, activity=255, state_94=0x01000000) for i in range(99)]
        for i in (47, 74, 85):
            rows[i].update(pointer=0, state_94=None)
        rows[42].update(activity=0, state_94=0x200)
        return dict(screens=rows)

    def test_loading_closed_without_hud_is_not_ready(self):
        state = self.catalog()
        self.assertTrue(loading.gameplay_state(state)["ready"])
        state["screens"][42].update(activity=255, state_94=0xfc0000)
        self.assertFalse(loading.gameplay_state(state)["ready"])

    def test_presentation_accepts_exact_hudless_shrine_signature_only_when_enabled(self):
        state = self.catalog()
        state["screens"][42].update(activity=255, state_94=0)
        state["screens"][68]["state_94"] = 0x01fc0000
        classified = presentation_ready.presentation_gameplay_state(state)
        self.assertEqual(classified["mode"], "hudless_shrine")
        flags = {name: 0 for name in presentation_ready.PROTECTIONS}
        ui = {"manager": 1, "screen": 0, "name": ""}
        with patch("tools.cemu.getdemo_state.snapshot", return_value=ui), \
             patch("tools.cemu.menu_diagnostic.screens", return_value=state):
            self.assertFalse(presentation_ready.ready(Mock(), Mock(base=0), lambda: flags))
            self.assertTrue(presentation_ready.ready(
                Mock(), Mock(base=0), lambda: flags, allow_hudless=True))

        state["screens"][78]["activity"] = 1
        self.assertEqual(
            presentation_ready.presentation_gameplay_state(state)["mode"], "blocked")

    def test_a_new_game_before_its_first_loading_is_ready(self):
        # Measured: the loading screen (78) stays in 0x01fc0000 until first shown.
        state = self.catalog()
        state["screens"][78]["state_94"] = 0x01fc0000
        self.assertTrue(loading.gameplay_state(state)["ready"])
        self.assertTrue(presentation_ready.presentation_gameplay_state(state)["strict_ready"])
        state["screens"][78]["activity"] = 1                 # while it shows: not ready
        self.assertFalse(loading.gameplay_state(state)["ready"])
        state = self.catalog()
        state["screens"][84]["state_94"] = 0x01fc0000        # only the loading screen has that state
        self.assertFalse(loading.gameplay_state(state)["ready"])

    def test_hud_does_not_override_loading_or_unknown_state(self):
        for index in (78, 84, 44):
            state = self.catalog()
            state["screens"][index]["state_94"] = 0x01000300
            self.assertFalse(loading.gameplay_state(state)["ready"])

    def test_bombs_inactive_hud_variant_keeps_other_readiness_barriers(self):
        from copy import deepcopy
        state = self.catalog()
        state['screens'][42].update(activity=255, state_94=0x00fc0000)
        for index in (44, 46, 68):
            state['screens'][index]['state_94'] = 0x01fc0000
        flags = {name: 0 for name in presentation_ready.PROTECTIONS}
        ui = {'manager': 1, 'screen': 0, 'name': ''}
        self.assertEqual(presentation_ready.presentation_gameplay_state(state)['mode'], 'hudless_shrine')
        self.assertFalse(loading.gameplay_state(state)['ready'])
        with patch('tools.cemu.getdemo_state.snapshot', return_value=ui), \
             patch('tools.cemu.menu_diagnostic.screens', return_value=state):
            self.assertFalse(presentation_ready.ready(Mock(), Mock(base=0), lambda: flags))
            self.assertTrue(presentation_ready.ready(Mock(), Mock(base=0), lambda: flags, allow_hudless=True))
            for name in flags:
                flags[name] = 1
                self.assertFalse(presentation_ready.ready(Mock(), Mock(base=0), lambda: flags, allow_hudless=True))
                flags[name] = 0
            for change in ({'screen': 2}, {'name': 'Obj_RemoteBomb'}, {'manager': 0}):
                with patch('tools.cemu.getdemo_state.snapshot', return_value={**ui, **change}):
                    self.assertFalse(presentation_ready.ready(Mock(), Mock(base=0), lambda: flags, allow_hudless=True))
        for index, change in [(42, {'state_94': 0x00fc0200}), (42, {'activity': 0}),
                              (42, {'pointer': 0}), (78, {'activity': 1}),
                              (84, {'state_94': 0x01000300}), (85, {'pointer': 1}),
                              (74, {'pointer': 1}), (44, {'activity': 1}),
                              (46, {'activity': 1}), (47, {'pointer': 1}),
                              (68, {'state_94': 0x01000300})]:
            mutated = deepcopy(state)
            mutated['screens'][index].update(change)
            self.assertFalse(presentation_ready.presentation_gameplay_state(mutated)['ready'], (index, change))

    def test_the_screens_holding_link_are_named(self):
        # Every screen that makes the catalog not gameplay, the HUD apart, is named with what it shows.
        state = self.catalog()
        self.assertEqual(presentation_ready.unexpected_screens(state), [])
        for index, change in [(78, {'activity': 1}), (84, {'state_94': 0x01000300}), (85, {'pointer': 1}),
                              (74, {'pointer': 1}), (44, {'activity': 1}), (46, {'activity': 1}),
                              (47, {'pointer': 1}), (68, {'state_94': 0x01000300})]:
            mutated = deepcopy(state)
            mutated['screens'][index].update(change)
            named = presentation_ready.unexpected_screens(mutated)
            self.assertEqual(len(named), 1, (index, named))
            self.assertIn(f"(screen {index})", named[0])
        state['screens'][78].update(activity=1, state_94=0x01000300)
        self.assertIn("loading (screen 78): present, activity 1, state 0x1000300",
                      presentation_ready.summary({"reasons": ["screen_catalog_not_gameplay"],
                                                  "unexpected_screens": presentation_ready.unexpected_screens(state),
                                                  "gameplay": {"screens": [state['screens'][42]]}}))

    def test_wait_requires_loading_then_three_ready_samples(self):
        busy = self.catalog()
        busy["screens"][78]["activity"] = 1
        read = Mock(side_effect=[self.catalog(), busy, self.catalog(), self.catalog(), self.catalog()])
        with tempfile.TemporaryDirectory() as folder, patch.object(loading.time, "sleep"):
            result = loading.wait_for_gameplay(read, Path(folder) / "trace.json")
        self.assertEqual(read.call_count, 5)
        self.assertEqual(result["status"], "released")
        self.assertTrue(result["loading_seen"])
        self.assertFalse(result["native_calls_issued"])

    def test_dialogue_must_disappear_even_if_hud_has_returned(self):
        busy = self.catalog()
        busy["screens"][74].update(pointer=0x41000000, activity=1, state_94=0x01000200)
        closing = self.catalog()
        closing["screens"][74].update(pointer=0x41000000, state_94=0x01000000)
        self.assertFalse(loading.gameplay_state(closing)["ready"])
        read = Mock(side_effect=[self.catalog(), busy, closing, self.catalog(), self.catalog(), self.catalog()])
        with tempfile.TemporaryDirectory() as folder, patch.object(loading.time, "sleep"):
            result = loading.wait_for_gameplay(read, Path(folder) / "trace.json", activity="dialogue")
        self.assertEqual(read.call_count, 6)
        self.assertTrue(result["dialogue_seen"])
        self.assertEqual(result["status"], "released")

    def test_partial_read_failure_keeps_other_components_without_writes(self):
        process, cave = Mock(), Mock(base=0, call_n=12, pf_req=16)
        process.read.return_value = bytes(4)
        cave.sub_state.return_value = (0, 0, 0, 0, 0)
        with patch.object(loading.menu_diagnostic, "screens", side_effect=ValueError("unavailable")), \
             patch.object(loading.autonomous_eventflow, "inspect", return_value={"manager_available": False}):
            state = loading.snapshot(process, cave)
        self.assertEqual(state["screens"]["read_error"], "unavailable")
        self.assertEqual(state["call_count"], 0)
        process.write.assert_not_called()
        cave.call_pf.assert_not_called()

    def test_interrupted_capture_is_saved_and_not_called_collected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.json"
            with self.assertRaises(KeyboardInterrupt):
                loading.capture(lambda: {"value": 1}, Mock(side_effect=KeyboardInterrupt), path, "test")
            data = json.loads(path.read_text())
        self.assertEqual(data["status"], "interrupted")
        self.assertFalse(data["native_calls_issued"])
        self.assertTrue(data["transitions"])

    def test_read_failure_preserved_then_recovery_and_user_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trace.json"
            data = loading.capture(Mock(side_effect=[RuntimeError("loading"), {"value": 2}]),
                                   Mock(side_effect=["", "oui"]), path, "test", interval=100)
        self.assertEqual(data["status"], "needs_review")
        self.assertEqual(data["read_error_samples"], 1)
        self.assertTrue(data["teleport_completed_user_report"])
        self.assertEqual(data["transitions"][-1]["state"], {"value": 2})
