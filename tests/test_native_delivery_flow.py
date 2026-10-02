from pathlib import Path
import unittest

import oead

from botw_patch.delivery_flow import (
    BIND_ENTRY, QUIET_EVENT_INFO, QUIET_FLOW, compile_native_entries, host_of, delivery_catalog,
    patch_delivery_event_info, patch_delivery_flow, patch_session_binding,
    retarget_session_binding)
from botw_patch.events import graph_snapshot, read_flow
from botw_patch.resources import unpack
from botw_patch.traps import TRAPS, add_entries


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".build/ledger-validation/4e60affc56def09f/content"


class NativeDeliveryCompilationTests(unittest.TestCase):
    def test_catalog_covers_verified_action_families_only(self):
        entries, unsupported = compile_native_entries()
        self.assertEqual(len([e for e in entries if not e.quiet]), 60)
        self.assertEqual(set(unsupported), set())
        self.assertEqual(len({entry.entry_name for entry in entries}), len(entries))
        self.assertTrue(all(entry.plan.mutations for entry in entries))

    def test_steps_with_a_get_window_have_a_silent_twin(self):
        entries, _ = compile_native_entries()
        by_name = {e.entry_name: e for e in entries}
        quiet = [e for e in entries if e.quiet]
        for twin in quiet:
            step = by_name[twin.entry_name[:-1]]
            self.assertEqual((twin.item_name, twin.step, twin.cursor_delta),
                             (step.item_name, step.step, step.cursor_delta))
            self.assertTrue(all(m.kind.value in ("grant_actor", "champion_actor",
                                                 "increase_rupee", "set_bool", "set_s32",
                                                 "trap_spent")
                                for m in twin.plan.mutations))
        self.assertEqual({e.item_name for e in quiet if e.item_name in (
            "Heart Container", "Stamina Vessel", "Ancient Bridle")}, set())
        # A rune given back: its flag and selection, without the download screen.
        (rune,) = [e for e in quiet if e.item_name == "Magnesis"]
        self.assertEqual([(m.kind.value, m.target, m.value) for m in rune.plan.mutations],
                         [("set_bool", "IsGet_Obj_Magnetglove", True),
                          ("set_s32", "PlayerEquipItemType", 2)])
        catalog = delivery_catalog()
        self.assertEqual([s.get("quiet_entry") for s in
                          catalog["items"]["Zora Set"]["variants"]["default"]],
                         [s["entry"] + "Q" for s in
                          catalog["items"]["Zora Set"]["variants"]["default"]])
        self.assertIsNone(catalog["items"]["Heart Container"]["variants"]["default"][0]
                          .get("quiet_entry"))

    def test_a_rupee_bundle_given_back_uses_the_games_rupee_action(self):
        entries, _ = compile_native_entries()
        (twin,) = [e for e in entries if e.item_name == "Rupee Bundle" and e.quiet]
        self.assertEqual([(m.kind.value, m.value) for m in twin.plan.mutations],
                         [("increase_rupee", 20)])

    def test_multi_piece_cursor_deltas_resume_without_regrant(self):
        entries, _ = compile_native_entries()
        snowquill = [entry for entry in entries
                     if entry.item_name == "Snowquill Set" and not entry.quiet]
        self.assertEqual([entry.step for entry in snowquill], [0, 1, 2])
        self.assertEqual([entry.step_count for entry in snowquill], [3, 3, 3])
        self.assertEqual([entry.cursor_delta for entry in snowquill], [1, 1, 254])
        self.assertEqual([entry.plan.capacity_actor for entry in snowquill], [
            "Armor_009_Head", "Armor_009_Upper", "Armor_009_Lower"])

    def test_progressive_variants_are_stable_and_saturating(self):
        entries, _ = compile_native_entries()
        climbing = [entry for entry in entries
                    if entry.item_name == "Progressive Climbing Gear" and not entry.quiet]
        self.assertEqual([entry.progressive_tier for entry in climbing], [0, 1, 2])
        self.assertEqual([entry.plan.capacity_actor for entry in climbing], [
            "Armor_014_Upper", "Armor_014_Head", "Armor_014_Lower"])
        catalog = delivery_catalog()
        self.assertEqual(set(catalog["items"]["Progressive Climbing Gear"]
                             ["variants"]), {"0", "1", "2"})

    def test_binding_catalog_is_explicit_and_zero_only(self):
        catalog = delivery_catalog(binding_token=123456)
        self.assertEqual(catalog["binding"], {
            "entry": BIND_ENTRY, "seed_token": 123456,
            "requires_cursor": 0, "requires_token": 0})
        with self.assertRaisesRegex(ValueError, "positive signed s32"):
            delivery_catalog(binding_token=0)

    def test_bool_group_has_one_commit_and_no_capacity_preflight(self):
        entries, _ = compile_native_entries()
        sensor = next(entry for entry in entries
                      if entry.item_name == "Sheikah Sensor")
        self.assertIsNone(sensor.plan.capacity_actor)
        self.assertEqual(len(sensor.plan.mutations), 3)
        self.assertEqual(sensor.cursor_delta, 256)


@unittest.skipUnless((SOURCE / "Pack/TitleBG.pack").is_file(),
                     "requires immutable presentation build")
class NativeDeliveryGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        title = oead.Sarc(unpack((SOURCE / "Pack/TitleBG.pack").read_bytes()))
        cls.member = staticmethod(lambda name: bytes(title.get_file(
            f"EventFlow/{name}.bfevfl").data))
        cls.original = cls.member("Demo007_1")
        cls.specs, cls.unsupported = compile_native_entries()
        cls.with_traps, _ = add_entries(cls.original, "Demo007_1")
        cls.patched, cls.changes = patch_delivery_flow(
            cls.with_traps, cls.member("OperationGuide"),
            cls.member("Demo002_0"), cls.member("GetDemo"),
            cls.member("GetDemo"), cls.member("Demo017_0"))
        with_traps, _ = add_entries(cls.member("OperationGuide"))
        cls.quiet, _ = patch_delivery_flow(
            with_traps, cls.member("OperationGuide"),
            cls.member("Demo002_0"), cls.member("GetDemo"),
            cls.member("GetDemo"), cls.member("Demo017_0"), quiet=True)

    def spec(self, item, step=0, tier=None):
        return next(entry for entry in self.specs
                    if entry.item_name == item and entry.step == step
                    and entry.progressive_tier == tier)

    def test_silent_twins_live_in_a_resident_non_demo_flowchart(self):
        # The twins' host is the resident OperationGuide (see
        # delivery_flow.QUIET_FLOW); its own graph stays as it is.
        demo = graph_snapshot(read_flow(self.patched))
        vanilla = graph_snapshot(read_flow(self.member("OperationGuide")))
        quiet = graph_snapshot(read_flow(self.quiet))
        self.assertFalse(QUIET_FLOW.startswith("Demo"))
        self.assertEqual(quiet["name"], QUIET_FLOW)
        twins = {s.entry_name for s in self.specs if host_of(s) == QUIET_FLOW}
        # With the twins, the steps that open no window of their own.
        self.assertEqual({s.item_name for s in self.specs
                          if host_of(s) == QUIET_FLOW and not s.quiet}, {
            "Sheikah Sensor", "Ancient Bridle", "Ancient Saddle",
            *(trap.item for trap in TRAPS if trap.host == QUIET_FLOW), "Cucco Swarm"})
        # The traps' own entries come first, then the delivery entries.
        added = [name for name, _ in quiet["entry_points"][len(vanilla["entry_points"]):]]
        self.assertEqual(quiet["entry_points"][:len(vanilla["entry_points"])],
                         vanilla["entry_points"])
        self.assertEqual(set(added), twins | {trap.entry for trap in TRAPS
                                              if trap.host == QUIET_FLOW})
        self.assertFalse(twins & {name for name, _ in demo["entry_points"]})
        for name, node in vanilla["events"].items():
            self.assertEqual(quiet["events"][name], node)
        catalog = delivery_catalog()
        step = catalog["items"]["Zora Set"]["variants"]["default"][1]
        self.assertEqual((step["quiet_entry"], step["quiet_flow"]),
                         ("APD_BFA8EB4C_01Q", "OperationGuide"))
        self.assertNotIn("flow", step)
        self.assertNotIn("flow", catalog["items"]["Stasis"]["variants"]["default"][0])
        self.assertEqual(catalog["items"]["Sheikah Sensor"]["variants"]["default"][0]["flow"],
                         "OperationGuide")

    def test_patch_is_deterministic_and_preserves_existing_graph(self):
        repeated, _ = patch_delivery_flow(
            self.with_traps, self.member("OperationGuide"),
            self.member("Demo002_0"), self.member("GetDemo"),
            self.member("GetDemo"), self.member("Demo017_0"))
        self.assertEqual(repeated, self.patched)
        before = graph_snapshot(read_flow(self.original))
        after = graph_snapshot(read_flow(self.patched))
        for name, node in before["events"].items():
            self.assertEqual(after["events"][name], node)
        self.assertEqual(after["entry_points"][:len(before["entry_points"])],
                         before["entry_points"])

    def test_actor_entry_refuses_before_guard_and_commits_before_release(self):
        spec = self.spec("Warm Doublet")
        graph = graph_snapshot(read_flow(self.patched))
        events = graph["events"]
        self.assertEqual(dict(graph["entry_points"])[spec.entry_name],
                         spec.entry_name + "_Capacity")
        capacity = events[spec.entry_name + "_Capacity"]
        self.assertEqual(capacity["actor_query"], "CheckAddPorchItem")
        self.assertEqual(capacity["params"], {
            "Count": 1, "PorchItemName": "Armor_044_Upper"})
        self.assertEqual(capacity["cases"], {
            1: spec.entry_name + "_GuardON",
            0: spec.entry_name + "_Reject"})
        self.assertEqual(events[spec.entry_name + "_Reject"], {
            "type": "ActionEvent", "nxt": spec.entry_name + "_Full",
            "actor": "EventSystemActor",
            "actor_action": "Demo_IncreaseGameDataInt",
            "params": {"GameDataIntName": "APDeliveryRejectCounter",
                       "Value": 1, "IsWaitFinish": True},
        })
        self.assertIsNone(events[spec.entry_name + "_Full"]["nxt"])
        path = [spec.entry_name + "_GuardON", spec.entry_name + "_Mut0",
                spec.entry_name + "_Commit", spec.entry_name + "_GuardOFF"]
        for current, following in zip(path, path[1:]):
            self.assertEqual(events[current]["nxt"], following)
        self.assertIsNone(events[path[-1]]["nxt"])
        # The piece is handed over by the game's own get window.
        self.assertEqual(events[path[1]]["res_flowchart_name"], "GetDemo")
        self.assertEqual(events[path[1]]["params"]["CheckTargetActorName"],
                         "Armor_044_Upper")
        self.assertEqual(events[path[2]]["params"], {
            "GameDataIntName": "APReceivedCursor", "Value": 256,
            "IsWaitFinish": True})

    def test_flag_group_mutates_all_flags_inside_one_guard(self):
        spec = self.spec("Sheikah Sensor")
        events = graph_snapshot(read_flow(self.quiet))["events"]
        self.assertNotIn(spec.entry_name + "_Capacity", events)
        cursor = spec.entry_name + "_GuardON"
        visited = []
        while cursor is not None:
            visited.append(cursor)
            cursor = events[cursor]["nxt"]
        self.assertEqual(visited, [
            spec.entry_name + "_GuardON", spec.entry_name + "_Mut0",
            spec.entry_name + "_Mut1", spec.entry_name + "_Mut2",
            spec.entry_name + "_Commit", spec.entry_name + "_GuardOFF"])
        flags = [events[name]["params"]["FlagName"]
                 for name in visited[1:4]]
        self.assertEqual(flags, [
            "IsGet_Obj_SheikSensor", "IsStart_Obj_SheikSensor",
            "App_SeakSensor_IsEnabled"])

    def test_rune_unlock_and_equip_commit_together(self):
        spec = self.spec("Stasis")
        graph = graph_snapshot(read_flow(self.patched))
        events = graph["events"]
        stem = spec.entry_name
        # Demo003_0 Item03, one after the other as the vanilla terminal:
        # IsDownloadDemo, the download screen, wait 70, the Slate's words, the
        # menu closed, then the rune's flag and selection.
        # Then Link puts the Slate away (Demo041_0<SheikPadSetOff>), and a
        # settle wait before the screen lets the map rest (pause_menu.py).
        chain = [stem + "_Mut0", stem + "_Mut0_Open", stem + "_Mut0_Wait",
                 stem + "_Mut0_Voice", stem + "_Mut0_Close", stem + "_Mut0_Flag", stem + "_Mut1"]
        full = [chain[0], stem + "_Mut0_Settle", *chain[1:6], stem + "_Mut0_Away",
                stem + "_Mut0_Idle", stem + "_Mut0_After", chain[6]]
        self.assertEqual(events[stem + "_GuardON"]["nxt"], full[0])
        for name, following in zip(full, full[1:]):
            self.assertEqual(events[name]["nxt"], following)
        self.assertEqual(events[chain[0]]["params"], {"FlagName": "IsDownloadDemo",
                                                      "IsWaitFinish": True})
        self.assertEqual((events[full[1]]["actor"], events[full[1]]["params"]),
                         ("EventSystemActor[01]", {"IsWaitFinish": True, "Frame": 10}))
        away, idle = events[stem + "_Mut0_Away"], events[stem + "_Mut0_Idle"]
        self.assertEqual((away["actor"], away["actor_action"], away["params"]["ASName"],
                          away["params"]["IsWaitFinish"]),
                         ("GameROMPlayer", "Demo_PlayASAdapt", "SheikPadSetOff", True))
        self.assertEqual((idle["params"]["ASName"], idle["params"]["IsWaitFinish"]),
                         ("DemoWait", False))
        self.assertEqual(events[stem + "_Mut0_After"]["params"],
                         {"IsWaitFinish": True, "Frame": 20})
        self.assertEqual((events[chain[1]]["actor"], events[chain[1]]["actor_action"],
                          events[chain[1]]["params"]), (
            "EventSystemActor", "Demo_OpenItemDownloadDemo",
            {"ItemType": 2, "IsWaitFinish": True, "IsEquip": True,
             "IsPowerUp": False, "IsPlayerClose": False}))
        self.assertEqual((events[chain[2]]["actor"], events[chain[2]]["params"]),
                         ("EventSystemActor[01]", {"IsWaitFinish": True, "Frame": 70}))
        self.assertEqual((events[chain[3]]["actor"], events[chain[3]]["actor_action"],
                          events[chain[3]]["params"]["MessageId"]),
                         ("NPC_DRCVoice", "Demo_OpenMessageDialog",
                          "DemoMsg/Demo003_0:Demo003_0_Text005"))
        self.assertEqual(events[chain[4]]["actor_action"], "Demo_CloseItemMenu")
        self.assertFalse([e for e in events.values() if e["type"] in ("ForkEvent", "JoinEvent")
                          and any(n.startswith(stem) for n in e.get("forks", []))])
        self.assertEqual(events[stem + "_Mut0_Flag"]["params"],
                         {"FlagName": "IsGet_Obj_StopTimer", "IsWaitFinish": True})
        self.assertEqual(events[stem + "_Mut1"], {
            "type": "ActionEvent", "nxt": stem + "_Commit",
            "actor": "EventSystemActor",
            "actor_action": "Demo_SetGameDataInt",
            "params": {"GameDataIntName": "PlayerEquipItemType",
                       "Value": 3, "IsWaitFinish": True},
        })

    def test_vessel_uses_complete_vanilla_getdemo_subflow(self):
        spec = self.spec("Heart Container")
        events = graph_snapshot(read_flow(self.patched))["events"]
        stem = spec.entry_name
        self.assertEqual(dict(graph_snapshot(read_flow(self.patched))
                              ["entry_points"])[stem], stem + "_GuardON")
        mutation = events[stem + "_Mut0"]
        self.assertEqual(mutation["type"], "SubFlowEvent")
        self.assertEqual(mutation["res_flowchart_name"], "GetDemo")
        self.assertEqual(mutation["entry_point_name"], "GetItemByName")
        self.assertEqual(mutation["params"], {
            "CheckTargetActorName": "Obj_HeartUtuwa_A_01",
            "IsInvalidOpenPouch": False})
        self.assertEqual(mutation["nxt"], stem + "_Commit")

    def test_a_champion_power_shows_the_games_get_window_in_vanilla_order(self):
        spec = self.spec("Mipha's Grace")
        events = graph_snapshot(read_flow(self.patched))["events"]
        stem = spec.entry_name + "_Mut0"
        self.assertEqual(events[stem]["actor_action"], "Demo_SetItemDataToPouch")
        self.assertEqual(events[stem]["nxt"], stem + "_Equip")
        self.assertEqual(events[stem + "_Equip"]["nxt"], stem + "_Show")
        show = events[stem + "_Show"]
        self.assertEqual((show["res_flowchart_name"], show["entry_point_name"]),
                         ("GetDemo", "ShowGetDemoDialogByName"))
        self.assertEqual(show["params"], {"CheckTargetActorName": "Obj_HeroSoul_Zora",
                                          "IsInvalidOpenPouch": False})
        self.assertEqual(show["nxt"], stem + "_GetFlag")

    def test_korok_seed_uses_the_vanilla_pouch_actor(self):
        spec = self.spec("Korok Seed")
        events = graph_snapshot(read_flow(self.patched))["events"]
        stem = spec.entry_name
        self.assertEqual(spec.plan.capacity_actor, "Obj_KorokNuts")
        self.assertEqual(events[stem + "_Capacity"]["params"], {
            "Count": 1, "PorchItemName": "Obj_KorokNuts"})
        self.assertEqual(events[stem + "_Mut0"]["params"], {
            "CheckTargetActorName": "Obj_KorokNuts", "IsInvalidOpenPouch": False})

    def test_rupee_bundle_uses_vanilla_red_rupee_getdemo(self):
        spec = self.spec("Rupee Bundle")
        events = graph_snapshot(read_flow(self.patched))["events"]
        stem = spec.entry_name
        self.assertIsNone(spec.plan.capacity_actor)
        self.assertEqual(events[stem + "_Mut0"]["res_flowchart_name"], "GetDemo")
        self.assertEqual(events[stem + "_Mut0"]["entry_point_name"], "GetItemByName")
        self.assertEqual(events[stem + "_Mut0"]["params"], {
            "CheckTargetActorName": "PutRupee_Red",
            "IsInvalidOpenPouch": False})
        # Given back: the quest action, not waited for (no frozen player).
        quiet = graph_snapshot(read_flow(self.quiet))["events"][stem + "Q_Mut0"]
        self.assertEqual((quiet["actor_action"], quiet["params"]), (
            "Demo_IncreaseRupee", {"Value": 20, "IsWaitFinish": False}))

    def test_event_info_adds_only_generated_entries(self):
        boot = oead.Sarc(unpack((SOURCE / "Pack/Bootup.pack").read_bytes()))
        raw = bytes(boot.get_file("Event/EventInfo.product.sbyml").data)
        patched, _ = patch_delivery_event_info(raw, self.specs)
        before = oead.byml.from_binary(unpack(raw))
        after = oead.byml.from_binary(unpack(patched))
        for key in before:
            self.assertEqual(oead.byml.to_text(after[key]),
                             oead.byml.to_text(before[key]))
        self.assertEqual(len(after), len(before) + len(self.specs))
        donor = oead.byml.to_text(before["Demo007_1<APDisplayStandalone>"])
        for spec in self.specs:
            if host_of(spec) == QUIET_FLOW:
                self.assertNotIn(f"Demo007_1<{spec.entry_name}>", after)
                registered = dict(after[f"{QUIET_FLOW}<{spec.entry_name}>"])
                self.assertEqual(registered, QUIET_EVENT_INFO)
                # The key that keeps the game running and the HUD up.
                self.assertIs(registered["is_pause_non_demo_member"], False)
                self.assertNotIn("demo_event", registered)
                continue
            metadata = after[f"Demo007_1<{spec.entry_name}>"]
            if spec.plan.host:
                # A trap that calls a cutscene: registered as the rest that calls it.
                self.assertEqual(oead.byml.to_text(metadata),
                                 oead.byml.to_text(before["Demo007_1<Demo007_1_Sub>"]))
                continue
            if not spec.quiet and any(m.kind.value in ("get_demo_actor", "champion_actor")
                                      for m in spec.plan.mutations):
                self.assertEqual([value["file"] for value in metadata["subfile"]],
                                 ["GetDemo.bfevfl"])
                metadata = oead.byml.Hash({
                    key: value for key, value in metadata.items()
                    if key != "subfile"})
            self.assertEqual(oead.byml.to_text(metadata), donor)

    def test_session_binding_requires_zero_ledger_and_guards_native_setter(self):
        token = 1492669680
        patched, changes = patch_session_binding(self.patched, token)
        graph = graph_snapshot(read_flow(patched))
        events = graph["events"]
        self.assertEqual(dict(graph["entry_points"])[BIND_ENTRY],
                         BIND_ENTRY + "_TokenZero")
        self.assertEqual(events[BIND_ENTRY + "_TokenZero"]["params"], {
            "GameDataIntName": "APSeedToken", "Value": 0,
            "Operator": "Equal"})
        self.assertEqual(events[BIND_ENTRY + "_TokenZero"]["cases"], {
            1: BIND_ENTRY + "_CursorZero", 0: BIND_ENTRY + "_Refused"})
        self.assertEqual(events[BIND_ENTRY + "_CursorZero"]["params"], {
            "GameDataIntName": "APReceivedCursor", "Value": 0,
            "Operator": "Equal"})
        path = [BIND_ENTRY + "_GuardON", BIND_ENTRY + "_WriteToken",
                BIND_ENTRY + "_GuardOFF"]
        for current, following in zip(path, path[1:]):
            self.assertEqual(events[current]["nxt"], following)
        self.assertEqual(events[path[0]]["actor_action"], "Demo_FlagON")
        self.assertEqual(events[path[1]]["actor_action"], "Demo_SetGameDataInt")
        self.assertEqual(events[path[1]]["params"], {
            "GameDataIntName": "APSeedToken", "Value": token,
            "IsWaitFinish": True})
        self.assertEqual(events[path[2]]["actor_action"], "Demo_FlagOFF")
        self.assertIsNone(events[path[2]]["nxt"])
        self.assertTrue(any("APBindSession" in change for change in changes))

        boot = oead.Sarc(unpack((SOURCE / "Pack/Bootup.pack").read_bytes()))
        raw = bytes(boot.get_file("Event/EventInfo.product.sbyml").data)
        registered, _ = patch_delivery_event_info(
            raw, self.specs, extra_entries=(BIND_ENTRY,))
        info = oead.byml.from_binary(unpack(registered))
        self.assertIn(f"Demo007_1<{BIND_ENTRY}>", info)

    def test_retarget_changes_only_existing_bind_literal(self):
        old_token, new_token = 1492669680, 1488534801
        source, _ = patch_session_binding(self.patched, old_token)
        before = graph_snapshot(read_flow(source))
        changed, _ = retarget_session_binding(source, old_token, new_token)
        after = graph_snapshot(read_flow(changed))
        write_name = BIND_ENTRY + "_WriteToken"
        self.assertEqual(after["events"][write_name]["params"]["Value"],
                         new_token)
        after["events"][write_name]["params"]["Value"] = old_token
        self.assertEqual(after, before)
        with self.assertRaisesRegex(ValueError, "audited layout"):
            retarget_session_binding(source, old_token + 1, new_token)


if __name__ == "__main__":
    unittest.main()
