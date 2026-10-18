"""The Divine Beasts' heart containers: picked up without the game's get window.

Each of them is an AP check (`Vah X Heart Container`, flag Get_HeartUtuwa_X):
picking it up must say nothing more than the check's AP message. In the game,
a map actor picked up goes through GetDemo<GetItemByActorIdentifierBase>: the
actor's flags and its death (Demo_SetGetFlag, Demo_SuccessGet; its DeadUp link
sets the check's flag), then the entry `_main`, the presentation: the get
sound, Link raising the item, the window, then the heart gauge filling up. The
heart itself is withheld by the native chain (tools/build_world_heart_withhold.py).

This stage puts a test before `_main`'s first event, the one `_main` already
makes further on (Event294, CheckTreasure on its argument actor): a heart
container skips the whole presentation, everything else runs it as before.
`_main` only presents a picked-up map actor (GetItemByActorIdentifierBase and
GetItemPouchFullWithNameByCurrentBase call it). Obj_HeartUtuwa_A_01 is placed
in the Divine Beasts and in front of the Goddess Statues, but a statue's heart
is not picked up: its trade (Demo034_0, GetMatome) grants through GetItemByName,
whose window is ShowGetDemoDialogByName's, as AP deliveries do. Both keep it.
"""
from __future__ import annotations

from evfl.common import StringHolder
from evfl.container import Container
from evfl.event import ActionEvent, Event, SwitchEvent
from evfl.util import Index, make_rindex

from botw_patch.events import graph_snapshot, read_flow, write_flow
from botw_patch.resources import digest, vanilla_digest

FLOW = "EventFlow/GetDemo.bfevfl"
FLOW_SHA = "af201d87d582f218ee5898ef3efa97f482fbd564e487385793b1efe7066817c8"
ENTRY = "_main"
FIRST = "Event327"
ACTOR = "Obj_HeartUtuwa_A_01"
# Event294's own parameters.
TEST = {"ActorName": ACTOR, "CheckTargetActorName": ""}
SOURCE_FILES = ("botw_patch/beast_heart.py",)


def transform(raw: bytes) -> tuple[bytes, list[str]]:
    if vanilla_digest(raw) != FLOW_SHA:
        raise ValueError("GetDemo flow changed")
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    chart = flow.flowchart
    entry = next(e for e in chart.entry_points if e.name == ENTRY)
    if entry.main_event.v.name != FIRST:
        raise ValueError(f"{ENTRY} starts with {entry.main_event.v.name}, not {FIRST}")
    vanilla = before["events"]["Event294"]
    if (vanilla.get("actor_query") != "CheckTreasure" or vanilla.get("params") != TEST
            or vanilla.get("actor") != "Argument[_main(Current)]"):
        raise ValueError("GetDemo heart test changed")
    current = next(a for a in chart.actors
                   if a.identifier.name == "Argument" and a.identifier.sub_name == "_main(Current)")
    system = next(a for a in chart.actors
                  if a.identifier.name == "EventSystemActor" and not a.identifier.sub_name)
    query = next(q for q in current.queries if str(q) == "CheckTreasure")
    wait = next((a for a in system.actions if str(a) == "Demo_WaitFrame"), None)
    if wait is None:
        wait = StringHolder("Demo_WaitFrame")
        system.actions.append(wait)

    skip = Event()
    skip.name = "APBeastHeart_Skip"
    skip.data = ActionEvent()
    skip.data.actor = make_rindex(system)
    skip.data.actor_action = make_rindex(wait)
    skip.data.params = Container()
    skip.data.params.data = {"Frame": 1, "IsWaitFinish": True}
    skip.data.nxt = Index()
    test = Event()
    test.name = "APBeastHeart"
    test.data = SwitchEvent()
    test.data.actor = make_rindex(current)
    test.data.actor_query = make_rindex(query)
    test.data.params = Container()
    test.data.params.data = dict(TEST)
    test.data.cases = {1: make_rindex(skip), 0: make_rindex(entry.main_event.v)}
    chart.events.extend([test, skip])
    entry.main_event = make_rindex(test)

    after = graph_snapshot(flow)
    if (any(after["events"][name] != node for name, node in before["events"].items())
            or set(after["events"]) - set(before["events"]) != {test.name, skip.name}
            or [e for e in after["entry_points"] if e[0] != ENTRY]
            != [e for e in before["entry_points"] if e[0] != ENTRY]):
        raise ValueError("GetDemo changed beyond the heart test")
    return write_flow(flow), [f"GetDemo<{ENTRY}>: a heart container picked up skips its presentation"]
