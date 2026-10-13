"""Traps: the entries (botw_patch/traps.py), their delivery, and what the client says."""
import json
import os
from pathlib import Path
import re
from types import SimpleNamespace
import tempfile
import unittest

import oead

from botw_client.backend import DeliveryCommand, DeliveryCoordinator
from botw_client.delivery_plan import MutationKind
from botw_client.items import load_item_map
from botw_client.native_delivery import NativeDeliveryCatalog
from botw_patch import death_link, traps
from botw_patch.delivery_flow import (
    QUIET_EVENT_INFO, QUIET_FLOW, compile_native_entries, delivery_catalog, host_of,
    patch_delivery_flow)
from botw_patch.events import graph_snapshot, read_flow
from botw_patch.melee_weapons import MASTER_SWORD, MELEE_WEAPONS
from botw_patch.resources import unpack
from botw_patch.shop_items import read_labels
from botw_client.runtime import BotwClientRuntime
from tests.test_native_delivery_backend import _RuntimeBackend

CONTENT = Path(os.environ.get("BOTW_TEST_CONTENT", str(
    Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content")))
ROOT = Path(__file__).resolve().parents[1]
needs_game = unittest.skipUnless((CONTENT / "Pack/TitleBG.pack").is_file(),
                                 "Wii U update dump absent")


def member(name):
    title = oead.Sarc(unpack((CONTENT / "Pack/TitleBG.pack").read_bytes()))
    return bytes(title.get_file(f"EventFlow/{name}.bfevfl").data)


def walk(snapshot, entry, answer):
    """The actions an entry performs, [(action, params)], its queries answered by
    answer(query, params) -> case. Sub-flows are followed."""
    events = snapshot["events"]
    done = []
    name = dict(snapshot["entry_points"])[entry]
    while name is not None:
        node = events[name]
        if node["type"] == "ActionEvent":
            done.append((node["actor_action"], node["params"]))
        elif node["type"] == "SwitchEvent":
            name = node["cases"].get(answer(node["actor_query"], node["params"]))
            continue
        elif node["type"] == "SubFlowEvent":
            done.extend(walk(snapshot, node["entry_point_name"], answer))
        else:
            raise AssertionError(node["type"])
        name = node["nxt"]
    return done


class DataTests(unittest.TestCase):
    def test_every_trap_item_has_one_entry_and_one_item_map_row(self):
        mapping = load_item_map()
        items = json.loads((ROOT / "botw_world/data/items.json").read_text(encoding="utf-8"))
        flagged = {row["name"] for row in items if row.get("trap")}
        native = {name for name, entry in mapping.items()
                  if entry["delivery"]["kind"] == "native_trap"}
        self.assertEqual(native, {"Cucco Swarm", "Downpour", "Yiga Ambush", "Paranoia"})
        self.assertEqual(flagged, {trap.item for trap in traps.TRAPS} | native)
        for trap in traps.TRAPS:
            delivery = mapping[trap.item]["delivery"]
            self.assertEqual((delivery["kind"], delivery["entry"]), ("trap", trap.entry))
            self.assertTrue(delivery["text"])
        self.assertEqual(len({trap.entry for trap in traps.TRAPS}), len(traps.TRAPS))

    def test_a_trap_item_is_hosted_quietly_and_its_twin_is_spent(self):
        entries, unsupported = compile_native_entries()
        self.assertEqual(unsupported, {})
        for trap in traps.TRAPS:
            live, twin = [e for e in entries if e.item_name == trap.item]
            self.assertEqual((live.quiet, twin.quiet), (False, True))
            self.assertEqual([m.kind for m in live.plan.mutations], [MutationKind.TRAP])
            self.assertEqual([m.kind for m in twin.plan.mutations], [MutationKind.TRAP_SPENT])
            # The Blood Moon in the demo that calls its cutscene; every twin quietly.
            self.assertEqual((host_of(live), host_of(twin)), (trap.host, QUIET_FLOW))
            self.assertEqual(live.cursor_delta, 256)
        step = delivery_catalog()["items"]["Rupoor"]["variants"]["default"][0]
        self.assertEqual(step["flow"], QUIET_FLOW)
        self.assertEqual(step["quiet_flow"], QUIET_FLOW)
        self.assertEqual(step["mutations"][0]["target"], "APTrapRupoor")

    def test_the_client_resolves_a_trap_from_the_catalog(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps(delivery_catalog()), encoding="utf-8")
            catalog = NativeDeliveryCatalog(path)
            for trap in traps.TRAPS:
                (step,) = catalog.steps(trap.item)
                flow, resolved = catalog.resolve(
                    DeliveryCommand("seed", 1, 7, trap.item, step=0, step_count=1))
                self.assertEqual((resolved.get("flow", flow), resolved["quiet_flow"]),
                                 (trap.host, QUIET_FLOW))
                self.assertEqual(resolved["quiet_entry"], resolved["entry"] + "Q")
                self.assertEqual([m["kind"] for m in step["mutations"]], ["trap"])

    def test_the_equipment_parameters_are_the_games_own(self):
        # The keys of a vanilla Demo_SwitchPlayerEquipment (ShieldofKolog, Demo205_1).
        params = traps.equipment("Weapon", "Shield", "Bow")
        self.assertEqual(len(params), 14)
        self.assertEqual({k for k, v in params.items() if v is True}, {
            "IsWaitFinish", "UnequipWeapon", "UnequipShield", "UnequipBow"})
        self.assertEqual({v for k, v in params.items() if k.startswith("PorchItemName")}, {""})
        with self.assertRaises(ValueError):
            traps.equipment("Cape")


@needs_game
class MeleeWeaponTests(unittest.TestCase):
    def test_the_list_is_every_named_melee_weapon_but_the_master_sword(self):
        pack = oead.Sarc(unpack((CONTENT / death_link.MESSAGES).read_bytes()))
        messages = oead.Sarc(unpack(bytes(pack.get_file(death_link.MESSAGE_ARCHIVE).data)))
        named = set()
        for kind in ("WeaponSmallSword", "WeaponLargeSword", "WeaponSpear"):
            for label in read_labels(bytes(messages.get_file(f"ActorType/{kind}.msbt").data)):
                found = re.fullmatch(r"(Weapon_(?:Sword|Lsword|Spear)_\d+)_Name", label)
                if found:
                    named.add(found.group(1))
        self.assertEqual(set(MELEE_WEAPONS), named - set(MASTER_SWORD))
        self.assertEqual(len(MELEE_WEAPONS), len(set(MELEE_WEAPONS)))
        self.assertTrue(set(MASTER_SWORD) <= named)

    def test_every_weapon_is_an_actor_of_the_game(self):
        packs = {path.stem for path in (CONTENT / "Actor/Pack").glob("Weapon_*.sbactorpack")}
        self.assertEqual(set(MELEE_WEAPONS) - packs, set())


@needs_game
class EntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = {host: member(host) for host in (QUIET_FLOW, "Demo007_1")}
        cls.out = {host: traps.add_entries(raw, host)[0] for host, raw in cls.raw.items()}
        cls.graphs = {host: graph_snapshot(read_flow(out)) for host, out in cls.out.items()}
        cls.graph = cls.graphs[QUIET_FLOW]

    def walk(self, trap, **state):
        def answer(query, params):
            if query == "CheckRupee":
                return int(state["rupees"] >= params["Value"])
            if query == "ComparePlayerHeart":
                return int(state["hearts"] >= params["Threshold"])
            if query == "CheckEquipment":
                return int(state["weapon"] == params["EquipItemName"])
            if query == "CheckFlag":
                assert params == {"FlagName": "BloodyMoonProhibition"}
                return int(state["prohibited"])
            if query == "IsCurrentMainFieldStage":
                return int(state["main_field"])
            raise AssertionError(query)
        found = next(t for t in traps.TRAPS if t.item == trap)
        return walk(self.graphs[found.host], found.entry, answer)

    def test_the_vanilla_graph_is_untouched_and_every_entry_is_added(self):
        for host, raw in self.raw.items():
            before = graph_snapshot(read_flow(raw))
            graph = self.graphs[host]
            for name, node in before["events"].items():
                self.assertEqual(graph["events"][name], node)
            names = [name for name, _ in graph["entry_points"][len(before["entry_points"]):]]
            self.assertEqual(names, [trap.entry for trap in traps.TRAPS if trap.host == host])
            with self.assertRaises(ValueError):
                traps.add_entries(self.out[host], host)
        self.assertEqual([t.item for t in traps.TRAPS if t.host == "Demo007_1"], ["Blood Moon"])

    def test_weapon_shatter_deletes_the_weapon_in_hand_and_unequips_the_slot(self):
        unequip = ("Demo_SwitchPlayerEquipment", traps.equipment("Weapon"))
        for weapon in (MELEE_WEAPONS[0], "Weapon_Lsword_057", MELEE_WEAPONS[-1]):
            self.assertEqual(self.walk("Weapon Shatter", weapon=weapon), [
                ("Demo_DeletePorchItemInEquip",
                 {"IsWaitFinish": True, "DeleteNum": 1, "PorchItemName": weapon}), unequip])
        # Empty hands, the Master Sword, a shield: nothing happens.
        for held in (None, *MASTER_SWORD, "Weapon_Shield_001"):
            self.assertEqual(self.walk("Weapon Shatter", weapon=held), [])

    def test_blood_moon_calls_the_cutscene_at_once_where_the_game_allows_it(self):
        self.assertEqual(self.walk("Blood Moon", prohibited=False, main_field=True), [
            ("Demo_SetGameDataFloat", {"GameDataFloatName": "WM_BloodyMoonTimer", "Value": 0.0,
                                       "IsWaitFinish": True}),
            ("Demo_CallDemo", {"DemoName": "Demo011_0", "EntryPointName": "Demo011_0",
                               "IsWaitFinish": True, "EndFade": 0})])

    def test_blood_moon_is_scheduled_for_midnight_where_the_game_would_not_allow_it(self):
        scheduled = [
            ("Demo_SetGameDataInt", {"GameDataIntName": "WM_bloodyEndReserveTimer", "Value": 0,
                                     "IsWaitFinish": True}),
            ("Demo_FlagON", {"FlagName": "WM_BloodyDay", "IsWaitFinish": True})]
        for prohibited, main_field in ((True, True), (False, False), (True, False)):
            self.assertEqual(self.walk("Blood Moon", prohibited=prohibited, main_field=main_field),
                             scheduled)

    def test_rupoor_takes_the_largest_step_the_purse_holds(self):
        for rupees, taken in ((0, 0), (1, 1), (4, 1), (5, 5), (19, 10), (20, 20), (99, 50),
                              (100, 100), (5000, 100)):
            done = self.walk("Rupoor", rupees=rupees)
            self.assertEqual(done, [("Demo_IncreaseRupee", {"Value": -taken, "IsWaitFinish": False})]
                             if taken else [], rupees)

    def test_hearts_down_never_kills_and_takes_two_hearts_when_it_can(self):
        for hearts in range(1, 161):
            done = self.walk("Hearts Down", hearts=hearts)
            taken = sum(params["Value"] for _, params in done)
            self.assertEqual(taken, min(traps.HEARTS_DOWN, hearts - 1), hearts)
            self.assertLess(taken, hearts)
            self.assertTrue(all(action == "Demo_ApplyDamage" for action, _ in done))
        player = [node for node in self.graph["events"].values()
                  if node.get("actor_action") == "Demo_ApplyDamage"]
        self.assertEqual({node["actor"] for node in player}, {"GameROMPlayer"})

    def test_strip_down_unequips_every_slot(self):
        self.assertEqual(self.walk("Strip Down"), [
            ("Demo_SwitchPlayerEquipment", traps.equipment(*traps.EQUIPMENT_SLOTS))])

    def test_the_entries_are_background_events_but_the_blood_moon_a_rest(self):
        boot = oead.Sarc(unpack((CONTENT / "Pack/Bootup.pack").read_bytes()))
        raw = bytes(boot.get_file(traps.EVENT_INFO).data)
        out, _ = traps.add_event_info(raw)
        info = oead.byml.from_binary(unpack(out))
        for trap in traps.TRAPS:
            if trap.host == QUIET_FLOW:
                self.assertEqual(dict(info[f"OperationGuide<{trap.entry}>"]), QUIET_EVENT_INFO)
        rest = info["Demo007_1<APTrapBloodMoon>"]
        self.assertEqual(oead.byml.to_text(rest), oead.byml.to_text(info[traps.DEMO_HOST_INFO]))
        self.assertEqual([dict(c)["entry"] for c in rest["child"]],
                         ["Demo011_0", "Demo165_4", "Demo165_5"])
        with self.assertRaises(ValueError):
            traps.add_event_info(out)


@needs_game
class DeliveryEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        donors = (member("OperationGuide"), member("Demo002_0"), member("GetDemo"),
                  member("GetDemo"), member("Demo017_0"))
        cls.events = {}
        for host, quiet in ((QUIET_FLOW, True), ("Demo007_1", False)):
            with_traps, _ = traps.add_entries(member(host), host)
            out, _ = patch_delivery_flow(with_traps, *donors, quiet=quiet)
            cls.events.update(graph_snapshot(read_flow(out))["events"])
        cls.specs, _ = compile_native_entries()

    def chain(self, entry):
        names, name = [], entry + "_GuardON"
        while name is not None:
            names.append(name)
            name = self.events[name]["nxt"]
        return names

    def test_a_trap_strikes_once_its_delivery_is_committed(self):
        for item, entry in (("Rupoor", "APTrapRupoor"), ("Blood Moon", "APTrapBloodMoon")):
            spec = next(s for s in self.specs if s.item_name == item and not s.quiet)
            stem = spec.entry_name
            self.assertEqual(self.chain(stem), [stem + "_GuardON", stem + "_Commit",
                                                stem + "_GuardOFF", stem + "_Mut0"])
            call = self.events[stem + "_Mut0"]
            self.assertEqual((call["type"], call["res_flowchart_name"], call["entry_point_name"]),
                             ("SubFlowEvent", "", entry))
            self.assertEqual(self.events[stem + "_Commit"]["params"]["Value"], 256)

    def test_a_trap_given_back_is_spent_without_effect(self):
        for item in ("Rupoor", "Blood Moon"):
            spec = next(s for s in self.specs if s.item_name == item and s.quiet)
            stem = spec.entry_name
            self.assertEqual(self.chain(stem), [stem + "_GuardON", stem + "_Commit",
                                                stem + "_GuardOFF"])

    def test_a_trap_without_its_entry_is_refused(self):
        with self.assertRaisesRegex(ValueError, "trap entry missing"):
            patch_delivery_flow(member("OperationGuide"), member("OperationGuide"),
                                member("Demo002_0"), member("GetDemo"), member("GetDemo"),
                                member("Demo017_0"), quiet=True)


class JournalTests(unittest.TestCase):
    def test_line(self):
        from botw_client.ap_journal import trap_line
        self.assertEqual(trap_line("Rupoor", "Rupees slip through your fingers."),
                         "{0}Rupoor{/}: Rupees slip through your fingers.")


class TrapRuntimeTests(unittest.IsolatedAsyncioTestCase):
    """A received trap: no window, the journal says what it did; given back after
    a reload, it is spent in silence."""

    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        game = SimpleNamespace(delivery_block_reason="", safe_for_delivery=lambda: True)
        self.runtime = BotwClientRuntime(
            "unused:1", "test", state_path=Path(self.temporary.name) / "state.json",
            game_factory=lambda: game, native_delivery=True, tip_factory=object,
            log=lambda _line: None)
        self.runtime._session_identity = ("seed", 0, 1, "checksum")
        self.runtime.state = self.runtime.state_store.select(*self.runtime._session_identity)
        self.runtime.ap = SimpleNamespace(
            items_synchronized=True, received_items={0: SimpleNamespace(item=10)},
            item_name=lambda item: "Rupoor")
        self.backend = _RuntimeBackend(0)
        step = {"step": 0, "quiet_entry": "APD_X_00Q", "mutations": [{
            "kind": "trap", "target": "APTrapRupoor",
            "value": "Rupees slip through your fingers."}]}
        self.backend.catalog.steps = lambda name, received_before=0: [step]
        self.runtime.deliveries = DeliveryCoordinator(self.backend)

    async def test_the_effect_is_told_once_it_has_struck(self):
        self.runtime._discover_received()
        await self.runtime._apply_one_received_native()
        self.assertFalse(self.backend.commands[0].quiet)
        self.assertEqual(self.runtime._journal_notes,
                         [("{0}Rupoor{/}: Rupees slip through your fingers.", None)])
        self.assertEqual(self.runtime.state.get("replay_batch", []), [])

    async def test_a_trap_given_back_says_nothing_and_is_not_listed(self):
        self.runtime.state["delivered_high"] = 5
        self.runtime._discover_received()
        await self.runtime._apply_one_received_native()
        self.assertTrue(self.backend.commands[0].quiet)
        self.assertEqual(self.runtime._journal_notes, [])
        self.assertEqual(self.runtime.state.get("replay_batch", []), [])

    async def test_a_native_trap_is_queued_for_the_client_once_committed(self):
        step = {"step": 0, "quiet_entry": "APD_Y_00Q", "mutations": [{
            "kind": "native_trap", "target": "cucco_swarm", "value": "The cuccos want revenge!"}]}
        self.backend.catalog.steps = lambda name, received_before=0: [step]
        self.runtime.ap.item_name = lambda item: "Cucco Swarm"
        self.runtime._discover_received()
        await self.runtime._apply_one_received_native()
        self.assertEqual(self.runtime._native_traps, ["cucco_swarm"])
        # Named once it has struck: its lines wait for the client to play it.
        self.assertEqual(self.runtime._journal_notes, [])
        self.assertEqual(self.runtime._native_trap_notes,
                         [["{0}Cucco Swarm{/}: The cuccos want revenge!"]])

    async def test_a_native_trap_is_named_once_it_has_struck(self):
        self.runtime._native_traps.append("downpour")
        self.runtime._native_trap_notes.append(["{2}Alice{/} sent {1}Downpour{/} to {2}Bob{/}",
                                                "{0}Downpour{/}: Dark clouds gather over Hyrule."])
        self.runtime.deliveries = SimpleNamespace(backend=SimpleNamespace(downpour=lambda kind, frames: True))
        await self.runtime._native_trap_tick()
        self.assertEqual([line for line, _tag in self.runtime._journal_notes],
                         ["{2}Alice{/} sent {1}Downpour{/} to {2}Bob{/}",
                          "{0}Downpour{/}: Dark clouds gather over Hyrule."])

    async def test_the_server_line_kept_for_the_trap_comes_with_its_effect(self):
        self.runtime._trap_lines[0] = "{2}Alice{/} sent {1}Rupoor{/} to {2}Bob{/}"
        self.runtime._discover_received()
        await self.runtime._apply_one_received_native()
        self.assertEqual(self.runtime._journal_notes,
                         [("{2}Alice{/} sent {1}Rupoor{/} to {2}Bob{/}", None),
                          ("{0}Rupoor{/}: Rupees slip through your fingers.", None)])
        self.assertEqual(self.runtime._trap_lines, {})

    async def test_nothing_announces_a_trap_before_it_strikes(self):
        self.runtime.tips = object()
        self.runtime.game.item_map = {"Rupoor": {"delivery": {"kind": "trap"}}}
        self.runtime._received_line = lambda index, item, wait=True: "{2}Alice{/} sent {1}Rupoor{/}"
        self.assertEqual(self.runtime._received_announcement(0), "skip")
        self.assertEqual(self.runtime._journal_notes, [])
        self.assertEqual(self.runtime._trap_lines, {0: "{2}Alice{/} sent {1}Rupoor{/}"})

    async def test_a_native_trap_given_back_is_not_played(self):
        step = {"step": 0, "quiet_entry": "APD_Y_00Q", "mutations": [{
            "kind": "native_trap", "target": "cucco_swarm", "value": "x"}]}
        self.backend.catalog.steps = lambda name, received_before=0: [step]
        self.runtime.state["delivered_high"] = 5
        self.runtime._discover_received()
        await self.runtime._apply_one_received_native()
        self.assertEqual(self.runtime._native_traps, [])

    async def test_a_trap_has_no_window_of_its_own_but_the_journal(self):
        self.assertIs(self.runtime._vanilla_window(0), True)


if __name__ == "__main__":
    unittest.main()
