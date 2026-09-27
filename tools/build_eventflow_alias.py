"""6h: isolate the display-name fix inside the previously traced EventFlow."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path if Path(p).resolve() != ROOT / "tools"]
from botw_patch.events import read_flow, write_flow, graph_snapshot
from botw_patch.resources import ResourceBuilder


def use_alias(raw):
    flow = read_flow(raw)
    expected = graph_snapshot(flow)
    event = next(e for e in flow.flowchart.events if e.name == "APDisplay_Dialog")
    node = expected["events"][event.name]
    if (node["actor_action"] != "Demo_OpenGetDemoDialog"
            or node["params"]["TargetActorName"] != "Item_Fruit_A"
            or not node["params"]["IsWaitFinish"]
            or node["params"]["UseLastTryGetItemName"]):
        raise ValueError("unexpected presentation action")
    event.data.params.data["TargetActorName"] = "Item_AP"
    node["params"]["TargetActorName"] = "Item_AP"
    result = write_flow(flow)
    if graph_snapshot(read_flow(result)) != expected:
        raise ValueError("unrelated event graph change")
    return result, ["display Item_AP instead of Item_Fruit_A; all event links/actions preserved"]


def build():
    source = ROOT / ".build/ledger-validation/a5836a5af9013c95"
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
    builder.patch_archive("Pack/TitleBG.pack", {"EventFlow/Demo007_1.bfevfl": use_alias})
    donor = ROOT / ".build/ledger-validation/71e75f181f8db5a8"
    donor_manifest = json.loads((donor / "manifest.json").read_text())
    icon_name = "UI/StockItem/Item_AP.sbitemico"
    icon = (donor / "content" / icon_name).read_bytes()
    if hashlib.sha256(icon).hexdigest() != donor_manifest["files"][icon_name]:
        raise ValueError("validated icon changed")
    from botw_patch.resources import unpack
    builder.outputs[icon_name] = icon
    builder.table.set_size("UI/StockItem/Item_AP.bitemico", len(unpack(icon)) + 8192)
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
    manifest.update(source_build=source.name, standalone_display=False, standalone_sound=False,
                    display_actor="Item_AP", presentation_variant="eventflow_alias",
                    dialog_question="Window visible with the test pattern (red circle, colored corners)? yes/no: ",
                    text_scope="No custom text substitution; note the actual title and description separately.",
                    files={n[8:]: h for n, h in hashes.items() if n.startswith("content/")},
                    native_files={n: h for n, h in hashes.items() if not n.startswith("content/")},
                    changes=builder.changes)
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(target)
    return target


if __name__ == "__main__":
    build()
