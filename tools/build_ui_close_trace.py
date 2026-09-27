"""Package the unchanged 6a resources plus one temporary close-call probe."""
import hashlib
import json
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/cemu"))
from rpx import Rpx
sys.path[:] = [str(ROOT)] + [p for p in sys.path
    if Path(p).resolve() not in {ROOT / "tools", ROOT / "tools/cemu"}]
from botw_patch.events import read_flow, write_flow, graph_snapshot
from botw_patch.resources import ResourceBuilder


def wait_for_message_close(raw):
    """Wait for the previous message to close before opening the item screen."""
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    event = next(e for e in flow.flowchart.events if e.name == "APDisplay_CloseMessage")
    expected = before["events"][event.name]
    if (expected.get("actor"), expected.get("actor_action"), expected.get("nxt"),
            expected.get("params")) != ("EventSystemActor[Temp]", "Demo_CloseMessageDialog",
                                       "APDisplay_Dialog", {"IsWaitFinish": False}):
        raise ValueError("unexpected close-message diagnostic")
    event.data.params.data["IsWaitFinish"] = True
    result = write_flow(flow)
    expected["params"]["IsWaitFinish"] = True
    if graph_snapshot(read_flow(result)) != before:
        raise ValueError("changed more than close-message completion policy")
    return result, ["await Demo_CloseMessageDialog before opening item dialog"]


def build(wait_previous_message=False):
    if Rpx().read(0x035FF004, 4) != bytes.fromhex("3d801048"):
        raise ValueError("unexpected close function instruction")
    source = ROOT / ".build/ledger-validation/7aeb16758e589d3c"
    manifest = json.loads((source / "manifest.json").read_text())
    files = {}
    for name, expected in manifest["files"].items():
        path = (source / "content" / name).resolve()
        if not path.is_relative_to((source / "content").resolve()):
            raise ValueError("resource path escapes build")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("source resource changed")
        files["content/" + name] = raw
    if wait_previous_message:
        builder = ResourceBuilder(source / "content")
        builder.patch_archive("Pack/TitleBG.pack", {
            "EventFlow/Demo007_1.bfevfl": wait_for_message_close})
        for name, raw in builder.finish().items():
            files["content/" + name] = raw
    # .origin/labels use Cemu's modern parser; patches.txt selects Cemuhook.
    patch_name = "patch_ui_close_trace.asm"
    files[patch_name] = (ROOT / "native/cemu/ui_close_trace.asm").read_bytes()
    hashes = {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())}
    identity = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:16]
    target = source.parent / identity
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("immutable build changed")
        path.write_bytes(raw)
    (target / "rules.txt").write_bytes((source / "rules.txt").read_bytes())
    manifest.update(native_files={patch_name: hashes[patch_name]},
                    close_call_trace=True, source_build=source.name)
    if wait_previous_message:
        manifest.update(wait_previous_message=True,
                        files={name.removeprefix("content/"): value for name, value in hashes.items()
                               if name.startswith("content/")}, changes=builder.changes)
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wait-previous-message", action="store_true")
    build(parser.parse_args().wait_previous_message)
