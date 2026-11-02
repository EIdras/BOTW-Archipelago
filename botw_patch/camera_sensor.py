"""The Sheikah Sensor, an item: the camera's restoration no longer gives it.

At Hateno's Ancient Tech Lab, once the guidance stone has its blue flame,
Purah restores the Slate's missing modules (Demo032_0): the camera, the
compendium, the album, and the Sheikah Sensor when IsGet_Obj_SheikSensor is
still 0. In AP the Sensor is an item of the pool (its first copy; the second is
Sensor+), which the multiworld alone must give.

This stage changes two checks of that flag in the demo's own flow:
  * Event251, the Slate's list of missing modules: the line without the Sensor
    (Text014) instead of the one that names it (Text015);
  * Event248, the Sensor's download: Event250 directly, the vanilla mark that
    Purah gave the Sensor (AncientLabo_AncientDoctor001_GetSSLv1, read by the
    lab's later talks), then the path taken when the Sensor is owned (Event321).
The download (Event249 to Event302) and the Sensor's flags after the mark
(Event318 IsGet, Event317 IsStart) are no longer reached. The camera,
compendium and album are given as in the game.
"""
from __future__ import annotations

from evfl.util import make_rindex

from botw_patch.events import graph_snapshot, read_flow, write_flow
from botw_patch.resources import vanilla_digest

PACK = "Event/Demo032_0.sbeventpack"
PACKS = {PACK: "7fccf39e214fb64b1097d3baab7a304c919ea7daa31a9a0439a655969c8015d0"}
FLOW = "EventFlow/Demo032_0.bfevfl"
FLOW_SHA = "7c3cfe61699b91733881d4b21ba3aafb9bc085791c08a6f7f15f72967039a3e0"
SENSOR = "IsGet_Obj_SheikSensor"
# Switch: (the case taken with the Sensor, the case taken without it).
LIST = ("Event251", "Event254", "Event253")
DOWNLOAD = ("Event248", "Event321", "Event249")
MARK = "Event250"
MARK_FLAG = "AncientLabo_AncientDoctor001_GetSSLv1"
# The chain no longer reached: its first event, down to the mark, then after it.
SKIPPED = ("Event249", "Event303", "Event304", "Event320", "Event311", "Event325",
           "Event302", "Event318", "Event317")
SENSOR_WRITERS = {"Event249", "Event318", "Event317", "Event304", "Event302", "Event305"}
SOURCE_FILES = ("botw_patch/camera_sensor.py",)


def _writers(graph: dict) -> set[str]:
    """The events that give the Sensor: its flags, its download presentation."""
    out = set()
    for name, node in graph["events"].items():
        flag = node.get("params", {}).get("FlagName", "")
        if ((node.get("actor_action") == "Demo_FlagON"
             and flag in (SENSOR, "IsStart_Obj_SheikSensor"))
                or node.get("actor_action") in ("Demo_DownloadShiekSensor",
                                                "Demo_DownloadSensorMoveIcon")):
            out.add(name)
    return out


def _referrers(graph: dict, target: str) -> set[str]:
    out = set()
    for name, node in graph["events"].items():
        refs = {node.get("nxt"), node.get("join"), *node.get("forks", []),
                *node.get("cases", {}).values()}
        if target in refs:
            out.add(name)
    return out


def transform(raw: bytes) -> tuple[bytes, list[str]]:
    if vanilla_digest(raw) != FLOW_SHA:
        raise ValueError("the camera restoration flow changed")
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    nodes = before["events"]
    if _writers(before) != SENSOR_WRITERS:
        raise ValueError(f"the Sensor's grants changed: {sorted(_writers(before))}")
    for switch, owned, missing in (LIST, DOWNLOAD):
        node = nodes[switch]
        if (node.get("actor_query") != "CheckFlag" or node["params"] != {"FlagName": SENSOR}
                or node["cases"] != {1: owned, 0: missing}):
            raise ValueError(f"the Sensor's check changed: {switch}")
    chain = [DOWNLOAD[2]]
    while nodes[chain[-1]].get("nxt") != DOWNLOAD[1]:
        chain.append(nodes[chain[-1]]["nxt"])
    if tuple(chain) != SKIPPED[:7] + (MARK,) + SKIPPED[7:]:
        raise ValueError(f"the Sensor's download changed: {chain}")
    if nodes[MARK]["params"].get("FlagName") != MARK_FLAG:
        raise ValueError("Purah's Sensor mark changed")
    # Only the chain itself leads into it, from its switch.
    for name in SKIPPED:
        if _referrers(before, name) - set(chain) - {DOWNLOAD[0]}:
            raise ValueError(f"{name} is reached from outside the Sensor's download")

    events = {event.name: event for event in flow.flowchart.events}
    events[LIST[0]].data.cases[0] = make_rindex(events[LIST[1]])
    events[DOWNLOAD[0]].data.cases[0] = make_rindex(events[MARK])
    events[MARK].data.nxt = make_rindex(events[DOWNLOAD[1]])

    after = graph_snapshot(flow)
    changed = {name for name in nodes if nodes[name] != after["events"][name]}
    if (changed != {LIST[0], DOWNLOAD[0], MARK} or set(after["events"]) != set(nodes)
            or after["entry_points"] != before["entry_points"]
            or after["events"][LIST[0]]["cases"] != {1: LIST[1], 0: LIST[1]}
            or after["events"][DOWNLOAD[0]]["cases"] != {1: DOWNLOAD[1], 0: MARK}
            or after["events"][MARK]["nxt"] != DOWNLOAD[1]):
        raise ValueError(f"the camera restoration changed beyond the Sensor: {sorted(changed)}")
    return write_flow(flow), [f"{FLOW}: the camera's restoration no longer gives the Sheikah Sensor"]
