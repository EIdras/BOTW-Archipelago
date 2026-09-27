"""Ablate only the external GetDemo call from the first failed delivery build."""
import json
import argparse
import copy
import oead
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path if Path(p).resolve() != ROOT / "tools"]
from botw_patch.events import read_flow, write_flow, wait_instead, graph_snapshot
from botw_patch.resources import ResourceBuilder, digest
from evfl.common import StringHolder
from evfl.util import make_rindex
from evfl.event import Event, ActionEvent
from evfl.container import Container

SOURCE = ROOT / ".build/ledger-validation/9fa8c98c1e172c8d"


def remove_external_call(raw):
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    grant = next(e for e in flow.flowchart.events if e.name == "APLedger_DeliverApple")
    node = before["events"][grant.name]
    if node.get("res_flowchart_name") != "GetDemo" or node.get("entry_point_name") != "GetItemByName":
        raise ValueError("unexpected diagnostic call")
    wait_instead(flow, grant)
    result = write_flow(flow)
    after = graph_snapshot(read_flow(result))
    # No other graph semantics, actor list or entry point may change.
    before["events"][grant.name] = after["events"][grant.name]
    if before != after:
        raise ValueError("control changed more than the selected call")
    return result, ["replace GetDemo call with Demo_WaitFrame(1); retain continuation"]


def direct_item_call(raw):
    control, _ = remove_external_call(raw)
    flow = read_flow(control)
    grant = next(e for e in flow.flowchart.events if e.name == "APLedger_DeliverApple")
    actor = grant.data.actor.v
    action = StringHolder("Demo_SetItemDataToPouch")
    actor.actions.append(action)
    grant.data.actor_action = make_rindex(action)
    # Exact native GetDemo::GetItemByName first action, with its literal input.
    grant.data.params.data = {"IsWaitFinish": False, "TargetActorName": "Item_Fruit_A"}
    return write_flow(flow), ["native Demo_SetItemDataToPouch(Item_Fruit_A), no external subflow"]


def guarded_delivery_call(raw, guard_donor, followup=False, fault=False):
    from botw_patch.ledger_experiment import (
        DELIVERED, FOLLOWUP_DELIVERED, patch_campfire_guarded_delivery)
    return patch_campfire_guarded_delivery(
        raw, guard_donor,
        start=DELIVERED if (followup or fault) else None,
        committed=FOLLOWUP_DELIVERED if (followup or fault) else None,
        hold_frames=1800 if fault else 0)


def capacity_delivery_call(raw, guard_donor, capacity_donor, full_donor):
    from botw_patch.ledger_experiment import patch_campfire_capacity_delivery
    return patch_campfire_capacity_delivery(
        raw, guard_donor, capacity_donor, full_donor, count=999)


def presentation_call(raw, close_message_donor=None):
    control, _ = remove_external_call(raw)
    flow = read_flow(control)
    chart = flow.flowchart
    chart.events[:] = [e for e in chart.events if not e.name.startswith("APLedger_")]
    events = {e.name: e for e in chart.events}
    system = next(a for a in chart.actors if str(a.identifier) == "EventSystemActor")
    sound = next(a for a in chart.actors if str(a.identifier) == "SoundTriggerTag")
    system.actions[:] = [a for a in system.actions if str(a) != "Demo_SetGameDataInt"]
    system.queries[:] = [q for q in system.queries if str(q) != "CheckGameDataInt"]
    show = StringHolder("Demo_OpenGetDemoDialog")
    system.actions.append(show)

    def action(name, actor, command, params, nxt):
        event = Event()
        event.name = name
        event.data = ActionEvent()
        event.data.actor = make_rindex(actor)
        event.data.actor_action = make_rindex(command)
        event.data.params = Container()
        event.data.params.data = params
        event.data.nxt = make_rindex(nxt)
        chart.events.append(event)
        return event

    dialog = action("APDisplay_Dialog", system, show, {
        "IsWaitFinish": True, "IsInvalidOpenPouch": False,
        "TargetActorName": "Item_Fruit_A", "UseLastTryGetItemName": False,
        "EnableMultiGet": False}, events["Event76"])
    play = action("APDisplay_Sound", sound,
                  next(a for a in sound.actions if str(a) == "Demo_SoundTrigger"),
                  {"SoundDelay": 0, "SLinkInst": "", "IsWaitFinish": False,
                   "Sound": "GetDemo_Standard"}, dialog)
    events["Event3"].data.cases[3] = make_rindex(play)
    if close_message_donor is not None:
        donor = read_flow(close_message_donor)
        template = next(e for e in donor.flowchart.events if e.name == "Event183")
        if (str(template.data.actor.v.identifier), str(template.data.actor_action.v)) != (
                "EventSystemActor[Temp]", "Demo_CloseMessageDialog"):
            raise ValueError("unexpected vanilla close-message action")
        temporary = copy.deepcopy(template.data.actor.v)
        close = copy.deepcopy(template)
        close.name = "APDisplay_CloseMessage"
        close.data.actor = make_rindex(temporary)
        close.data.actor_action = make_rindex(next(a for a in temporary.actions
                                                 if str(a) == "Demo_CloseMessageDialog"))
        close.data.nxt = make_rindex(dialog)
        chart.actors.append(temporary)
        chart.events.append(close)
        play.data.nxt = make_rindex(close)
    return write_flow(flow), ["native sound and dialog only; no inventory or ledger writes"]


def build(direct_item=False, presentation=False, close_message=False,
          guarded_delivery=False, guarded_fault=False,
          guarded_followup=False, guarded_capacity=False):
    guarded_delivery = (guarded_delivery or guarded_fault
                        or guarded_followup or guarded_capacity)
    presentation = presentation or close_message
    if sum(bool(value) for value in
           (direct_item, presentation, guarded_delivery)) > 1:
        raise ValueError("select a single diagnostic")
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    files = {}
    for name, expected in manifest["files"].items():
        path = (SOURCE / "content" / name).resolve()
        if not path.is_relative_to((SOURCE / "content").resolve()):
            raise ValueError("source file escapes build")
        raw = path.read_bytes()
        if digest(raw) != expected:
            raise ValueError(f"modified source build: {name}")
        files[name] = raw
    builder = ResourceBuilder(SOURCE / "content")
    donor = None
    guard_donor = None
    capacity_donor = None
    full_donor = None
    if close_message:
        archive = oead.Sarc(files["Pack/TitleBG.pack"])
        donor = bytes(archive.get_file("EventFlow/GetDemo.bfevfl").data)
        if digest(donor) != "af201d87d582f218ee5898ef3efa97f482fbd564e487385793b1efe7066817c8":
            raise ValueError("unsupported GetDemo donor")
    if guarded_delivery:
        archive = oead.Sarc(files["Pack/TitleBG.pack"])
        guard_donor = bytes(archive.get_file(
            "EventFlow/OperationGuide.bfevfl").data)
        if guarded_capacity:
            capacity_donor = bytes(archive.get_file(
                "EventFlow/Demo002_0.bfevfl").data)
            # The full-pouch action donor is in GetDemo; combine the two
            # verified flows only for donor validation.
            full_donor = bytes(archive.get_file(
                "EventFlow/GetDemo.bfevfl").data)
    builder.patch_archive("Pack/TitleBG.pack", {"EventFlow/Demo007_1.bfevfl":
                           (lambda raw: presentation_call(raw, donor)) if presentation else
                           (lambda raw: capacity_delivery_call(
                               raw, guard_donor, capacity_donor,
                               full_donor)) if guarded_capacity else
                           (lambda raw: guarded_delivery_call(
                               raw, guard_donor, guarded_followup,
                               guarded_fault)) if guarded_delivery else
                           direct_item_call if direct_item else remove_external_call})
    files.update(builder.finish())
    hashes = {name: digest(raw) for name, raw in sorted(files.items())}
    target = SOURCE.parent / digest(json.dumps(hashes, sort_keys=True).encode())[:16]
    for name, raw in files.items():
        path = target / "content" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("immutable build modified")
        path.write_bytes(raw)
    (target / "rules.txt").write_text((SOURCE / "rules.txt").read_text(), encoding="utf-8")
    (target / "manifest.json").write_text(json.dumps({
        "schema": 1, "status": "experiment", "startup_control": not (direct_item or presentation),
        "direct_item_diagnostic": direct_item,
        "presentation_diagnostic": presentation,
        "guarded_delivery_diagnostic": guarded_delivery,
        "guarded_fault_injection": guarded_fault,
        "guarded_followup": guarded_followup,
        "guarded_capacity": guarded_capacity,
        "capacity_probe_count": 999 if guarded_capacity else None,
        "expected_start": ({"APReceivedCursor": 256, "APSeedToken": 1357912}
                           if (guarded_fault or guarded_followup) else
                           {"APReceivedCursor": 512, "APSeedToken": 1357912}
                           if guarded_capacity else None),
        "expected_commit": ({"APReceivedCursor": 512, "APSeedToken": 1357912}
                            if (guarded_fault or guarded_followup) else
                            {"APReceivedCursor": 768, "APSeedToken": 1357912}
                            if guarded_capacity else None),
        "fault_window_frames": 1800 if guarded_fault else 0,
        "save_guard": "unvalidated" if guarded_delivery else None,
        "close_previous_message": close_message,
        "source_build": SOURCE.name, "files": hashes, "changes": builder.changes,
        "delivery_diagnostic": False, "save_transaction": False,
    }, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--direct-item", action="store_true")
    parser.add_argument("--presentation", action="store_true")
    parser.add_argument("--close-message", action="store_true")
    parser.add_argument("--guarded-delivery", action="store_true")
    parser.add_argument("--guarded-fault", action="store_true")
    parser.add_argument("--guarded-followup", action="store_true")
    parser.add_argument("--guarded-capacity", action="store_true")
    args = parser.parse_args()
    build(args.direct_item, args.presentation, args.close_message,
          args.guarded_delivery, args.guarded_fault,
          args.guarded_followup, args.guarded_capacity)
