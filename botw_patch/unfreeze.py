"""A small event that gives Link back to the player when he is left frozen.

A received DeathLink whose kill the game runs during a cutscene empties
Link's hearts, but the game never starts his death: he stays in place, cannot
move nor save (seen in a room, at the end of the Great Plateau Tower's
cutscene). Writing his hearts back does not free him. What did, measured in
the same room, was the next item delivery: a rune's presentation, whose last
steps are the player putting the Slate away (Demo041_0<SheikPadSetOff>, then
DemoWait) in a Demo007_1 entry, a demo event.

Demo007_1<APUnfreeze> plays only those last steps, as the rune deliveries do
(botw_patch/delivery_flow.py, SLATE_AWAY, DEMO_WAIT, AFTER_SLATE): the player's
SheikPadSetOff, then DemoWait, then AFTER_SLATE frames. It is registered as the
delivery entries are (their EventInfo donor), so the game plays it as one of
them: a demo event, which takes Link and hands him back as it ends.

The client requests it (botw_client/runtime.py, _rescue_stuck_death; console
/ap-unfreeze) once Link has a quarter heart again: the game takes no event
while his hearts are empty.
"""
from __future__ import annotations

import copy

import oead
from evfl.actor import Actor, ActorIdentifier
from evfl.common import StringHolder
from evfl.container import Container
from evfl.entry_point import EntryPoint
from evfl.event import ActionEvent, Event
from evfl.util import Index, make_rindex

from botw_patch.delivery_flow import (AFTER_SLATE, DEMO_WAIT, FLOW_NAME, PLAYER, PLAYER_PARAMS,
                                      SLATE_AWAY)
from botw_patch.events import graph_snapshot, read_flow, write_flow
from botw_patch.resources import unpack

ENTRY = "APUnfreeze"
EVENT_INFO = "Event/EventInfo.product.sbyml"
SOURCE_FILES = ("botw_patch/unfreeze.py",)
# The fields the delivery entries take from their donor (patch_delivery_event_info).
INFO_FIELDS = ("demo_event", "is_timeline", "mode", "slink_user", "special_actor_name")


def add_entry(raw: bytes) -> tuple[bytes, list[str]]:
    """Demo007_1<APUnfreeze>: the player's SheikPadSetOff, DemoWait, then
    AFTER_SLATE frames."""
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    chart = flow.flowchart
    if chart.name != FLOW_NAME:
        raise ValueError(f"unexpected flow: {chart.name}")
    names = {entry.name for entry in chart.entry_points} | {e.name for e in chart.events}
    if ENTRY in names:
        raise ValueError(f"{ENTRY} already present")
    system = next(a for a in chart.actors if str(a.identifier) == "EventSystemActor")
    player = next((a for a in chart.actors
                   if (a.identifier.name, a.identifier.sub_name) == PLAYER), None)
    if player is None:
        player = Actor()
        player.identifier = ActorIdentifier(*PLAYER)
        player.params = Container()
        player.params.data = dict(PLAYER_PARAMS)
        player.concurrent_clips = 1
        chart.actors.append(player)

    def holder(collection, name):
        found = next((value for value in collection if str(value) == name), None)
        if found is None:
            found = StringHolder(name)
            collection.append(found)
        return found

    def action(name, actor, command, params, nxt=None):
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

    after = action(f"{ENTRY}_After", system, "Demo_WaitFrame",
                   {"IsWaitFinish": True, "Frame": AFTER_SLATE})
    idle = action(f"{ENTRY}_Idle", player, "Demo_PlayASAdapt", dict(DEMO_WAIT), after)
    away = action(ENTRY, player, "Demo_PlayASAdapt", dict(SLATE_AWAY), idle)
    if names & {e.name for e in (after, idle)}:
        raise ValueError(f"{ENTRY} events already present")
    entry = EntryPoint(ENTRY)
    entry.main_event = make_rindex(away)
    chart.entry_points.append(entry)
    out = write_flow(flow)
    after_graph = graph_snapshot(read_flow(out))
    if any(after_graph["events"].get(name) != node for name, node in before["events"].items()):
        raise ValueError("existing event changed")
    if after_graph["entry_points"][:len(before["entry_points"])] != before["entry_points"]:
        raise ValueError("existing entry points changed")
    return out, [f"{FLOW_NAME}<{ENTRY}>: GameROMPlayer SheikPadSetOff, DemoWait, "
                 f"{AFTER_SLATE} frames"]


def add_event_info(raw: bytes) -> tuple[bytes, list[str]]:
    """Register the entry as the delivery entries are: their donor's fields."""
    info = oead.byml.from_binary(unpack(raw))
    key = f"{FLOW_NAME}<{ENTRY}>"
    if key in info:
        raise ValueError(f"EventInfo already present: {key}")
    donor_key = f"{FLOW_NAME}<APDisplayStandalone>"
    if donor_key not in info:
        donor_key = f"{FLOW_NAME}<{FLOW_NAME}>"
    donor = info[donor_key]
    missing = [field for field in INFO_FIELDS if field not in donor]
    if missing:
        raise ValueError(f"incomplete EventInfo donor: {missing}")
    info[key] = oead.byml.Hash({field: copy.deepcopy(donor[field]) for field in INFO_FIELDS})
    packed = oead.byml.to_binary(info, big_endian=True)
    return (bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else bytes(packed)), [
        f"register {key} as a delivery entry"]
