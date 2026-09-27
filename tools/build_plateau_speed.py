"""Build an isolated candidate with faster player locomotion animations."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path
                            if Path(p).resolve() != ROOT / "tools"]
import oead
from botw_patch.resources import ResourceBuilder, digest, unpack


def faster_animation(raw, member, multiplier=3, *, preserve_size=True):
    params = oead.aamp.ParameterIO.from_binary(raw)
    edits = []
    for key, element in params.lists["Elements"].lists.items():
        node = element.objects["Parameters"]
        if "FileName" not in node.params:
            continue
        name = str(node.params["FileName"].v)
        selected = (name.startswith(("Nml_Move_Run", "Nml_Move_Dash"))
                    if member.endswith("Player_Move.bas") else
                    name.startswith("Climb_Wall_Move"))
        if not selected:
            continue
        ctrl = element.lists["Extend"].lists["FrameCtrl"].objects["FrameCtrl0"]
        if "Rate" not in ctrl.params:
            continue  # Keep structure/allocation unchanged, including tired movement.
        previous = float(ctrl.params["Rate"].v)
        ctrl.params["Rate"] = oead.aamp.Parameter(previous * multiplier)
        edits.append({"animation": name, "before": previous,
                      "after": float(ctrl.params["Rate"].v)})
    result = bytes(params.to_binary())
    if not edits or (preserve_size and len(result) != len(raw)):
        raise ValueError("Locomotion edit must preserve allocation size")
    return result, edits


def build(source, output):
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        if digest((source / "content" / name).read_bytes()) != expected:
            raise ValueError(f"Modified source: {name}")
    resources = ResourceBuilder(source / "content")

    def player(raw):
        archive = oead.Sarc(unpack(raw))
        writer = oead.SarcWriter.from_sarc(archive)
        edits = {}
        for member in ("Actor/AS/Player_Move.bas", "Actor/AS/Player_ClimbMove.bas"):
            replacement, detail = faster_animation(bytes(archive.get_file(member).data), member)
            writer.files[member] = replacement
            edits[member] = detail
        return bytes(oead.yaz0.compress(bytes(writer.write()[1]))), edits

    resources.patch_archive("Pack/TitleBG.pack", {
        "Actor/Pack/GameROMPlayer.sbactorpack": player})
    replacements = resources.finish()
    files = {name: (replacements[name] if name in replacements else
                    (source / "content" / name).read_bytes())
             for name in manifest["files"]}
    identity = hashlib.sha256(json.dumps(
        {name: digest(raw) for name, raw in files.items()}, sort_keys=True).encode()).hexdigest()[:16]
    target = output / identity
    target.mkdir(parents=True, exist_ok=True)
    for path in source.iterdir():
        if path.is_file() and path.name != "manifest.json":
            destination = target / path.name
            data = path.read_bytes()
            if destination.exists() and destination.read_bytes() != data:
                raise ValueError("Modified immutable speed candidate")
            destination.write_bytes(data)
    for name, data in files.items():
        path = target / "content" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != data:
            raise ValueError("Modified immutable speed resource")
        path.write_bytes(data)
    manifest["files"] = {name: digest(raw) for name, raw in files.items()}
    manifest["validation_aids"] = {"source_candidate": source.name,
        "locomotion_animation_rate_multiplier": 3,
        "status": "requires_in_game_validation", "changes": resources.changes,
        "reference": "https://zeldamods.org/wiki/Bas#FrameCtrl"}
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / ".build/plateau-speed")
    args = parser.parse_args()
    print(build(args.source, args.output))
