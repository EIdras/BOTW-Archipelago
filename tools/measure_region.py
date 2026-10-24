"""Measure another region's update and DLC against the European ones the build pins.

    venv\\Scripts\\python tools\\measure_region.py <region> [--mlc <Cemu mlc01>]

The build reads the game's resources only once it has checked them against the
SHA-256 of the European files (EUR v208). The other versions hold the same data,
compressed apart, so their files' own bytes differ. For each pinned resource
(a hash of the shipped sources found in the European update or DLC, as a file
or a member of an archive), this finds the same resource in the region's game,
checks that its content is the European one once Yaz0 is undone and archives
are opened, and records its hash. The region's language archives, which the
European version has not, are pinned as they are. Writes the region's entry of
data/region_hashes.json (botw_client/regions.py reads it); fails, writing
nothing, when a pinned resource is missing or holds other data.

`contents` writes data/content_hashes.json: the content of every pinned
resource of the European update and DLC (its languages too) and of the other
versions' language archives, with its pinned hash, by which the build knows
the files of another distribution of the game, compressed apart.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import oead  # noqa: E402

from botw_client import regions  # noqa: E402

SOURCES = ("botw_patch", "botw_client", "tools")
KINDS = {"update": "0005000e", "dlc": "0005000c"}


def pins() -> set[str]:
    """Every SHA-256 written in the shipped sources."""
    found = set()
    for folder in SOURCES:
        for path in (ROOT / folder).rglob("*.py"):
            found.update(re.findall(r"['\"]([0-9a-f]{64})['\"]", path.read_text(encoding="utf-8")))
    return found


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _members(data: bytes, prefix: str, out: dict[str, bytes], wanted: set[str]) -> None:
    """Every resource of `data` (itself and its archives' members, at any depth)
    whose hash is wanted, by path."""
    if _sha(data) in wanted:
        out[prefix] = data
    raw = bytes(oead.yaz0.decompress(data)) if data[:4] == b"Yaz0" else data
    if raw[:4] != b"SARC":
        return
    try:
        archive = oead.Sarc(raw)
    except (RuntimeError, ValueError):
        return
    for member in archive.get_files():
        _members(bytes(member.data), f"{prefix}//{member.name}", out, wanted)


def _resource(root: Path, path: str) -> bytes | None:
    """The resource at `path` (file//member//member...) under `root`."""
    file, *members = path.split("//")
    if not (root / file).is_file():
        return None
    data = (root / file).read_bytes()
    for name in members:
        raw = bytes(oead.yaz0.decompress(data)) if data[:4] == b"Yaz0" else data
        member = oead.Sarc(raw).get_file(name)
        if member is None:
            return None
        data = bytes(member.data)
    return data


def measure(region: regions.Region, mlc: Path) -> dict:
    wanted = pins()
    equivalents, languages, problems = {}, {}, []
    for kind, folder in KINDS.items():
        europe = mlc / "usr/title" / folder / regions.EUR.title / "content"
        other = mlc / "usr/title" / folder / region.title / "content"
        if not other.is_dir():
            raise SystemExit(f"{region.name} {kind} not installed in Cemu: {other}")
        found: dict[str, bytes] = {}
        for path in sorted(europe.rglob("*")):
            if path.is_file():
                _members(path.read_bytes(), path.relative_to(europe).as_posix(), found, wanted)
        print(f"{kind}: {len(found)} pinned resources", flush=True)
        for path, data in sorted(found.items()):
            if any(f"_{language}." in path.split("//")[0] for language in regions.EUR.languages):
                continue        # a European language: the region has its own
            theirs = _resource(other, path)
            if theirs is None:
                problems.append(f"missing in {region.key}: {path}")
            elif regions.content_digest(theirs) != regions.content_digest(data):
                problems.append(f"other content in {region.key}: {path}")
            elif _sha(theirs) != _sha(data):
                if equivalents.setdefault(_sha(theirs), _sha(data)) != _sha(data):
                    problems.append(f"one {region.key} file for two European ones: {path}")
                equivalents[_sha(theirs)] = _sha(data)
        if kind == "update":
            for language in region.languages:
                name = f"Pack/Bootup_{language}.pack"
                if not (other / name).is_file():
                    problems.append(f"missing in {region.key}: {name}")
                else:
                    languages[name] = _sha((other / name).read_bytes())
    if problems:
        raise SystemExit("\n".join(problems))
    return {"equivalents": dict(sorted(equivalents.items())), "languages": languages}


def contents(mlc: Path) -> dict[str, str]:
    """{content: pinned hash} of every pinned resource and language archive."""
    wanted, table, problems = pins(), {}, []

    def record(data: bytes, where: str) -> None:
        if table.setdefault(regions.content_digest(data), _sha(data)) != _sha(data):
            problems.append(f"two pinned files hold the content of {where}")

    for kind, folder in KINDS.items():
        europe = mlc / "usr/title" / folder / regions.EUR.title / "content"
        found: dict[str, bytes] = {}
        for path in sorted(europe.rglob("*")):
            if path.is_file():
                _members(path.read_bytes(), path.relative_to(europe).as_posix(), found, wanted)
        print(f"{kind}: {len(found)} pinned resources", flush=True)
        for path, data in sorted(found.items()):
            record(data, path)
    for region in regions.REGIONS[1:]:
        for name, sha in json.loads(regions.HASHES.read_text(encoding="utf-8"))[region.key]["languages"].items():
            path = mlc / "usr/title" / KINDS["update"] / region.title / "content" / name
            if not path.is_file() or _sha(path.read_bytes()) != sha:
                problems.append(f"{region.key} {name} missing or not the pinned one")
            else:
                record(path.read_bytes(), f"{region.key} {name}")
    if problems:
        raise SystemExit("\n".join(problems))
    return dict(sorted(table.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("region", choices=[r.key for r in regions.REGIONS if r is not regions.EUR] + ["contents"])
    parser.add_argument("--mlc", type=Path, default=Path(os.environ.get("APPDATA", "")) / "Cemu/mlc01")
    arguments = parser.parse_args()
    if arguments.region == "contents":
        table = contents(arguments.mlc)
        regions.CONTENTS.write_text(json.dumps(table, indent=1) + "\n", encoding="utf-8")
        print(f"{len(table)} pinned contents -> {regions.CONTENTS}")
        return
    region = regions.by_key(arguments.region)
    entry = measure(region, arguments.mlc)
    table = json.loads(regions.HASHES.read_text(encoding="utf-8")) if regions.HASHES.is_file() else {}
    table[region.key] = entry
    regions.HASHES.write_text(json.dumps(table, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{region.key}: {len(entry['equivalents'])} equivalent resources, "
          f"{len(entry['languages'])} language archives -> {regions.HASHES}")


if __name__ == "__main__":
    main()
