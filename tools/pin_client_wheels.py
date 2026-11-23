"""Pin the libraries the client downloads inside Archipelago (botw_world/client/wheels.json).

    python tools/pin_client_wheels.py [name==version ...]

Archipelago installs nothing for a world: the client downloads, once, the
wheels of the libraries Archipelago lacks, for the Python Archipelago runs.
This writes, for each library and each Python a release supports, the wheel's
file name, URL, size and sha256 as PyPI publishes them; the client downloads
that URL and accepts nothing else. Run it when a version changes (a name==version
argument), or when a new Python is to be supported (PYTHONS).
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / "botw_world/client/wheels.json"
PYTHONS = ("cp313", "cp314")
PLATFORM = "win_amd64"
HOSTS = ("https://files.pythonhosted.org/",)


def _release(name: str, version: str) -> list[dict]:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as response:
        return json.load(response)["urls"]


def _pick(files: list[dict], python: str) -> dict | None:
    for suffix in (f"-{python}-{python}-{PLATFORM}.whl", f"-abi3-{PLATFORM}.whl", "-py3-none-any.whl"):
        found = [entry for entry in files if entry["filename"].endswith(suffix) and not entry.get("yanked")]
        if found:
            return found[0]
    return None


def pin(versions: dict[str, str]) -> dict:
    pinned = {}
    for name, version in versions.items():
        files = _release(name, version)
        wheels = {}
        for python in PYTHONS:
            entry = _pick(files, python)
            if entry is None:
                raise SystemExit(f"Error: no {name} {version} wheel for {python} {PLATFORM}")
            if not entry["url"].startswith(HOSTS):
                raise SystemExit(f"Error: {entry['url']} is not on PyPI's file host")
            wheels[python] = {"file": entry["filename"], "url": entry["url"], "size": entry["size"],
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
    content = {"platform": PLATFORM, "libraries": pin(versions)}
    PINS.parent.mkdir(parents=True, exist_ok=True)
    PINS.write_bytes((json.dumps(content, indent=2) + "\n").encode("utf-8"))
    for name, entry in content["libraries"].items():
        print(f"{name} {entry['version']}: {', '.join(entry['wheels'])}")


if __name__ == "__main__":
    main(sys.argv[1:])
