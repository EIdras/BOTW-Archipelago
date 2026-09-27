"""Generate guarded EventFlow entries from the AP delivery map.

The generated entries are deliberately small: one entry performs one resumable
delivery step.  The companion owns session/index validation and invokes an
entry only after observing the exact packed cursor it expects.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import copy
import zlib

import oead
from evfl.actor import Actor, ActorIdentifier
from evfl.common import StringHolder
from evfl.container import Container
from evfl.entry_point import EntryPoint
from evfl.event import ActionEvent, Event, SubFlowEvent, SwitchEvent
from evfl.util import Index, make_rindex

from botw_client.delivery_plan import (
    DeliveryMutation, DeliveryStep, ItemDeliveryPlan, MutationKind, compile_delivery_plan)
from botw_client.items import load_item_map
from .events import graph_snapshot, read_flow, write_flow
from .resources import unpack


FLOW_NAME = "Demo007_1"
# The silent twins (items given back after a reload, without the game's
# window) have their own host and EventInfo, so that giving back does not
# pause the game nor hide the HUD (Simon, 25-26/09):
#   * what paused the game and blinked the HUD was the EventInfo key
#     is_pause_non_demo_member: absent, an event pauses whatever does not take
#     part in it. The game's own background events set it to False (e.g.
#     Npc_King_Vagrant001<Near>); so do ours (QUIET_EVENT_INFO). Measured with
#     no-op probes and the request trace (console /ap-evt): with the key, no
#     blink; without it, a blink whatever the request's flags (0xf demo,
#     0x64 default, 0x19a Near, 0x1fe Background);
#   * their host is the resident OperationGuide, appended to as Demo007_1 is
#     (its own entries untouched). A flowchart whose name starts with "Demo"
#     gets the demo request flags (zeldaret/botw evtMetadata.cpp initFlags_),
#     and a new EventFlow/APDelivery.bfevfl added to TitleBG.pack was
#     accepted and never ran: an added file is not found as the resident
#     flowcharts are. Demo007_1 with the key was not tried.
QUIET_FLOW = "OperationGuide"
QUIET_EVENT_INFO = {"disable_event_start_interval": True,
                    "is_pause_non_demo_member": False,
                    "is_timeline": False, "mode": "Seamless"}
CURSOR_FLAG = "APReceivedCursor"
REJECT_COUNTER = "APDeliveryRejectCounter"
# The rune terminal's presentation, as Demo003_0 plays it (Item01..04), one
# after the other: IsDownloadDemo on, the download screen, 70 frames on a
# second system actor, the Slate's "Le module est activé.", the menu closed,
# the rune's flag, then Link puts the Slate away (Demo041_0<SheikPadSetOff>,
# its player part: SheikPadSetOff then DemoWait) and 20 frames. Measured on
# the vanilla terminal (11a, 20260926T184407.328329Z): the menu consumes
# IsDownloadDemo as it opens, runs its download states and hands back the
# screen action on its own. Without SheikPadSetOff, Link stays in the pose
# the menu left him in, without control (26/09).
#
# The download screen needs the pause menu built at once, which the game does
# only with the map at rest (botw_client/pause_menu.py). The map rests while
# the HUD is hidden, some frames into an event; the terminal opens the screen
# after 20 s of cinematic, ours waits DOWNLOAD_SETTLE frames (measured
# 26/09: the map rests about 0.1 s after the HUD hides, 60 ms in the
# validated run; 30 frames worked but showed as a pause, Simon).
DOWNLOAD_FLAG = "IsDownloadDemo"
DOWNLOAD_SETTLE = 10
DOWNLOAD_WAIT = 70
PLAYER = ("GameROMPlayer", "")
PLAYER_PARAMS = {"CreateMode": 0, "IsGrounding": False, "IsWorld": False, "PosX": 0.0,
                 "PosY": 0.0, "PosZ": 0.0, "RotX": 0.0, "RotY": 0.0, "RotZ": 0.0,
                 "Weapon": "", "DisableWeapon": False, "Shield": "", "DisableShield": False,
                 "Bow": "", "DisableBow": False, "ArmorHead": "", "ArmorUpper": "",
                 "ArmorLower": "", "DisableSheikPad": False}
SLATE_AWAY = {"IsWaitFinish": True, "ASName": "SheikPadSetOff", "IsIgnoreSame": False,
              "IsEnabledAnimeDriven": -1, "IsOneTimeEndKeep": True, "TargetIndex": -1,
              "SeqBank": 0, "ClothWarpMode": 1, "MorphingFrame": -1.0, "NoErrorCheck": False}
DEMO_WAIT = {"IsIgnoreSame": True, "IsEnabledAnimeDriven": -1, "ASName": "DemoWait",
             "IsWaitFinish": False, "TargetIndex": -1, "SeqBank": 0, "MorphingFrame": -1.0,
             "IsOneTimeEndKeep": True, "NoErrorCheck": False, "ClothWarpMode": -1}
AFTER_SLATE = 20
ACTOR_PARAMS = {"CreateMode": 0, "IsGrounding": False, "IsWorld": False, "PosX": 0.0,
                "PosY": 0.0, "PosZ": 0.0, "RotX": 0.0, "RotY": 0.0, "RotZ": 0.0}
SLATE_WAITER = ("EventSystemActor", "01")
SLATE_VOICE = ("NPC_DRCVoice", "")
SLATE_VOICE_PARAMS = {"IsGrounding": False, "IsWorld": False, "PosX": 0.0, "PosY": 0.0,
                      "PosZ": 0.0, "RotX": 0.0, "RotY": 0.0, "RotZ": 0.0, "CreateMode": 1}
SLATE_MESSAGE = {"IsCloseMessageDialog": True, "IsWaitFinish": True, "ASName": "",
                 "IsOverWriteLabelActorName": False, "CloseDialogOption": 0,
                 "MessageOpenDelayTime": 0, "IsWaitAS": False, "IsBecomingSpeaker": True,
                 "MessageId": "DemoMsg/Demo003_0:Demo003_0_Text005"}
BIND_ENTRY = "APBindSession"


@dataclass(frozen=True)
class NativeDeliveryEntry:
    item_name: str
    entry_name: str
    step: int
    step_count: int
    cursor_delta: int
    plan: DeliveryStep
    progressive_tier: int | None = None
    # The silent twin of a step that shows the game's get window: used to
    # give back items a reloaded save lost, under one AP summary instead of
    # one window per item (Simon, 25/09).
    quiet: bool = False


# Rupees of a GetDemo rupee actor, given silently by Demo_IncreaseRupee.
RUPEE_VALUES = {"PutRupee": 1, "PutRupee_Blue": 5, "PutRupee_Red": 20,
                "PutRupee_Purple": 50, "PutRupee_Silver": 100, "PutRupee_Gold": 300}


def quiet_step(plan: DeliveryStep) -> DeliveryStep | None:
    """The same step without the game's get window, when there is one: pouch
    items granted directly, champion powers without their window (the 9w
    chain), rupees by the game's own Demo_IncreaseRupee (a bare GameData
    counter write failed in 7h; this is the action quests use). Hearts and
    stamina have no silent delivery. A rune's twin sets its flag only."""
    if any(m.kind is MutationKind.RUNE_DOWNLOAD for m in plan.mutations):
        return replace(plan, mutations=tuple(
            DeliveryMutation(MutationKind.SET_BOOL, m.target, True, value_type="bool")
            if m.kind is MutationKind.RUNE_DOWNLOAD else m for m in plan.mutations))
    rupees = [m for m in plan.mutations if m.kind is MutationKind.GET_DEMO_ACTOR
              and m.target in RUPEE_VALUES]
    if rupees and len(plan.mutations) == 1:
        return replace(plan, mutations=(replace(
            rupees[0], kind=MutationKind.INCREASE_RUPEE,
            value=RUPEE_VALUES[rupees[0].target]),))
    if not plan.capacity_actor and not any(
            m.kind is MutationKind.CHAMPION_ACTOR for m in plan.mutations):
        return None
    if not any(m.kind in (MutationKind.GET_DEMO_ACTOR, MutationKind.CHAMPION_ACTOR)
               for m in plan.mutations):
        return None
    return replace(plan, mutations=tuple(
        replace(m, kind=MutationKind.GRANT_ACTOR) if m.kind is MutationKind.GET_DEMO_ACTOR
        else m for m in plan.mutations))


def shows_window(plan: DeliveryStep) -> bool:
    """The step opens the game's window (GetDemo, champion powers, the rune
    download screen)."""
    return any(m.kind in (MutationKind.GET_DEMO_ACTOR, MutationKind.CHAMPION_ACTOR,
                          MutationKind.RUNE_DOWNLOAD)
               for m in plan.mutations)


def host_of(entry: NativeDeliveryEntry) -> str:
    """Demo007_1 for a step that opens the game's window, QUIET_FLOW for all
    others: the silent twins, and the steps with no window of their own
    (Sheikah Sensor, horse gear), which would pause the game and blink the
    HUD in Demo007_1 for nothing to show (seen with runes, Simon, 26/09)."""
    return QUIET_FLOW if entry.quiet or not shows_window(entry.plan) else FLOW_NAME


def _entry_stem(item_name: str, progressive_tier: int | None) -> str:
    identity = item_name if progressive_tier is None else (
        f"{item_name}\0tier={progressive_tier}")
    return f"APD_{zlib.crc32(identity.encode('utf-8')) & 0xffffffff:08X}"


def _cursor_delta(step: int, step_count: int) -> int:
    if step + 1 < step_count:
        return 1
    return 0x100 - step


def compile_native_entries(mapping=None) -> tuple[list[NativeDeliveryEntry], dict[str, str]]:
    """Compile the action families supported by verified vanilla commands.

    Pouch actors, boolean flags and the vanilla GetDemo specialized path are
    supported. Bare counters remain rejected: test 7h proved that changing a
    related GameData value can commit without delivering the gameplay item.
    """
    mapping = load_item_map() if mapping is None else mapping
    entries: list[NativeDeliveryEntry] = []
    unsupported: dict[str, str] = {}
    for item_name in sorted(mapping):
        kind = mapping[item_name]["delivery"]["kind"]
        if kind in {"counter", "counter_at_least"}:
            unsupported[item_name] = "bare GameData counter delivery is withdrawn"
            continue
        if kind == "manual_prompt":
            unsupported[item_name] = "no automatic native action"
            continue

        tiers = range(len(mapping[item_name]["delivery"]["actors"])) \
            if kind == "progressive_actors" else (None,)
        for tier in tiers:
            plan: ItemDeliveryPlan = compile_delivery_plan(
                item_name, received_before=0 if tier is None else tier,
                mapping=mapping)
            stem = _entry_stem(item_name, tier)
            for step, operation in enumerate(plan.steps):
                entries.append(NativeDeliveryEntry(
                    item_name=item_name,
                    entry_name=f"{stem}_{step:02X}",
                    step=step,
                    step_count=len(plan.steps),
                    cursor_delta=_cursor_delta(step, len(plan.steps)),
                    plan=operation,
                    progressive_tier=tier))
                quiet = quiet_step(operation)
                if quiet is not None:
                    entries.append(replace(entries[-1], entry_name=f"{stem}_{step:02X}Q",
                                           plan=quiet, quiet=True))

    names = [entry.entry_name for entry in entries]
    if len(names) != len(set(names)):
        raise ValueError("native delivery entry-name collision")
    return entries, unsupported


def delivery_catalog(mapping=None, *, binding_token: int | None = None) -> dict:
    entries, unsupported = compile_native_entries(mapping)
    items: dict[str, dict] = {}
    for entry in entries:
        item = items.setdefault(entry.item_name, {"variants": {}})
        variant = "default" if entry.progressive_tier is None else str(
            entry.progressive_tier)
        if entry.quiet:
            # Follows its step: the catalogue names it on that step.
            item["variants"][variant][-1]["quiet_entry"] = entry.entry_name
            item["variants"][variant][-1]["quiet_flow"] = QUIET_FLOW
            continue
        item["variants"].setdefault(variant, []).append({
            "entry": entry.entry_name,
            **({"flow": QUIET_FLOW} if host_of(entry) == QUIET_FLOW else {}),
            "step": entry.step,
            "step_count": entry.step_count,
            "cursor_delta": entry.cursor_delta,
            "capacity_actor": entry.plan.capacity_actor,
            "mutations": [asdict(mutation) for mutation in entry.plan.mutations],
        })
    result = {
        "schema": 1,
        "flow": FLOW_NAME,
        "cursor": "(received_index << 8) | step",
        "reject_counter": REJECT_COUNTER,
        "items": items,
        "unsupported": unsupported,
    }
    if binding_token is not None:
        if not isinstance(binding_token, int) or not 0 < binding_token <= 0x7FFFFFFF:
            raise ValueError("binding token must be a positive signed s32")
        result["binding"] = {
            "entry": BIND_ENTRY,
            "seed_token": binding_token,
            "requires_cursor": 0,
            "requires_token": 0,
        }
    return result


def patch_session_binding(data: bytes, binding_token: int) -> tuple[bytes, list[str]]:
    """Append a literal, guarded zero-ledger session binding entry."""
    if not isinstance(binding_token, int) or not 0 < binding_token <= 0x7FFFFFFF:
        raise ValueError("binding token must be a positive signed s32")
    flow = read_flow(data)
    before = graph_snapshot(flow)
    chart = flow.flowchart
    if chart.name != FLOW_NAME or any(
            entry.name == BIND_ENTRY for entry in chart.entry_points):
        raise ValueError("session binding entry collision or wrong flow")
    system = next(actor for actor in chart.actors
                  if str(actor.identifier) == "EventSystemActor")

    def holder(collection, command):
        found = next((value for value in collection if str(value) == command), None)
        if found is None:
            found = StringHolder(command)
            collection.append(found)
        return found

    set_int = holder(system.actions, "Demo_SetGameDataInt")
    flag_on = holder(system.actions, "Demo_FlagON")
    flag_off = holder(system.actions, "Demo_FlagOFF")
    wait = holder(system.actions, "Demo_WaitFrame")
    check_int = holder(system.queries, "CheckGameDataInt")

    def action(name, command, params, nxt=None):
        event = Event()
        event.name = name
        event.data = ActionEvent()
        event.data.actor = make_rindex(system)
        event.data.actor_action = make_rindex(command)
        event.data.params = Container()
        event.data.params.data = params
        event.data.nxt = make_rindex(nxt) if nxt is not None else Index()
        chart.events.append(event)
        return event

    refused = action(BIND_ENTRY + "_Refused", wait, {
        "Frame": 0, "IsWaitFinish": True})
    guard_off = action(BIND_ENTRY + "_GuardOFF", flag_off, {
        "FlagName": "SaveProhibition", "IsWaitFinish": True})
    write_token = action(BIND_ENTRY + "_WriteToken", set_int, {
        "GameDataIntName": "APSeedToken", "Value": binding_token,
        "IsWaitFinish": True}, guard_off)
    guard_on = action(BIND_ENTRY + "_GuardON", flag_on, {
        "FlagName": "SaveProhibition", "IsWaitFinish": True}, write_token)

    def check(name, flag, yes):
        event = Event()
        event.name = name
        event.data = SwitchEvent()
        event.data.actor = make_rindex(system)
        event.data.actor_query = make_rindex(check_int)
        event.data.params = Container()
        event.data.params.data = {
            "GameDataIntName": flag, "Value": 0, "Operator": "Equal"}
        event.data.cases = {1: make_rindex(yes), 0: make_rindex(refused)}
        chart.events.append(event)
        return event

    cursor_zero = check(BIND_ENTRY + "_CursorZero", "APReceivedCursor", guard_on)
    token_zero = check(BIND_ENTRY + "_TokenZero", "APSeedToken", cursor_zero)
    entry = EntryPoint(BIND_ENTRY)
    entry.main_event = make_rindex(token_zero)
    chart.entry_points.append(entry)

    result = write_flow(flow)
    after = graph_snapshot(read_flow(result))
    for name, node in before["events"].items():
        if after["events"].get(name) != node:
            raise ValueError(f"existing event changed by session binding: {name}")
    if after["entry_points"][:len(before["entry_points"])] != before["entry_points"]:
        raise ValueError("existing entry points changed by session binding")
    return result, [
        f"append {BIND_ENTRY} for token {binding_token}",
        "require APSeedToken=0 and APReceivedCursor=0",
        "guard native APSeedToken setter with SaveProhibition",
    ]


def retarget_session_binding(data: bytes, old_token: int,
                             new_token: int) -> tuple[bytes, list[str]]:
    """Change only the literal token of an existing guarded binding entry."""
    if (not isinstance(new_token, int) or not 0 < new_token <= 0x7FFFFFFF
            or new_token == old_token):
        raise ValueError("new binding token must be a distinct positive signed s32")
    flow = read_flow(data)
    before = graph_snapshot(flow)
    write_name = BIND_ENTRY + "_WriteToken"
    expected = {
        "GameDataIntName": "APSeedToken", "Value": old_token,
        "IsWaitFinish": True,
    }
    node = before["events"].get(write_name)
    if (before["name"] != FLOW_NAME
            or dict(before["entry_points"]).get(BIND_ENTRY) != BIND_ENTRY + "_TokenZero"
            or node is None or node.get("actor_action") != "Demo_SetGameDataInt"
            or node.get("params") != expected
            or node.get("nxt") != BIND_ENTRY + "_GuardOFF"):
        raise ValueError("existing native session binding differs from audited layout")
    event = next(event for event in flow.flowchart.events if event.name == write_name)
    event.data.params.data["Value"] = new_token
    result = write_flow(flow)
    after = graph_snapshot(read_flow(result))
    expected_after = copy.deepcopy(before)
    expected_after["events"][write_name]["params"]["Value"] = new_token
    if after != expected_after:
        raise ValueError("retarget changed an unrelated delivery event")
    return result, [f"retarget {BIND_ENTRY} token {old_token} -> {new_token}"]


def _require_donors(guard_raw: bytes, capacity_raw: bytes,
                    full_raw: bytes, grant_raw: bytes,
                    special_raw: bytes) -> None:
    guard = graph_snapshot(read_flow(guard_raw))["events"].values()
    for command in ("Demo_FlagON", "Demo_FlagOFF"):
        if not any(node.get("actor_action") == command and node.get("params") == {
                "FlagName": "SaveProhibition", "IsWaitFinish": True}
                   for node in guard):
            raise ValueError(f"vanilla {command}(SaveProhibition) donor unavailable")

    capacity = graph_snapshot(read_flow(capacity_raw))["events"].values()
    if not any(node.get("actor_query") == "CheckAddPorchItem" and
               node.get("params") == {
                   "Count": 1,
                   "PorchItemName": ("Argument", "Arg_CurrentActorName")}
               for node in capacity):
        raise ValueError("vanilla CheckAddPorchItem donor unavailable")

    full = graph_snapshot(read_flow(full_raw))["events"].values()
    if not any(node.get("actor_action") == "Demo_AppearFullPouchInfo" and
               node.get("params") == {
                   "IsWaitFinish": True,
                   "PorchItemName": ("Argument", "PorchItemName")}
               for node in full):
        raise ValueError("vanilla full-pouch donor unavailable")

    grant = graph_snapshot(read_flow(grant_raw))["events"].values()
    if not any(node.get("actor_action") == "Demo_SetItemDataToPouch" and
               node.get("params", {}).get("TargetActorName") ==
               ("Argument", "CheckTargetActorName")
               for node in grant):
        raise ValueError("vanilla pouch-grant donor unavailable")
    special = graph_snapshot(read_flow(special_raw))["events"].values()
    if not any(node.get("res_flowchart_name") == "GetDemo"
               and node.get("entry_point_name") == "GetItemByName"
               and set(node.get("params", {})) == {
                   "CheckTargetActorName", "IsInvalidOpenPouch"}
               for node in special):
        raise ValueError("vanilla GetDemo<GetItemByName> donor unavailable")


def require_champion_grant_donor(raw: bytes) -> None:
    """Require the vanilla GetItemByName grant chain validated by 8g.

    Our champion entries replay it: pouch, equipment, the get window
    (ShowGetDemoDialogByName), then the get flag.
    """
    events = graph_snapshot(read_flow(raw))["events"]
    for name, command, field, wait in (
            ('Event198', 'Demo_SetItemDataToPouch', 'TargetActorName', False),
            ('Event208', 'Demo_CheckAndCreateEquip', 'TargetActorName', True),
            ('Event255', 'Demo_SetGetFlagByActorName', 'ActorName', True)):
        node = events.get(name, {})
        if (node.get('actor') != 'EventSystemActor'
                or node.get('actor_action') != command
                or node.get('params') != {'IsWaitFinish':wait,
                    field:('Argument', 'CheckTargetActorName')}):
            raise ValueError('vanilla champion grant donor unavailable')
    if (events['Event198'].get('nxt') != 'Event208'
            or events['Event208'].get('nxt') != 'Event197'
            or events['Event197'].get('entry_point_name') != 'ShowGetDemoDialogByName'
            or events['Event197'].get('nxt') != 'Event255'):
        raise ValueError('vanilla champion grant order changed')


def patch_delivery_flow(data: bytes, guard_donor: bytes, capacity_donor: bytes,
                        full_donor: bytes, grant_donor: bytes,
                        special_donor: bytes,
                        mapping=None, *, quiet: bool = False) -> tuple[bytes, list[str]]:
    """Append one guarded entry per supported native delivery step: the
    steps with the game's window to Demo007_1, or, with `quiet`, all others
    (silent twins, steps without a window) to QUIET_FLOW (see host_of)."""
    specs, unsupported = compile_native_entries(mapping)
    host = QUIET_FLOW if quiet else FLOW_NAME
    specs = [spec for spec in specs if host_of(spec) == host]
    _require_donors(guard_donor, capacity_donor, full_donor, grant_donor,
                    special_donor)
    champions = any(m.kind is MutationKind.CHAMPION_ACTOR
                    for spec in specs for m in spec.plan.mutations)
    if champions:
        require_champion_grant_donor(grant_donor)
    flow = read_flow(data)
    before = graph_snapshot(flow)
    chart = flow.flowchart
    if chart.name != host:
        raise ValueError(f"wrong delivery host flow: {chart.name}")
    existing_events = {event.name for event in chart.events}
    existing_entries = {entry.name for entry in chart.entry_points}
    if any(spec.entry_name in existing_entries for spec in specs):
        raise ValueError("native delivery entry already present")

    system = next(actor for actor in chart.actors
                  if str(actor.identifier) == "EventSystemActor")

    def holder(collection, command):
        found = next((value for value in collection if str(value) == command), None)
        if found is None:
            found = StringHolder(command)
            collection.append(found)
        return found

    action_names = (
        "Demo_FlagON", "Demo_FlagOFF", "Demo_SetItemDataToPouch",
        "Demo_AppearFullPouchInfo", "Demo_IncreaseGameDataInt",
        "Demo_SetGameDataInt")
    if champions:
        action_names += ('Demo_CheckAndCreateEquip', 'Demo_SetGetFlagByActorName')
    if any(m.kind is MutationKind.INCREASE_RUPEE for spec in specs for m in spec.plan.mutations):
        action_names += ('Demo_IncreaseRupee',)
    runes = any(m.kind is MutationKind.RUNE_DOWNLOAD for spec in specs for m in spec.plan.mutations)
    if runes:
        action_names += ('Demo_OpenItemDownloadDemo', 'Demo_CloseItemMenu')
    actions = {name: holder(system.actions, name) for name in action_names}
    queries = {"CheckAddPorchItem": holder(
        system.queries, "CheckAddPorchItem")}

    def action(name, command, params, nxt=None):
        if name in existing_events:
            raise ValueError(f"delivery event collision: {name}")
        existing_events.add(name)
        event = Event()
        event.name = name
        event.data = ActionEvent()
        event.data.actor = make_rindex(system)
        event.data.actor_action = make_rindex(actions[command])
        event.data.params = Container()
        event.data.params.data = params
        event.data.nxt = make_rindex(nxt) if nxt is not None else Index()
        chart.events.append(event)
        return event

    def actor_of(identifier, params):
        # A Demo003_0 actor, declared as it declares it when missing.
        found = next((actor for actor in chart.actors
                      if (actor.identifier.name, actor.identifier.sub_name) == identifier), None)
        if found is None:
            found = Actor()
            found.identifier = ActorIdentifier(*identifier)
            found.params = Container()
            found.params.data = dict(params)
            found.concurrent_clips = 1
            chart.actors.append(found)
        return found

    def acted(name, actor, command, params, nxt=None):
        if name in existing_events:
            raise ValueError(f"delivery event collision: {name}")
        existing_events.add(name)
        event = Event()
        event.name = name
        event.data = ActionEvent()
        event.data.actor = make_rindex(actor)
        event.data.actor_action = make_rindex(holder(actor.actions, command))
        event.data.params = Container()
        event.data.params.data = params
        event.data.nxt = make_rindex(nxt) if nxt is not None else Index()
        chart.events.append(event)
        return event

    if runes:
        waiter = actor_of(SLATE_WAITER, ACTOR_PARAMS)
        voice = actor_of(SLATE_VOICE, SLATE_VOICE_PARAMS)
        player = actor_of(PLAYER, PLAYER_PARAMS)

    def switch(name, command, params, yes, no):
        if name in existing_events:
            raise ValueError(f"delivery event collision: {name}")
        existing_events.add(name)
        event = Event()
        event.name = name
        event.data = SwitchEvent()
        event.data.actor = make_rindex(system)
        event.data.actor_query = make_rindex(queries[command])
        event.data.params = Container()
        event.data.params.data = params
        event.data.cases = {1: make_rindex(yes), 0: make_rindex(no)}
        chart.events.append(event)
        return event

    def subflow(name, flow_name, entry_name, params, nxt=None):
        if name in existing_events:
            raise ValueError(f"delivery event collision: {name}")
        existing_events.add(name)
        event = Event()
        event.name = name
        event.data = SubFlowEvent()
        event.data.res_flowchart_name = flow_name
        event.data.entry_point_name = entry_name
        event.data.params = Container()
        event.data.params.data = params
        event.data.nxt = make_rindex(nxt) if nxt is not None else Index()
        chart.events.append(event)
        return event

    for spec in specs:
        stem = spec.entry_name
        guard_off = action(stem + "_GuardOFF", "Demo_FlagOFF", {
            "FlagName": "SaveProhibition", "IsWaitFinish": True})
        commit = action(stem + "_Commit", "Demo_IncreaseGameDataInt", {
            "GameDataIntName": CURSOR_FLAG, "Value": spec.cursor_delta,
            "IsWaitFinish": True}, guard_off)
        nxt = commit
        for index, mutation in reversed(list(enumerate(spec.plan.mutations))):
            if mutation.kind is MutationKind.CHAMPION_ACTOR and spec.quiet:
                # The 9w chain: pouch, equipment, flag, without the window.
                get_flag = action(stem + f"_Mut{index}_GetFlag", 'Demo_SetGetFlagByActorName', {
                    'ActorName':mutation.target, 'IsWaitFinish':True}, nxt)
                equip = action(stem + f"_Mut{index}_Equip", 'Demo_CheckAndCreateEquip', {
                    'TargetActorName':mutation.target, 'IsWaitFinish':True}, get_flag)
                nxt = action(stem + f"_Mut{index}", 'Demo_SetItemDataToPouch', {
                    'TargetActorName':mutation.target, 'IsWaitFinish':False}, equip)
            elif mutation.kind is MutationKind.CHAMPION_ACTOR:
                get_flag = action(stem + f"_Mut{index}_GetFlag", 'Demo_SetGetFlagByActorName', {
                    'ActorName':mutation.target, 'IsWaitFinish':True}, nxt)
                # The game's own get window, where vanilla GetItemByName shows
                # it (Event197): kept since the AP journal names the sender
                # instead of an AP window (25/09).
                show = subflow(stem + f"_Mut{index}_Show", "GetDemo",
                               "ShowGetDemoDialogByName", {
                    "CheckTargetActorName": mutation.target,
                    "IsInvalidOpenPouch": False}, get_flag)
                equip = action(stem + f"_Mut{index}_Equip", 'Demo_CheckAndCreateEquip', {
                    'TargetActorName':mutation.target, 'IsWaitFinish':True}, show)
                nxt = action(stem + f"_Mut{index}", 'Demo_SetItemDataToPouch', {
                    'TargetActorName':mutation.target, 'IsWaitFinish':False}, equip)
            elif mutation.kind is MutationKind.RUNE_DOWNLOAD:
                # Demo003_0 Item01..04 (see DOWNLOAD_FLAG).
                after = acted(stem + f"_Mut{index}_After", waiter, "Demo_WaitFrame", {
                    "IsWaitFinish": True, "Frame": AFTER_SLATE}, nxt)
                idle = acted(stem + f"_Mut{index}_Idle", player, "Demo_PlayASAdapt",
                             dict(DEMO_WAIT), after)
                away = acted(stem + f"_Mut{index}_Away", player, "Demo_PlayASAdapt",
                             dict(SLATE_AWAY), idle)
                flag = action(stem + f"_Mut{index}_Flag", "Demo_FlagON", {
                    "FlagName": mutation.target, "IsWaitFinish": True}, away)
                close = action(stem + f"_Mut{index}_Close", "Demo_CloseItemMenu", {
                    "IsWaitFinish": True}, flag)
                voiced = acted(stem + f"_Mut{index}_Voice", voice, "Demo_OpenMessageDialog",
                               dict(SLATE_MESSAGE), close)
                waited = acted(stem + f"_Mut{index}_Wait", waiter, "Demo_WaitFrame", {
                    "IsWaitFinish": True, "Frame": DOWNLOAD_WAIT}, voiced)
                screen = action(stem + f"_Mut{index}_Open", "Demo_OpenItemDownloadDemo", {
                    "ItemType": int(mutation.value), "IsWaitFinish": True, "IsEquip": True,
                    "IsPowerUp": False, "IsPlayerClose": False}, waited)
                settle = acted(stem + f"_Mut{index}_Settle", waiter, "Demo_WaitFrame", {
                    "IsWaitFinish": True, "Frame": DOWNLOAD_SETTLE}, screen)
                nxt = action(stem + f"_Mut{index}", "Demo_FlagON", {
                    "FlagName": DOWNLOAD_FLAG, "IsWaitFinish": True}, settle)
            elif mutation.kind is MutationKind.INCREASE_RUPEE:
                # Not waited for: the counter's animation then runs after the
                # event instead of freezing the player (Simon, 25/09).
                nxt = action(stem + f"_Mut{index}", "Demo_IncreaseRupee", {
                    "Value": int(mutation.value), "IsWaitFinish": False}, nxt)
            elif mutation.kind is MutationKind.GRANT_ACTOR:
                nxt = action(stem + f"_Mut{index}",
                             "Demo_SetItemDataToPouch", {
                    "IsWaitFinish": False,
                    "TargetActorName": mutation.target}, nxt)
            elif mutation.kind is MutationKind.SET_BOOL and mutation.value is True:
                nxt = action(stem + f"_Mut{index}", "Demo_FlagON", {
                    "FlagName": mutation.target, "IsWaitFinish": True}, nxt)
            elif mutation.kind is MutationKind.SET_S32:
                nxt = action(stem + f"_Mut{index}", "Demo_SetGameDataInt", {
                    "GameDataIntName": mutation.target,
                    "Value": int(mutation.value),
                    "IsWaitFinish": True}, nxt)
            elif mutation.kind is MutationKind.GET_DEMO_ACTOR:
                nxt = subflow(stem + f"_Mut{index}", "GetDemo",
                              "GetItemByName", {
                    "CheckTargetActorName": mutation.target,
                    "IsInvalidOpenPouch": False}, nxt)
            else:
                raise ValueError(
                    f"unsupported compiled mutation: {spec.item_name}/{mutation.kind}")
        guard_on = action(stem + "_GuardON", "Demo_FlagON", {
            "FlagName": "SaveProhibition", "IsWaitFinish": True}, nxt)
        first = guard_on
        if spec.plan.capacity_actor:
            full = action(stem + "_Full", "Demo_AppearFullPouchInfo", {
                "IsWaitFinish": True,
                "PorchItemName": spec.plan.capacity_actor})
            reject = action(stem + "_Reject",
                            "Demo_IncreaseGameDataInt", {
                "GameDataIntName": REJECT_COUNTER, "Value": 1,
                "IsWaitFinish": True}, full)
            first = switch(stem + "_Capacity", "CheckAddPorchItem", {
                "Count": 1, "PorchItemName": spec.plan.capacity_actor},
                guard_on, reject)
        entry = EntryPoint(spec.entry_name)
        entry.main_event = make_rindex(first)
        chart.entry_points.append(entry)

    result = write_flow(flow)
    after = graph_snapshot(read_flow(result))
    for name, node in before["events"].items():
        if after["events"].get(name) != node:
            raise ValueError(f"existing event changed: {name}")
    if after["entry_points"][:len(before["entry_points"])] != before["entry_points"]:
        raise ValueError("existing entry points changed")
    return result, [
        f"append {len(specs)} guarded native delivery entries",
        f"leave {len(unsupported)} unsupported item families out of the flow",
        "use vanilla GetDemo<GetItemByName> for pouch items, vessels and rupees",
        "champions: vanilla pouch/create-equip/get-window/get-flag",
        "capacity rejection increments a volatile result counter without cursor commit",
        "capacity preflight only for actor grants; cursor commit before guard release",
    ]


def patch_delivery_event_info(data: bytes,
                              entries: list[NativeDeliveryEntry], *,
                              extra_entries=()) -> tuple[bytes, list[str]]:
    """Register entries and declare every external flow they can reach."""
    info = oead.byml.from_binary(unpack(data))
    donor_key = f"{FLOW_NAME}<APDisplayStandalone>"
    if donor_key not in info:
        donor_key = f"{FLOW_NAME}<{FLOW_NAME}>"
    donor = info[donor_key]
    fields = ("demo_event", "is_timeline", "mode", "slink_user",
              "special_actor_name")
    missing = [field for field in fields if field not in donor]
    if missing:
        raise ValueError(f"incomplete EventInfo donor: {missing}")
    added = []
    dependencies = 0
    named_entries = [(spec.entry_name, spec) for spec in entries]
    named_entries.extend((str(name), None) for name in extra_entries)
    for entry_name, spec in sorted(named_entries, key=lambda pair: pair[0]):
        quiet = spec is not None and host_of(spec) == QUIET_FLOW
        key = f"{QUIET_FLOW if quiet else FLOW_NAME}<{entry_name}>"
        if key in info:
            raise ValueError(f"delivery EventInfo already present: {key}")
        if quiet:
            # Silent: registered as the game's background events, which
            # do not pause it (QUIET_EVENT_INFO).
            info[key] = oead.byml.Hash(QUIET_EVENT_INFO)
            added.append(key)
            continue
        metadata = oead.byml.Hash({field: copy.deepcopy(donor[field])
                                   for field in fields})
        if (spec is not None and not spec.quiet and any(
                mutation.kind in (MutationKind.GET_DEMO_ACTOR, MutationKind.CHAMPION_ACTOR)
                for mutation in spec.plan.mutations)):
            metadata["subfile"] = oead.byml.Array([
                oead.byml.Hash({"file": "GetDemo.bfevfl"})])
            dependencies += 1
        info[key] = metadata
        added.append(key)
    raw = oead.byml.to_binary(info, big_endian=True)
    return bytes(oead.yaz0.compress(raw)), [
        f"register {len(added)} native delivery entries in EventInfo",
        f"declare GetDemo.bfevfl on {dependencies} vessel entries"]
