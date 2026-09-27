"""Explicit, verified pack selection for a play seed; no historical fallback."""
import json
import os
from pathlib import Path
import tempfile

from tools.build_pack_from_source import ROOT, load_seed, verify_pack
from tools.build_resources_from_source import digest, encode


def select_pack(folder: Path, pack: Path) -> None:
    pack = pack.resolve()
    if not pack.is_relative_to(ROOT.resolve()):
        raise ValueError("selected play pack must be inside the project")
    verify_pack(pack, load_seed(folder / "analysis.json", 1))
    raw = encode({"schema": 1, "pack": pack.relative_to(ROOT.resolve()).as_posix(),
                  "manifest_sha256": digest((pack / "manifest.json").read_bytes())})
    target = folder / "play-pack.json"
    if target.exists() and target.read_bytes() == raw:
        return
    with tempfile.NamedTemporaryFile(dir=folder, suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(raw)
    try:
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def selected_pack(folder: Path) -> Path:
    pointer = folder / "play-pack.json"
    if not pointer.is_file():
        raise RuntimeError("aucun pack sélectionné pour cette seed ; préparer la seed avec tools/play_seed.py")
    data = json.loads(pointer.read_text(encoding="utf-8"))
    pack = (ROOT / data["pack"]).resolve()
    if data.get("schema") != 1 or not pack.is_relative_to(ROOT.resolve()):
        raise ValueError("invalid play pack selection")
    if digest((pack / "manifest.json").read_bytes()) != data["manifest_sha256"]:
        raise ValueError("selected pack manifest changed")
    verify_pack(pack, load_seed(folder / "analysis.json", 1))
    return pack
