"""Rebuild the verified persistence/EventFlow base from the Wii U v208 update.

This stage is intentionally limited to the historical ledger base. Later
resource stages compose on its outputs; no previous .build candidate is read.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

import oead

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path
                            if Path(p).resolve() != ROOT / "tools"]

from botw_patch.ledger_experiment import patch_campfire_delivery  # noqa: E402
from botw_patch.resources import ResourceBuilder, digest, unpack  # noqa: E402
from tools.build_delivery_control import presentation_call  # noqa: E402
from tools.build_game_data_mod import modify_gamedata, modify_saveformat, verify  # noqa: E402
from tools.build_ui_close_trace import wait_for_message_close  # noqa: E402
from tools.build_ui_lifecycle import porch_guards  # noqa: E402
from tools.build_eventflow_alias import use_alias  # noqa: E402
from tools.build_autonomous_eventflow import add_entry, add_info  # noqa: E402
from tools.build_owned_presentation import mark_action  # noqa: E402

INPUT_HASHES = {
    "Pack/Bootup.pack": "f092c69a3598c31dbcdab1caa6292d2eabb78a7391c2e0954d5ae7fbb888594b",
    "Pack/TitleBG.pack": "12f9925add7d855bad95fbd85cbfbdf760b932e2361c8b306943a6fa0b8e3234",
    "System/Resource/ResourceSizeTable.product.srsizetable":
        "c501fc3033958f609cd2fc960c16ab4258b083381bd7be578d88f819a5444f2b",
}
ALLOCATION = 65536
ICON = ROOT / "assets/wiiu/Item_AP.sbitemico"
ICON_SHA256 = "09c6057c14ecd01abb42df9d2975034c931bc93b95188599e866a6f211f24cd3"


def generate(content: Path) -> tuple[dict[str, bytes], list[dict]]:
    """Return the three overlay resources without reading prior candidates."""
    for name, expected in INPUT_HASHES.items():
        if digest((content / name).read_bytes()) != expected:
            raise ValueError(f"unexpected Wii U update resource: {name}")
    builder = ResourceBuilder(content)
    builder.patch_archive("Pack/Bootup.pack", {
        "GameData/gamedata.ssarc": lambda raw: (
            modify_gamedata(raw, is_save=True), ["APReceivedCursor", "APSeedToken"]),
        "GameData/savedataformat.ssarc": lambda raw: (
            modify_saveformat(raw), ["register saved AP flags"]),
    })
    builder.patch_archive("Pack/TitleBG.pack", {
        "EventFlow/Demo007_1.bfevfl": patch_campfire_delivery,
    })
    for key in ("GameData/gamedata.sarc", "GameData/savedataformat.sarc"):
        builder.table.set_size(key, builder.table.get_size(key) + ALLOCATION)
    return builder.finish(), builder.changes


def patch_stage(files: dict[str, bytes], name: str, transforms: dict, *,
                extra_archive: tuple[str, dict] | None = None,
                icon: bytes | None = None, new_members=()) -> tuple[dict, list]:
    """Apply a historic stage with its own resource-size table accounting."""
    # A file the antivirus still holds may outlive the build here: the system's
    # temporary folder takes it, rather than failing the pack.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        stage_content = Path(temp)
        for filename, raw in files.items():
            path = stage_content / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        builder = ResourceBuilder(stage_content)
        builder.patch_archive(name, transforms, new_members=new_members)
        if extra_archive is not None:
            builder.patch_archive(*extra_archive)
        if icon is not None:
            builder.outputs["UI/StockItem/Item_AP.sbitemico"] = icon
            builder.table.set_size("UI/StockItem/Item_AP.bitemico", len(unpack(icon)) + 8192)
        files.update(builder.finish())
        return files, builder.changes


def generate_presentation(content: Path, stage: str = "presentation") -> tuple[dict[str, bytes], list[dict]]:
    """Rebuild the presentation chain while preserving each stage's RSTB."""
    files, changes = generate(content)
    vanilla = oead.Sarc(unpack((content / "Pack/TitleBG.pack").read_bytes()))
    donor = bytes(vanilla.get_file("EventFlow/GetDemo.bfevfl").data)
    if digest(donor) != "af201d87d582f218ee5898ef3efa97f482fbd564e487385793b1efe7066817c8":
        raise ValueError("unexpected vanilla GetDemo donor")
    name = "Pack/TitleBG.pack"
    member = "EventFlow/Demo007_1.bfevfl"
    files, edits = patch_stage(files, name, {member: lambda raw: presentation_call(raw, donor)})
    changes.extend(edits)
    if stage == "presentation":
        return files, changes
    files, edits = patch_stage(files, name, {member: wait_for_message_close})
    changes.extend(edits)
    if stage == "message_wait":
        return files, changes
    files, edits = patch_stage(files, name, {member: lambda raw: porch_guards(raw, donor)})
    changes.extend(edits)
    if stage == "porch_guards":
        return files, changes
    icon = ICON.read_bytes()
    if digest(icon) != ICON_SHA256 or unpack(icon)[:4] != b"FRES":
        raise ValueError("project AP icon is missing or changed")
    files, edits = patch_stage(files, name, {member: use_alias}, icon=icon)
    changes.extend(edits)
    if stage == "alias":
        return files, changes
    files, edits = patch_stage(files, name, {member: add_entry},
                              extra_archive=("Pack/Bootup.pack", {
                                  "Event/EventInfo.product.sbyml": add_info}))
    changes.extend(edits)
    if stage == "autonomous":
        return files, changes
    files, edits = patch_stage(files, name, {member: mark_action})
    changes.extend(edits)
    return files, changes


def build(content: Path, output: Path, *, stage: str = "base") -> Path:
    if stage not in ("base", "presentation", "message_wait", "porch_guards",
                     "alias", "autonomous", "owned_marker"):
        raise ValueError("unknown resource stage")
    files, changes = (generate(content) if stage == "base"
                      else generate_presentation(content, stage))
    hashes = {name: digest(raw) for name, raw in sorted(files.items())}
    target = output.resolve() / digest(json.dumps(hashes, sort_keys=True).encode())[:16]
    if target.exists():
        existing = {p.relative_to(target).as_posix() for p in target.rglob("*") if p.is_file()}
        if existing != {"manifest.json", *("content/" + name for name in files)}:
            raise ValueError("existing resource base is incomplete or has extra files")
    for name, raw in files.items():
        path = target / "content" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"immutable resource base modified: {name}")
        path.write_bytes(raw)
    verify(target / "content/Pack/Bootup.pack", expect_saved=True,
           expect_definition_saved=True)
    manifest = {
        "schema": 1, "component": "resource_" + stage + "_only", "status": "not_installable",
        "platform": "wiiu", "revision": "EUR v208", "installed": False,
        "input_hashes": INPUT_HASHES, "extra_parse_allocation": ALLOCATION,
        "files": hashes, "changes": changes,
    }
    encoded = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    path = target / "manifest.json"
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("immutable resource base manifest modified")
    path.write_bytes(encoded)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / ".build/resource-base-from-source")
    parser.add_argument("--stage", choices=("base", "presentation", "message_wait",
                                            "porch_guards", "alias", "autonomous",
                                            "owned_marker"), default="base")
    args = parser.parse_args()
    print(build(args.content, args.output, stage=args.stage))
