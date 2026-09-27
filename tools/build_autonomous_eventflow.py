"""6k: an independent entry for the validated presentation actions."""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path if Path(p).resolve() != ROOT / "tools"]
import oead
from evfl.entry_point import EntryPoint
from evfl.util import make_rindex, Index
from botw_patch.events import read_flow, write_flow, graph_snapshot
from botw_patch.resources import ResourceBuilder, unpack

ENTRY = "APDisplayStandalone"


def add_entry(raw):
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    chart = flow.flowchart
    if any(e.name == ENTRY for e in chart.entry_points):
        raise ValueError("entry already present")
    source = {e.name: e for e in chart.events}
    names = []
    event = source["APDisplay_Sound"]
    while event.name.startswith("APDisplay_"):
        if event.name in names:
            raise ValueError("unexpected presentation cycle")
        names.append(event.name)
        event = event.data.nxt.v
    if event.name != "Event76" or len(names) != 9:
        raise ValueError("unexpected presentation chain")
    clones = []
    for name in names:
        clone = copy.copy(source[name])
        clone.name = "APStandalone_" + name.removeprefix("APDisplay_")
        clone.data = copy.copy(source[name].data)
        clones.append(clone)
    for index, clone in enumerate(clones):
        clone.data.nxt = make_rindex(clones[index + 1]) if index + 1 < len(clones) else Index()
    chart.events.extend(clones)
    entry = EntryPoint(ENTRY)
    entry.main_event = make_rindex(clones[0])
    chart.entry_points.append(entry)
    result = write_flow(flow)
    after = graph_snapshot(read_flow(result))
    for name, node in before["events"].items():
        if after["events"][name] != node:
            raise ValueError("existing event changed")
    if after["actors"] != before["actors"] or after["entry_points"][:-1] != before["entry_points"]:
        raise ValueError("existing bindings changed")
    return result, ["independent presentation entry; no campfire continuation or grant"]


def add_info(raw):
    info = oead.byml.from_binary(unpack(raw))
    key = f"Demo007_1<{ENTRY}>"
    if key in info:
        raise ValueError("metadata already present")
    donor = info["Demo007_1<Demo007_1>"]
    # Retain event/audio mode; no campfire camera, player transform, animations,
    # or child demos are used by this independent chain.
    info[key] = oead.byml.Hash({k: donor[k] for k in
        ("demo_event", "is_timeline", "mode", "slink_user", "special_actor_name")})
    return bytes(oead.yaz0.compress(oead.byml.to_binary(info, big_endian=True))), ["register standalone entry with existing event SLink user"]


def build():
    source = ROOT / ".build/ledger-validation/41b9b4eaad608300"
    manifest = json.loads((source / "manifest.json").read_text())
    files = {}
    for prefix, group in [("content/", "files"), ("", "native_files")]:
        for name, expected in manifest[group].items():
            path = (source / (prefix + name)).resolve()
            if not path.is_relative_to(source.resolve()):
                raise ValueError("source path escapes build")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("source build changed")
            files[prefix + name] = raw
    builder = ResourceBuilder(source / "content")
    builder.patch_archive("Pack/TitleBG.pack", {"EventFlow/Demo007_1.bfevfl": add_entry})
    builder.patch_archive("Pack/Bootup.pack", {"Event/EventInfo.product.sbyml": add_info})
    files.update({"content/" + n: raw for n, raw in builder.finish().items()})
    hashes = {n: hashlib.sha256(raw).hexdigest() for n, raw in sorted(files.items())}
    target = source.parent / hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:16]
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("immutable build changed")
        path.write_bytes(raw)
    (target / "rules.txt").write_bytes((source / "rules.txt").read_bytes())
    manifest.update(source_build=source.name, autonomous_eventflow=True, event_entry=ENTRY,
                    files={n[8:]: h for n, h in hashes.items() if n.startswith("content/")}, changes=builder.changes)
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    build()
