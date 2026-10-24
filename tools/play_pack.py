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


def selections(seeds: Path) -> set[Path]:
    """The packs the prepared seeds of `seeds` select."""
    found = set()
    for folder in seeds.iterdir() if seeds.is_dir() else ():
        try:
            found.add(selected_pack(folder))
        except (OSError, ValueError, RuntimeError, KeyError):
            continue
    return found


def outdated(pack: Path, layers: list[dict] | None = None, mem2_end: int | None = None) -> list[str]:
    """The sources that changed since the pack was built from them: a new
    version of the project builds it again; so does a profile switched to
    another version of the game (tools/cemu_profile.py --region), and, given
    the graphic packs it must be built over now (`layers`,
    tools/player_packs.py), a change of them, or of the end of the game's
    main memory they give (`mem2_end`, tools/cemu/guest.py)."""
    from tools.cemu.guest import MEM2_END
    from tools import cemu_profile
    manifest = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    built_for = manifest.get("revision", "EUR v208").split()[0]
    changed = [] if built_for == cemu_profile.region().key else [f"built for the {built_for} version"]
    if layers is not None and manifest.get("game_packs", []) != [
            {key: layer[key] for key in ("pack", "priority", "fingerprint")} for layer in layers]:
        changed.append("the mods it is built on")
    if mem2_end is not None and manifest.get("mem2_end", MEM2_END) != mem2_end:
        changed.append("the game's memory")
    for name, recorded in sorted(manifest.get("source_hashes", {}).items()):
        path = ROOT / name
        if not path.is_file() or digest(path.read_bytes()) != recorded:
            changed.append(name)
    return changed


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
