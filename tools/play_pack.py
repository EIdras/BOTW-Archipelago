"""Explicit, verified pack selection for a play seed; no historical fallback."""
import json
import os
from pathlib import Path
import tempfile

from botw_client.paths import DATA, ROOT
from tools.build_pack_from_source import load_seed, seed_slot, verify_pack
from tools.build_resources_from_source import digest, encode


def seed_binding(folder: Path) -> dict:
    """The verified identity of a prepared seed, for its BOTW slot."""
    report = folder / "analysis.json"
    return load_seed(report, seed_slot(report))


def select_pack(folder: Path, pack: Path) -> None:
    pack = pack.resolve()
    if not pack.is_relative_to(DATA.resolve()):
        raise ValueError(f"selected play pack must be inside the data folder: {DATA}")
    verify_pack(pack, seed_binding(folder))
    raw = encode({"schema": 2, "pack": pack.relative_to(DATA.resolve()).as_posix(),
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
        raise RuntimeError("no pack selected for this seed; prepare the seed with tools/play_seed.py")
    data = json.loads(pointer.read_text(encoding="utf-8"))
    # Schema 1, written by source checkouts before the data folder, is
    # relative to the project.
    base = {1: ROOT, 2: DATA}.get(data.get("schema"))
    pack = (base / data["pack"]).resolve() if base is not None else None
    if pack is None or not pack.is_relative_to(base.resolve()):
        raise ValueError("invalid play pack selection")
    if digest((pack / "manifest.json").read_bytes()) != data["manifest_sha256"]:
        raise ValueError("selected pack manifest changed")
    verify_pack(pack, seed_binding(folder))
    return pack
