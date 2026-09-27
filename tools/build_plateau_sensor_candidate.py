"""Remove the vanilla Sheikah Sensor grant of the tower flow (Demo004_0).

A stage of the native build chain: any verified parent without its own
Demo004_0 archive. Once MapTower_DemoFirst is set, *any* tower activated while
IsGet_Obj_SheikSensor is false grants the sensor, so the neutralisation
belongs to every build, not only to the Plateau lab pack. Validated in game on
386f3df72c18dcb3 (8t/8u: tower check, no vanilla sensor). Seed builds start
from a base that carries this stage (tools/build_seed_bound_candidate.py).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path
                            if Path(p).resolve() != ROOT / "tools"]

import oead  # noqa: E402

from botw_patch.events import graph_snapshot, read_flow, wait_instead, write_flow  # noqa: E402
from botw_patch.resources import ResourceBuilder, digest, unpack  # noqa: E402
from tools.build_seed_bound_candidate import verified_files  # noqa: E402

SOURCE = ROOT / ".build/seed-bound-candidates/c21e751b27597559"
OUTPUT = ROOT / ".build/plateau-sensor-candidates"
UPDATE = Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title/0005000e/101c9500/content"
PACK = "Event/Demo004_0.sbeventpack"
FLOW = "EventFlow/Demo004_0.bfevfl"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
EXPECTED_SOURCE_SHA = "6b766cb93bcf1eb5a93d6d3510317cec63a52308bdbc0d39c13ce19b2dd42758"
SENSOR_ACTIONS = {
    "Event595": ("Demo_FlagON", "IsGet_Obj_SheikSensor"),
    "Event664": ("Demo_DownloadShiekSensor", None),
    "Event673": ("Demo_FlagON", "MiniMapSensor_Demo"),
    "Event678": ("Demo_StartShiekSensorGaugeDemo", None),
    "Event669": ("Demo_FlagON", "IsStart_Obj_SheikSensor"),
}


def transform(raw: bytes) -> tuple[bytes, list[str]]:
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    if flow.flowchart.name != "Demo004_0":
        raise ValueError("wrong tower flow")
    events = {event.name: event for event in flow.flowchart.events}
    for name, (action, flag) in SENSOR_ACTIONS.items():
        node = before["events"][name]
        if (node.get("actor_action") != action
                or (flag is not None and node.get("params", {}).get("FlagName") != flag)):
            raise ValueError(f"tower sensor source changed: {name}")
        wait_instead(flow, events[name])
    after = graph_snapshot(flow)
    if (before["entry_points"] != after["entry_points"]
            or before["name"] != after["name"]
            or set(before["events"]) != set(after["events"])):
        raise ValueError("tower graph structure changed")
    changed = {name for name in before["events"]
               if before["events"][name] != after["events"][name]}
    if changed != set(SENSOR_ACTIONS):
        raise ValueError(f"unexpected tower actions changed: {changed}")
    for name in changed:
        if before["events"][name].get("nxt") != after["events"][name].get("nxt"):
            raise ValueError(f"tower edge changed: {name}")
    for name in ("Event275", "Event284", "Event594", "Event667"):
        if before["events"][name] != after["events"][name]:
            raise ValueError(f"tower progression changed: {name}")
    return write_flow(flow), sorted(changed)


def build(source: Path = SOURCE, output: Path = OUTPUT, update: Path = UPDATE) -> Path:
    source = source.resolve()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if (PACK in manifest["files"] or not manifest.get("native_delivery_entries")
            or manifest.get("plateau_sensor_source")):
        raise ValueError("source is not a verified native candidate without the sensor stage")
    files = verified_files(source, manifest)
    raw_pack = (update / PACK).read_bytes()
    if digest(raw_pack) != EXPECTED_SOURCE_SHA:
        raise ValueError("mounted Plateau tower source changed")
    stage = output / "_input"
    (stage / "Event").mkdir(parents=True, exist_ok=True)
    (stage / "System/Resource").mkdir(parents=True, exist_ok=True)
    (stage / PACK).write_bytes(raw_pack)
    (stage / TABLE).write_bytes(files["content/" + TABLE])
    builder = ResourceBuilder(stage)
    builder.patch_archive(PACK, {FLOW: transform})
    outputs = builder.finish()
    if set(outputs) != {PACK, TABLE} or len(builder.changes) != 1:
        raise ValueError("unexpected source outputs")
    before = oead.Sarc(unpack(raw_pack))
    after = oead.Sarc(unpack(outputs[PACK]))
    names = {item.name for item in before.get_files()}
    if names != {item.name for item in after.get_files()}:
        raise ValueError("tower pack members changed")
    changed = {name for name in names if bytes(before.get_file(name).data)
               != bytes(after.get_file(name).data)}
    if changed != {FLOW}:
        raise ValueError(f"unexpected tower pack members changed: {changed}")
    files.update({"content/" + name: raw for name, raw in outputs.items()})
    hashes = {name: digest(raw) for name, raw in sorted(files.items())}
    build_id = hashlib.sha256(json.dumps(hashes, sort_keys=True,
                              separators=(",", ":")).encode()).hexdigest()[:16]
    target = (output / build_id).resolve()
    if not target.is_relative_to(output.resolve()):
        raise ValueError("candidate escaped output root")
    for name, raw in files.items():
        path = (target / name).resolve()
        if not path.is_relative_to(target):
            raise ValueError("candidate member escaped output root")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"immutable candidate changed: {name}")
        path.write_bytes(raw)
    result = dict(manifest)
    result.update({
        "status": "requires_in_game_validation",
        "plateau_sensor_source": {
            "parent_build": source.name,
            "source_sha256": EXPECTED_SOURCE_SHA,
            "flow": FLOW,
            "disabled_actions": sorted(SENSOR_ACTIONS),
            "source_change": builder.changes[0],
        },
        "files": {name[8:]: value for name, value in hashes.items()
                  if name.startswith("content/")},
        "native_files": {name: hashes[name] for name in manifest["native_files"]},
    })
    manifest_path = target / "manifest.json"
    encoded = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    if manifest_path.exists() and manifest_path.read_bytes() != encoded:
        raise ValueError("immutable candidate manifest changed")
    manifest_path.write_bytes(encoded)
    return target


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    print(build(arguments.source, arguments.output))
