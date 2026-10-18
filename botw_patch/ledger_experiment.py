"""Isolated persistence diagnostic, never part of a generated AP seed.

Cancel at a campfire toggles the two known diagnostic states using Nintendo's
setter. Other ledger values and all other choices retain vanilla behavior.
"""
from evfl.common import StringHolder
from evfl.container import Container
from evfl.event import ActionEvent, Event, SwitchEvent, SubFlowEvent
from evfl.util import make_rindex

from .events import graph_snapshot, read_flow, write_flow
from .resources import digest, vanilla_digest
from .resources import unpack
import oead

CAMPFIRE_HASH = "d82417a6f764234f1d647f492cadf0b5c6bf61c8f4ba97d6cac5a04b7cad5ade"
SAVED = {"APReceivedCursor": 1794, "APSeedToken": 1357911}
ZERO = dict.fromkeys(SAVED, 0)
DELIVERED = {"APReceivedCursor": 256, "APSeedToken": 1357912}
FOLLOWUP_DELIVERED = {"APReceivedCursor": 512, "APSeedToken": 1357912}
THIRD_DELIVERED = {"APReceivedCursor": 768, "APSeedToken": 1357912}
DELIVERY_ITEM = "Item_Fruit_A"
EVENT_INFO_HASH = "3b834dc21abe303f55673623946c92466347ebee755f27b556ef7a969488eede"


def patch_delivery_event_info(data):
    """Declare the new external flow for the entry that can reach it.

    This is separate from bfevfl links: EventInfo supplies loading metadata.
    Keep every other field/entry intact, including the campfire sub-entry.
    """
    if vanilla_digest(data) != EVENT_INFO_HASH:
        raise ValueError("unsupported vanilla EventInfo dependency metadata")
    info = oead.byml.from_binary(unpack(data))
    entry = info["Demo007_1<Demo007_1>"]
    if "subfile" not in entry:
        entry["subfile"] = oead.byml.Array()
    files = entry["subfile"]
    if not any(f["file"] == "GetDemo.bfevfl" for f in files):
        files.append(oead.byml.Hash({"file": "GetDemo.bfevfl"}))
    output = bytes(oead.byml.to_binary(info, big_endian=True))
    return bytes(oead.yaz0.compress(output)), ["Demo007_1<Demo007_1>: load GetDemo.bfevfl"]


def patch_campfire(data):
    if vanilla_digest(data) != CAMPFIRE_HASH:
        raise ValueError("unsupported vanilla campfire flow; no patch applied")
    flow = read_flow(data)
    chart = flow.flowchart
    events = {e.name: e for e in chart.events}
    choice = events["Event3"].data
    resume = events["Event76"]
    if not isinstance(choice, SwitchEvent) or choice.cases[3].v is not resume:
        raise ValueError("campfire cancel edge does not match")
    actor = next(a for a in chart.actors if str(a.identifier) == "EventSystemActor")
    action = StringHolder("Demo_SetGameDataInt")
    query = StringHolder("CheckGameDataInt")
    actor.actions.append(action)
    actor.queries.append(query)
    added = []

    def node(name, body, params):
        event = Event()
        event.name = "APLedger_" + name
        event.data = body
        body.actor = make_rindex(actor)
        body.params = Container()
        body.params.data = params
        chart.events.append(event)
        added.append(event.name)
        return event

    def set_pair(label, values):
        nxt = resume
        for name, value in reversed(list(values.items())):
            body = ActionEvent()
            body.actor_action = make_rindex(action)
            body.nxt = make_rindex(nxt)
            nxt = node(label + name, body, {"GameDataIntName": name,
                        "Value": value, "IsWaitFinish": True})
        return nxt

    def check(label, name, value, yes, no):
        body = SwitchEvent()
        body.actor_query = make_rindex(query)
        body.cases = {1: make_rindex(yes), 0: make_rindex(no)}
        return node(label, body, {"GameDataIntName": name,
                    "Value": value, "Operator": "Equal"})

    write_a = set_pair("SetA_", SAVED)
    write_zero = set_pair("Reset_", ZERO)
    a_cursor = check("IsACursor", "APReceivedCursor", SAVED["APReceivedCursor"], write_zero, resume)
    a_token = check("IsAToken", "APSeedToken", SAVED["APSeedToken"], a_cursor, resume)
    zero_cursor = check("IsZeroCursor", "APReceivedCursor", 0, write_a, resume)
    zero_token = check("IsZeroToken", "APSeedToken", 0, zero_cursor, a_token)
    choice.cases[3] = make_rindex(zero_token)
    return write_flow(flow), added


def patch_campfire_delivery(data):
    """One diagnostic item, then cursor commit; not an atomic delivery backend.

    The only accepted starting state is (0, 0). Already committed or foreign
    states are no-ops. GetDemo runs to completion before the ledger setters.
    """
    patched, _ = patch_campfire(data)
    flow = read_flow(patched)
    chart = flow.flowchart
    events = {event.name: event for event in chart.events}
    resume = events["Event76"]
    removed = {"APLedger_IsAToken", "APLedger_IsACursor"} | {
        "APLedger_Reset_" + name for name in SAVED}
    chart.events[:] = [event for event in chart.events if event.name not in removed]
    events["APLedger_IsZeroToken"].data.cases[0] = make_rindex(resume)
    for name, value in DELIVERED.items():
        events["APLedger_SetA_" + name].data.params.data["Value"] = value
    grant = Event()
    grant.name = "APLedger_DeliverApple"
    grant.data = SubFlowEvent()
    grant.data.res_flowchart_name = "GetDemo"
    grant.data.entry_point_name = "GetItemByName"
    grant.data.params = Container()
    grant.data.params.data = {"CheckTargetActorName": DELIVERY_ITEM, "IsInvalidOpenPouch": False}
    grant.data.nxt = make_rindex(events["APLedger_SetA_APReceivedCursor"])
    chart.events.append(grant)
    events["APLedger_IsZeroCursor"].data.cases[1] = make_rindex(grant)
    return write_flow(flow), [e.name for e in chart.events if e.name.startswith("APLedger_")]


def patch_campfire_guarded_delivery(data, guard_donor, *,
                                    start=None, committed=None,
                                    hold_frames=0):
    """Guard the diagnostic mutation/commit window against BOTW saves.

    This is a fault-injection candidate, not a proven transaction.  It uses
    the exact SaveProhibition actions found in vanilla OperationGuide, changes
    the fixed apple grant to the already validated direct action, and keeps
    the guard set until both ledger integers have been written.
    """
    start = dict(ZERO if start is None else start)
    committed = dict(DELIVERED if committed is None else committed)
    if set(start) != set(ZERO) or set(committed) != set(ZERO):
        raise ValueError("guarded delivery requires the two ledger fields")
    if not isinstance(hold_frames, int) or not 0 <= hold_frames <= 3600:
        raise ValueError("hold_frames must be between 0 and 3600")
    if vanilla_digest(data) == CAMPFIRE_HASH:
        patched, _ = patch_campfire_delivery(data)
    else:
        # build_delivery_control starts from one immutable build in which this
        # diagnostic graph already exists. Refuse any other modified shape.
        candidate = graph_snapshot(read_flow(data))["events"]
        grant = candidate.get("APLedger_DeliverApple", {})
        zero = candidate.get("APLedger_IsZeroCursor", {})
        if (grant.get("type") != "SubFlowEvent"
                or grant.get("res_flowchart_name") != "GetDemo"
                or grant.get("entry_point_name") != "GetItemByName"
                or grant.get("params") != {
                    "CheckTargetActorName": DELIVERY_ITEM,
                    "IsInvalidOpenPouch": False}
                or zero.get("cases", {}).get(1) != "APLedger_DeliverApple"):
            raise ValueError("unsupported prepatched delivery flow")
        patched = data
    flow = read_flow(patched)
    donor = read_flow(guard_donor)
    chart = flow.flowchart
    events = {event.name: event for event in chart.events}
    system = next(a for a in chart.actors
                  if str(a.identifier) == "EventSystemActor")
    events["APLedger_IsZeroToken"].data.params.data["Value"] = start["APSeedToken"]
    events["APLedger_IsZeroCursor"].data.params.data["Value"] = start["APReceivedCursor"]
    for name, value in committed.items():
        events["APLedger_SetA_" + name].data.params.data["Value"] = value

    templates = {}
    for event in donor.flowchart.events:
        body = event.data
        if (isinstance(body, ActionEvent)
                and str(body.actor.v.identifier) == "EventSystemActor"
                and body.params.data == {
                    "FlagName": "SaveProhibition", "IsWaitFinish": True}):
            command = str(body.actor_action.v)
            if command in ("Demo_FlagON", "Demo_FlagOFF"):
                templates.setdefault(command, event)
    if set(templates) != {"Demo_FlagON", "Demo_FlagOFF"}:
        raise ValueError("vanilla SaveProhibition guard donor unavailable")

    commands = ["Demo_SetItemDataToPouch", "Demo_FlagON", "Demo_FlagOFF"]
    if hold_frames:
        commands.append("Demo_WaitFrame")
    for command in commands:
        if not any(str(action) == command for action in system.actions):
            system.actions.append(StringHolder(command))

    grant = events["APLedger_DeliverApple"]
    grant.data = ActionEvent()
    grant.data.actor = make_rindex(system)
    grant.data.actor_action = make_rindex(next(
        action for action in system.actions
        if str(action) == "Demo_SetItemDataToPouch"))
    grant.data.params = Container()
    grant.data.params.data = {
        "IsWaitFinish": False, "TargetActorName": DELIVERY_ITEM}
    after_grant = events["APLedger_SetA_APReceivedCursor"]
    if hold_frames:
        hold = Event()
        hold.name = "APLedger_FaultWindow"
        hold.data = ActionEvent()
        hold.data.actor = make_rindex(system)
        hold.data.actor_action = make_rindex(next(
            action for action in system.actions
            if str(action) == "Demo_WaitFrame"))
        hold.data.params = Container()
        hold.data.params.data = {
            "Frame": hold_frames, "IsWaitFinish": True}
        hold.data.nxt = make_rindex(after_grant)
        chart.events.append(hold)
        after_grant = hold
    grant.data.nxt = make_rindex(after_grant)

    def guard(name, command, nxt):
        event = Event()
        event.name = name
        event.data = ActionEvent()
        event.data.actor = make_rindex(system)
        event.data.actor_action = make_rindex(next(
            action for action in system.actions if str(action) == command))
        event.data.params = Container()
        event.data.params.data = dict(templates[command].data.params.data)
        event.data.nxt = make_rindex(nxt)
        chart.events.append(event)
        return event

    guard_off = guard("APLedger_SaveGuardOFF", "Demo_FlagOFF", events["Event76"])
    events["APLedger_SetA_APSeedToken"].data.nxt = make_rindex(guard_off)
    guard_on = guard("APLedger_SaveGuardON", "Demo_FlagON", grant)
    events["APLedger_IsZeroCursor"].data.cases[1] = make_rindex(guard_on)
    return write_flow(flow), [
        "vanilla SaveProhibition ON before fixed diagnostic grant",
        "cursor and seed setters before SaveProhibition OFF",
        "direct Demo_SetItemDataToPouch(Item_Fruit_A); transaction unproven",
        *( [f"fault window {hold_frames} frames after grant"]
           if hold_frames else []),
    ]


def patch_campfire_capacity_delivery(data, guard_donor, capacity_donor,
                                     full_donor, *, count=1):
    """Preflight one guarded follow-up with the vanilla pouch-capacity query."""
    guarded, _ = patch_campfire_guarded_delivery(
        data, guard_donor, start=FOLLOWUP_DELIVERED,
        committed=THIRD_DELIVERED)
    flow = read_flow(guarded)
    donor = graph_snapshot(read_flow(capacity_donor))["events"]
    candidates = [node for node in donor.values()
                  if node.get("actor_query") == "CheckAddPorchItem"
                  and node.get("params") == {
                      "Count": 1,
                      "PorchItemName": ("Argument", "Arg_CurrentActorName")}]
    full_graph = graph_snapshot(read_flow(full_donor))["events"]
    full_candidates = [node for node in full_graph.values()
                       if node.get("actor_action") == "Demo_AppearFullPouchInfo"
                       and node.get("params") == {
                           "IsWaitFinish": True,
                           "PorchItemName": ("Argument", "PorchItemName")}]
    if not candidates or not full_candidates:
        raise ValueError("vanilla pouch-capacity donors unavailable")
    if not isinstance(count, int) or not 1 <= count <= 999:
        raise ValueError("capacity count must be between 1 and 999")

    chart = flow.flowchart
    events = {event.name: event for event in chart.events}
    system = next(actor for actor in chart.actors
                  if str(actor.identifier) == "EventSystemActor")
    for collection, command in ((system.queries, "CheckAddPorchItem"),
                                (system.actions, "Demo_AppearFullPouchInfo")):
        if not any(str(entry) == command for entry in collection):
            collection.append(StringHolder(command))

    full = Event()
    full.name = "APLedger_InventoryFull"
    full.data = ActionEvent()
    full.data.actor = make_rindex(system)
    full.data.actor_action = make_rindex(next(
        action for action in system.actions
        if str(action) == "Demo_AppearFullPouchInfo"))
    full.data.params = Container()
    full.data.params.data = {
        "IsWaitFinish": True, "PorchItemName": DELIVERY_ITEM}
    full.data.nxt = make_rindex(events["Event76"])
    chart.events.append(full)

    capacity = Event()
    capacity.name = "APLedger_CheckCapacity"
    capacity.data = SwitchEvent()
    capacity.data.actor = make_rindex(system)
    capacity.data.actor_query = make_rindex(next(
        query for query in system.queries
        if str(query) == "CheckAddPorchItem"))
    capacity.data.params = Container()
    capacity.data.params.data = {
        "Count": count, "PorchItemName": DELIVERY_ITEM}
    capacity.data.cases = {
        1: make_rindex(events["APLedger_SaveGuardON"]),
        0: make_rindex(full),
    }
    chart.events.append(capacity)
    events["APLedger_IsZeroCursor"].data.cases[1] = make_rindex(capacity)
    return write_flow(flow), [
        f"CheckAddPorchItem({DELIVERY_ITEM}, {count}) before save guard",
        "capacity false shows vanilla full-pouch info; grant/cursor untouched",
    ]
