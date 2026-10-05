"""The Master Sword's pedestal closed, when its sword was taken without the pull.

The game can let Link take the pedestal's sword (Weapon_Sword_070, HashId
2427157272 in F-2) as a dropped weapon: no pull, so none of the pull's flags.
The client sees the check through the actor's own flag
(botw_client/locations.ALTERNATE_FLAGS), but the pedestal still offers its
pull, "Retirer", for a sword it no longer holds: the map unit F-2 gates the
pull with tags whose state is saved in IsPlayed_Demo104_0 (the first try,
set as the pull starts) and IsPlayed_Demo109_0 (the pull done: the pull's
EventTag, its observer and area deleted, the base signalled). Measured on
Simon's saves (06/10): a closed pedestal differs from that open one, among the
pedestal's flags, by Get_MasterSword_Finish and IsPlayed_Demo109_0/_1/_2,
which Get_MasterSword<NukiGameFinish> sets as the pull ends.

A client's raw write to a live flag is volatile (tools/cemu/livegdt.py), and
the save kept Get_MasterSword_Finish at 0 after such a write. This entry sets
the same flags through the game's own Demo_FlagON, which the save keeps; the
client requests it once, when the pedestal is open after its check. The tags
read their flags as the area loads: the pedestal is closed from the next load
of F-2 on.
"""
from __future__ import annotations

import oead
from evfl.common import StringHolder
from evfl.container import Container
from evfl.entry_point import EntryPoint
from evfl.event import ActionEvent, Event
from evfl.util import Index, make_rindex

from botw_patch.delivery_flow import QUIET_EVENT_INFO, QUIET_FLOW
from botw_patch.events import graph_snapshot, read_flow, write_flow
from botw_patch.resources import unpack

ENTRY = "APClosePedestal"
FLOW_NAME = QUIET_FLOW
EVENT_INFO = "Event/EventInfo.product.sbyml"
# In the order the pull sets them: IsPlayed_Demo104_0 as it starts (equal on
# both saves measured, a try had been made; without it the first pull's
# EventTag stays), the others as it ends (Get_MasterSword<NukiGameFinish>).
FLAGS = ("IsPlayed_Demo104_0", "IsPlayed_Demo109_0", "IsPlayed_Demo109_1", "IsPlayed_Demo109_2",
         "Get_MasterSword_Finish")
SOURCE_FILES = ("botw_patch/pedestal.py",)


def add_entry(raw: bytes) -> tuple[bytes, list[str]]:
    """OperationGuide<APClosePedestal>: Demo_FlagON on each of FLAGS."""
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    chart = flow.flowchart
    if chart.name != FLOW_NAME:
        raise ValueError(f"unexpected flow: {chart.name}")
    names = {entry.name for entry in chart.entry_points} | {e.name for e in chart.events}
    events = [ENTRY] + [f"{ENTRY}_{n}" for n in range(1, len(FLAGS))]
    if names & set(events):
        raise ValueError(f"{ENTRY} already present")
    system = next(a for a in chart.actors if str(a.identifier) == "EventSystemActor")
    command = next((a for a in system.actions if str(a) == "Demo_FlagON"), None)
    if command is None:
        command = StringHolder("Demo_FlagON")
        system.actions.append(command)
    following = None
    for name, flag in reversed(list(zip(events, FLAGS))):
        event = Event()
        event.name = name
        event.data = ActionEvent()
        event.data.actor = make_rindex(system)
        event.data.actor_action = make_rindex(command)
        event.data.params = Container()
        event.data.params.data = {"FlagName": flag, "IsWaitFinish": True}
        event.data.nxt = make_rindex(following) if following is not None else Index()
        chart.events.append(event)
        following = event
    entry = EntryPoint(ENTRY)
    entry.main_event = make_rindex(following)
    chart.entry_points.append(entry)
    out = write_flow(flow)
    after = graph_snapshot(read_flow(out))
    if any(after["events"].get(name) != node for name, node in before["events"].items()):
        raise ValueError("existing event changed")
    if after["entry_points"][:len(before["entry_points"])] != before["entry_points"]:
        raise ValueError("existing entry points changed")
    return out, [f"{FLOW_NAME}<{ENTRY}>: Demo_FlagON {', '.join(FLAGS)}"]


def add_event_info(raw: bytes) -> tuple[bytes, list[str]]:
    info = oead.byml.from_binary(unpack(raw))
    key = f"{FLOW_NAME}<{ENTRY}>"
    if key in info:
        raise ValueError(f"EventInfo already present: {key}")
    info[key] = oead.byml.Hash(QUIET_EVENT_INFO)
    packed = oead.byml.to_binary(info, big_endian=True)
    return (bytes(oead.yaz0.compress(packed)) if raw[:4] == b"Yaz0" else bytes(packed)), [
        f"register {key} as a background event"]
