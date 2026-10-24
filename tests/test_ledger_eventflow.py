"""Validate the resource diagnostic against the user's vanilla flow."""
import os
from pathlib import Path
import unittest

import oead
from botw_patch.events import graph_snapshot, read_flow
from botw_patch.ledger_experiment import (FOLLOWUP_DELIVERED, THIRD_DELIVERED,
    patch_campfire, patch_campfire_capacity_delivery,
    patch_campfire_delivery, patch_campfire_guarded_delivery,
    patch_delivery_event_info, SAVED, ZERO, DELIVERED)
from botw_patch.resources import unpack

CONTENT = Path(os.environ.get("BOTW_TEST_CONTENT", str(Path.home() /
    "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content")))


@unittest.skipUnless((CONTENT / "Pack/TitleBG.pack").is_file(), "requires user's game dump")
class EventFlowLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive = oead.Sarc(unpack((CONTENT / "Pack/TitleBG.pack").read_bytes()))
        cls.raw = bytes(archive.get_file("EventFlow/Demo007_1.bfevfl").data)
        cls.patched, cls.added = patch_campfire(cls.raw)

    def test_only_cancel_edge_changes_and_serialization_is_reproducible(self):
        original = graph_snapshot(read_flow(self.raw))
        patched = graph_snapshot(read_flow(self.patched))
        for name, event in original["events"].items():
            if name == "Event3":
                event["cases"][3] = "APLedger_IsZeroToken"
            self.assertEqual(event, patched["events"][name], name)
        self.assertEqual(original["entry_points"], patched["entry_points"])
        self.assertEqual(patch_campfire(self.raw)[0], self.patched)
        for old, new in zip(original["actors"], patched["actors"]):
            if old[0] == "EventSystemActor":
                old[3].append("Demo_SetGameDataInt")
                old[4].append("CheckGameDataInt")
            self.assertEqual(old, new)

    def test_native_actions_toggle_only_known_pairs_and_rejoin_vanilla(self):
        graph = graph_snapshot(read_flow(self.patched))["events"]
        def interpret(values):
            values = dict(values)
            cursor = graph["Event3"]["cases"][3]
            visited = []
            while cursor != "Event76":
                self.assertLess(len(visited), 10)
                visited.append(cursor)
                node = graph[cursor]
                params = node["params"]
                self.assertEqual(node["actor"], "EventSystemActor")
                name = params["GameDataIntName"]
                if node["type"] == "SwitchEvent":
                    self.assertEqual(node["actor_query"], "CheckGameDataInt")
                    self.assertEqual(params["Operator"], "Equal")
                    cursor = node["cases"][int(values[name] == params["Value"])]
                else:
                    self.assertEqual(node["actor_action"], "Demo_SetGameDataInt")
                    self.assertTrue(params["IsWaitFinish"])
                    values[name] = params["Value"]
                    cursor = node["nxt"]
            return values
        self.assertEqual(interpret(ZERO), SAVED)
        self.assertEqual(interpret(SAVED), ZERO)
        for other in ({"APReceivedCursor": 17, "APSeedToken": 0},
                      {"APReceivedCursor": 0, "APSeedToken": SAVED["APSeedToken"]},
                      {"APReceivedCursor": 0, "APSeedToken": 42}):
            self.assertEqual(interpret(other), other)

    def test_unknown_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported vanilla"):
            patch_campfire(self.raw + b"changed")

    def test_delivery_calls_vanilla_before_cursor_and_never_repeats(self):
        raw, _ = patch_campfire_delivery(self.raw)
        graph = graph_snapshot(read_flow(raw))["events"]
        original = graph_snapshot(read_flow(self.raw))["events"]
        for name, node in original.items():
            if name == "Event3":
                node["cases"][3] = "APLedger_IsZeroToken"
            self.assertEqual(node, graph[name])
        self.assertFalse(any(name.startswith("APLedger_Reset") for name in graph))
        for initial, grants in [(ZERO, 1), (DELIVERED, 0),
                                 ({"APReceivedCursor": 256, "APSeedToken": 0}, 0),
                                 ({"APReceivedCursor": 0, "APSeedToken": 42}, 0)]:
            values, trace = dict(initial), []
            cursor = graph["Event3"]["cases"][3]
            while cursor != "Event76":
                self.assertLess(len(trace), 10)
                node = graph[cursor]
                params = node["params"]
                if node["type"] == "SwitchEvent":
                    cursor = node["cases"][int(values[params["GameDataIntName"]] == params["Value"])]
                    trace.append("query")
                elif node["type"] == "SubFlowEvent":
                    self.assertEqual((node["res_flowchart_name"], node["entry_point_name"]),
                                     ("GetDemo", "GetItemByName"))
                    self.assertEqual(params, {"CheckTargetActorName": "Item_Fruit_A", "IsInvalidOpenPouch": False})
                    trace.append("grant")
                    cursor = node["nxt"]
                else:
                    self.assertEqual(node["actor_action"], "Demo_SetGameDataInt")
                    trace.append("commit")
                    values[params["GameDataIntName"]] = params["Value"]
                    cursor = node["nxt"]
            self.assertEqual(trace.count("grant"), grants)
            self.assertEqual(values, DELIVERED if grants else initial)
            if grants:
                self.assertLess(trace.index("grant"), trace.index("commit"))

    def test_delivery_dependency_is_declared_without_other_metadata_changes(self):
        archive = oead.Sarc((CONTENT / "Pack/Bootup.pack").read_bytes())
        raw = bytes(archive.get_file("Event/EventInfo.product.sbyml").data)
        patched, _ = patch_delivery_event_info(raw)
        original = oead.byml.from_binary(unpack(raw))
        actual = oead.byml.from_binary(unpack(patched))
        key = "Demo007_1<Demo007_1>"
        self.assertEqual([f["file"] for f in actual[key]["subfile"]], ["GetDemo.bfevfl"])
        # GetDemo is the new external subflow in the generated event.
        flow, _ = patch_campfire_delivery(self.raw)
        grant = graph_snapshot(read_flow(flow))["events"]["APLedger_DeliverApple"]
        self.assertIn(grant["res_flowchart_name"] + ".bfevfl",
                      [f["file"] for f in actual[key]["subfile"]])
        del actual[key]["subfile"]
        self.assertEqual(oead.byml.to_text(actual), oead.byml.to_text(original))
        self.assertEqual(patch_delivery_event_info(raw)[0], patched)
        with self.assertRaisesRegex(ValueError, "unsupported vanilla EventInfo"):
            patch_delivery_event_info(bytes(oead.yaz0.compress(unpack(raw) + b"modified")))

    def test_startup_control_only_replaces_external_call_with_wait(self):
        from tools.build_delivery_control import remove_external_call
        delivery, _ = patch_campfire_delivery(self.raw)
        control, _ = remove_external_call(delivery)
        before = graph_snapshot(read_flow(delivery))
        after = graph_snapshot(read_flow(control))
        node = after["events"]["APLedger_DeliverApple"]
        self.assertEqual(node["actor_action"], "Demo_WaitFrame")
        self.assertEqual(node["params"], {"Frame": 1, "IsWaitFinish": True})
        self.assertEqual(node["nxt"], before["events"]["APLedger_DeliverApple"]["nxt"])
        before["events"]["APLedger_DeliverApple"] = node
        self.assertEqual(before, after)

    def test_direct_item_uses_vanilla_action_without_external_dependency(self):
        from tools.build_delivery_control import direct_item_call, remove_external_call
        delivery, _ = patch_campfire_delivery(self.raw)
        direct, _ = direct_item_call(delivery)
        control, _ = remove_external_call(delivery)
        graph = graph_snapshot(read_flow(direct))
        before = graph_snapshot(read_flow(control))
        action = graph["events"]["APLedger_DeliverApple"]
        self.assertEqual(action["actor_action"], "Demo_SetItemDataToPouch")
        self.assertEqual(action["params"], {"IsWaitFinish": False, "TargetActorName": "Item_Fruit_A"})
        self.assertEqual(action["nxt"], before["events"]["APLedger_DeliverApple"]["nxt"])
        before["events"]["APLedger_DeliverApple"] = action
        next(a for a in before["actors"] if a[0] == "EventSystemActor")[3].append("Demo_SetItemDataToPouch")
        self.assertEqual(before, graph)
        archive = oead.Sarc((CONTENT / "Pack/TitleBG.pack").read_bytes())
        vanilla = graph_snapshot(read_flow(bytes(archive.get_file("EventFlow/GetDemo.bfevfl").data)))
        entry = dict(vanilla["entry_points"])["GetItemByName"]
        donor = vanilla["events"][entry]
        self.assertEqual(donor["actor_action"], action["actor_action"])
        self.assertEqual(donor["actor"], action["actor"])
        self.assertEqual(donor["params"]["IsWaitFinish"], action["params"]["IsWaitFinish"])
        self.assertEqual(donor["params"]["TargetActorName"], ("Argument", "CheckTargetActorName"))

    def test_guarded_delivery_wraps_mutation_and_commit_with_vanilla_save_guard(self):
        archive = oead.Sarc((CONTENT / "Pack/TitleBG.pack").read_bytes())
        operation_guide = bytes(archive.get_file(
            "EventFlow/OperationGuide.bfevfl").data)
        raw, _ = patch_campfire_guarded_delivery(self.raw, operation_guide)
        prepatched = patch_campfire_delivery(self.raw)[0]
        self.assertEqual(
            patch_campfire_guarded_delivery(prepatched, operation_guide)[0],
            raw)
        graph = graph_snapshot(read_flow(raw))
        events = graph["events"]
        expected_path = [
            "APLedger_SaveGuardON",
            "APLedger_DeliverApple",
            "APLedger_SetA_APReceivedCursor",
            "APLedger_SetA_APSeedToken",
            "APLedger_SaveGuardOFF",
            "Event76",
        ]
        cursor = events["APLedger_IsZeroCursor"]["cases"][1]
        actual = []
        while cursor != "Event76":
            actual.append(cursor)
            cursor = events[cursor]["nxt"]
        actual.append(cursor)
        self.assertEqual(actual, expected_path)
        self.assertEqual(events["APLedger_SaveGuardON"]["actor_action"],
                         "Demo_FlagON")
        self.assertEqual(events["APLedger_SaveGuardOFF"]["actor_action"],
                         "Demo_FlagOFF")
        for name in ("APLedger_SaveGuardON", "APLedger_SaveGuardOFF"):
            self.assertEqual(events[name]["params"], {
                "FlagName": "SaveProhibition", "IsWaitFinish": True})
        self.assertEqual(events["APLedger_DeliverApple"]["actor_action"],
                         "Demo_SetItemDataToPouch")
        self.assertEqual(events["APLedger_DeliverApple"]["params"], {
            "IsWaitFinish": False, "TargetActorName": "Item_Fruit_A"})

        donor = graph_snapshot(read_flow(operation_guide))["events"]
        for command in ("Demo_FlagON", "Demo_FlagOFF"):
            candidates = [node for node in donor.values()
                          if node.get("actor_action") == command
                          and node.get("params", {}).get("FlagName") ==
                          "SaveProhibition"]
            self.assertTrue(candidates)
            self.assertEqual(candidates[0]["params"], {
                "FlagName": "SaveProhibition", "IsWaitFinish": True})

    def test_fault_variant_holds_after_grant_before_followup_commit(self):
        archive = oead.Sarc((CONTENT / "Pack/TitleBG.pack").read_bytes())
        operation_guide = bytes(archive.get_file(
            "EventFlow/OperationGuide.bfevfl").data)
        raw, _ = patch_campfire_guarded_delivery(
            self.raw, operation_guide, start=DELIVERED,
            committed=FOLLOWUP_DELIVERED, hold_frames=1800)
        events = graph_snapshot(read_flow(raw))["events"]
        self.assertEqual(events["APLedger_IsZeroToken"]["params"]["Value"],
                         DELIVERED["APSeedToken"])
        self.assertEqual(events["APLedger_IsZeroCursor"]["params"]["Value"],
                         DELIVERED["APReceivedCursor"])
        self.assertEqual(events["APLedger_DeliverApple"]["nxt"],
                         "APLedger_FaultWindow")
        self.assertEqual(events["APLedger_FaultWindow"], {
            "type": "ActionEvent",
            "nxt": "APLedger_SetA_APReceivedCursor",
            "actor": "EventSystemActor",
            "actor_action": "Demo_WaitFrame",
            "params": {"Frame": 1800, "IsWaitFinish": True},
        })
        self.assertEqual(
            events["APLedger_SetA_APReceivedCursor"]["params"]["Value"],
            FOLLOWUP_DELIVERED["APReceivedCursor"])

    def test_normal_followup_has_no_fault_window(self):
        archive = oead.Sarc((CONTENT / "Pack/TitleBG.pack").read_bytes())
        operation_guide = bytes(archive.get_file(
            "EventFlow/OperationGuide.bfevfl").data)
        raw, _ = patch_campfire_guarded_delivery(
            self.raw, operation_guide, start=DELIVERED,
            committed=FOLLOWUP_DELIVERED)
        events = graph_snapshot(read_flow(raw))["events"]
        self.assertNotIn("APLedger_FaultWindow", events)
        self.assertEqual(events["APLedger_DeliverApple"]["nxt"],
                         "APLedger_SetA_APReceivedCursor")
        self.assertEqual(
            events["APLedger_SetA_APReceivedCursor"]["params"]["Value"],
            FOLLOWUP_DELIVERED["APReceivedCursor"])

    def test_capacity_preflight_refuses_before_guard_grant_and_cursor(self):
        archive = oead.Sarc((CONTENT / "Pack/TitleBG.pack").read_bytes())
        operation_guide = bytes(archive.get_file(
            "EventFlow/OperationGuide.bfevfl").data)
        capacity_donor = bytes(archive.get_file(
            "EventFlow/Demo002_0.bfevfl").data)
        full_donor = bytes(archive.get_file("EventFlow/GetDemo.bfevfl").data)
        raw, _ = patch_campfire_capacity_delivery(
            self.raw, operation_guide, capacity_donor, full_donor, count=999)
        events = graph_snapshot(read_flow(raw))["events"]
        self.assertEqual(events["APLedger_IsZeroCursor"]["cases"][1],
                         "APLedger_CheckCapacity")
        check = events["APLedger_CheckCapacity"]
        self.assertEqual(check["actor_query"], "CheckAddPorchItem")
        self.assertEqual(check["params"], {
            "Count": 999, "PorchItemName": "Item_Fruit_A"})
        self.assertEqual(check["cases"], {
            1: "APLedger_SaveGuardON", 0: "APLedger_InventoryFull"})
        self.assertEqual(events["APLedger_InventoryFull"], {
            "type": "ActionEvent", "nxt": "Event76",
            "actor": "EventSystemActor",
            "actor_action": "Demo_AppearFullPouchInfo",
            "params": {"IsWaitFinish": True,
                       "PorchItemName": "Item_Fruit_A"},
        })
        self.assertEqual(
            events["APLedger_SetA_APReceivedCursor"]["params"]["Value"],
            THIRD_DELIVERED["APReceivedCursor"])

    def test_presentation_only_has_sound_and_dialog_with_vanilla_continuation(self):
        from tools.build_delivery_control import presentation_call
        delivery, _ = patch_campfire_delivery(self.raw)
        raw, _ = presentation_call(delivery)
        graph = graph_snapshot(read_flow(raw))
        original = graph_snapshot(read_flow(self.raw))
        added = set(graph["events"]) - set(original["events"])
        self.assertEqual(added, {"APDisplay_Sound", "APDisplay_Dialog"})
        self.assertEqual(graph["events"]["APDisplay_Sound"]["nxt"], "APDisplay_Dialog")
        self.assertEqual(graph["events"]["APDisplay_Dialog"]["nxt"], "Event76")
        original["events"]["Event3"]["cases"][3] = "APDisplay_Sound"
        for name, event in original["events"].items():
            self.assertEqual(event, graph["events"][name])
        self.assertEqual(original["entry_points"], graph["entry_points"])
        archive = oead.Sarc((CONTENT / "Pack/TitleBG.pack").read_bytes())
        donor = graph_snapshot(read_flow(bytes(archive.get_file("EventFlow/GetDemo.bfevfl").data)))
        for actual_name, donor_name in [("APDisplay_Dialog", "Event175"), ("APDisplay_Sound", "Event253")]:
            expected = donor["events"][donor_name]
            expected["nxt"] = graph["events"][actual_name]["nxt"]
            if donor_name == "Event175":
                expected["params"]["IsInvalidOpenPouch"] = False
                expected["params"]["TargetActorName"] = "Item_Fruit_A"
            self.assertEqual(expected, graph["events"][actual_name])

    def test_close_message_variant_copies_vanilla_actor_and_only_inserts_close(self):
        from tools.build_delivery_control import presentation_call
        archive = oead.Sarc((CONTENT / "Pack/TitleBG.pack").read_bytes())
        donor = bytes(archive.get_file("EventFlow/GetDemo.bfevfl").data)
        delivery, _ = patch_campfire_delivery(self.raw)
        before = graph_snapshot(read_flow(presentation_call(delivery)[0]))
        after = graph_snapshot(read_flow(presentation_call(delivery, donor)[0]))
        vanilla = graph_snapshot(read_flow(donor))
        close = dict(vanilla["events"]["Event183"])
        close["nxt"] = "APDisplay_Dialog"
        before["events"]["APDisplay_CloseMessage"] = close
        before["events"]["APDisplay_Sound"]["nxt"] = "APDisplay_CloseMessage"
        before["actors"].append(next(a for a in vanilla["actors"] if a[0] == "EventSystemActor[Temp]"))
        self.assertEqual(before, after)

    def test_waiting_close_changes_only_completion_policy_and_has_vanilla_precedent(self):
        from tools.build_delivery_control import presentation_call
        from tools.build_ui_close_trace import wait_for_message_close
        archive = oead.Sarc((CONTENT / "Pack/TitleBG.pack").read_bytes())
        donor = bytes(archive.get_file("EventFlow/GetDemo.bfevfl").data)
        delivery, _ = patch_campfire_delivery(self.raw)
        raw = presentation_call(delivery, donor)[0]
        expected = graph_snapshot(read_flow(raw))
        expected["events"]["APDisplay_CloseMessage"]["params"]["IsWaitFinish"] = True
        result, _ = wait_for_message_close(raw)
        self.assertEqual(graph_snapshot(read_flow(result)), expected)
        vanilla = graph_snapshot(read_flow(donor))["events"]["Event214"]
        self.assertEqual(vanilla["actor_action"], "Demo_CloseMessageDialog")
        self.assertEqual(vanilla["params"], {"IsWaitFinish": True})
        with self.assertRaisesRegex(ValueError, "unexpected close-message"):
            wait_for_message_close(result)
