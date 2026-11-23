"""Pin the libraries the client downloads inside Archipelago (botw_world/client/wheels.json).

    python tools/pin_client_wheels.py [name==version ...]

Archipelago installs nothing for a world: the client downloads, once, the
wheels of the libraries Archipelago lacks, for the Python Archipelago runs.
This writes, for each library, each system (PLATFORMS) and each Python a
release supports, the wheel's file name, URL, size and sha256 as PyPI publishes
them; the client downloads that URL and accepts nothing else. Run it when a
version changes (a name==version argument), or when a new Python is to be
supported (PYTHONS).
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / "botw_world/client/wheels.json"
PYTHONS = ("cp313", "cp314")
PLATFORMS = ("win_amd64", "linux_x86_64")       # the client's platform_key()
GLIBC = (2, 35)         # Archipelago's Linux build (Ubuntu 22.04): no wheel may ask for more
HOSTS = ("https://files.pythonhosted.org/",)
LEGACY_LINUX = {"manylinux1_x86_64": (2, 5), "manylinux2010_x86_64": (2, 12), "manylinux2014_x86_64": (2, 17)}


def _release(name: str, version: str) -> list[dict]:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as response:
        return json.load(response)["urls"]


def _floor(tag: str, platform: str) -> tuple[int, int] | None:
    """What a wheel's platform tag asks of `platform` (a Linux wheel's glibc: the
    lower, the more systems it runs on), or None when the tag is not one of
    `platform`'s: musllinux, ARM and 32-bit wheels never are."""
    if platform == "win_amd64":
        return (0, 0) if tag == "win_amd64" else None
    if tag in LEGACY_LINUX:
        return LEGACY_LINUX[tag]
    found = re.fullmatch(r"manylinux_(\d+)_(\d+)_x86_64", tag)
    return (int(found[1]), int(found[2])) if found else None


def _rank(filename: str, python: str, platform: str) -> tuple | None:
    """How well a wheel suits `python` on `platform`, the lower the better: the
    Python's own build, then abi3, then pure Python; None when it does not run
    there (a free-threaded build, among others)."""
    if not filename.endswith(".whl") or filename.count("-") < 4:
        return None
    pythons, abi, tags = filename[:-4].rsplit("-", 3)[1:]
    if (pythons, abi, tags) == ("py3", "none", "any"):
        return (2, (0, 0))
    if abi != "abi3" and (abi, pythons) != (python, python):
        return None
    floors = [floor for floor in (_floor(tag, platform) for tag in tags.split(".")) if floor is not None]
    return (0 if abi == python else 1, min(floors)) if floors else None


def _pick(files: list[dict], python: str, platform: str) -> dict | None:
    ranked = [(rank, entry) for entry in files if not entry.get("yanked")
              if (rank := _rank(entry["filename"], python, platform)) is not None]
    return min(ranked, key=lambda found: found[0])[1] if ranked else None


def pin(versions: dict[str, str]) -> dict:
    pinned = {}
    for name, version in versions.items():
        files = _release(name, version)
        wheels: dict[str, dict] = {}
        for platform in PLATFORMS:
            for python in PYTHONS:
                entry = _pick(files, python, platform)
                if entry is None:
                    raise SystemExit(f"Error: no {name} {version} wheel for {python} {platform}")
                if not entry["url"].startswith(HOSTS):
                    raise SystemExit(f"Error: {entry['url']} is not on PyPI's file host")
                if _rank(entry["filename"], python, platform)[1] > GLIBC:
                    raise SystemExit(f"Error: {entry['filename']} asks for a newer glibc than "
                                     f"Archipelago's Linux build has")
                wheels.setdefault(platform, {})[python] = {
                    "file": entry["filename"], "url": entry["url"], "size": entry["size"],
                    "sha256": entry["digests"]["sha256"]}
        pinned[name] = {"version": version, "wheels": wheels}
    return pinned


def main(arguments: list[str]) -> None:
    current = json.loads(PINS.read_bytes()) if PINS.is_file() else {}
    versions = {name: entry["version"] for name, entry in current.get("libraries", {}).items()}
    for argument in arguments:
        name, _, version = argument.partition("==")
        if not version:
            raise SystemExit(f"Error: {argument!r}: expected name==version")
        versions[name] = version
    if not versions:
        raise SystemExit("Error: nothing to pin")
    content = {"libraries": pin(versions)}
    PINS.parent.mkdir(parents=True, exist_ok=True)
    PINS.write_bytes((json.dumps(content, indent=2) + "\n").encode("utf-8"))
    for name, entry in content["libraries"].items():
        print(f"{name} {entry['version']}: "
              + ", ".join(f"{platform} {' '.join(pythons)}" for platform, pythons in entry["wheels"].items()))


if __name__ == "__main__":
    main(sys.argv[1:])
