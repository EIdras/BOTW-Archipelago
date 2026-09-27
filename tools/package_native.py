"""Package botw_world/ as botw.apworld, with deterministic ZIP metadata.

    python tools/package_native.py [--output dist/botw.apworld]

Does what Archipelago's "Build APWorlds" launcher component does: the world
folder under the name "botw", and its archipelago.json completed with the
APContainer version fields (worlds/Files.py, container version 7). The
project's LICENSE goes with it: a copy of the world carries its license (GPL).
"""
from pathlib import Path
import argparse
import json
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "botw_world"
LICENSE = ROOT / "LICENSE"
NAME = "botw"
CONTAINER_VERSION = 7          # worlds/Files.py container_version (AP 0.6.x)
SUFFIXES = {".py", ".json", ".md"}


def manifest() -> bytes:
    data = json.loads((SOURCE / "archipelago.json").read_text(encoding="utf-8"))
    for key in ("version", "compatible_version"):
        if key in data:
            raise ValueError(f"archipelago.json must not set {key}: packaging adds it")
    data.update({"version": CONTAINER_VERSION, "compatible_version": CONTAINER_VERSION})
    return (json.dumps(data, indent=2) + "\n").encode("utf-8")


def contents():
    for path in sorted(SOURCE.rglob("*")):
        if not path.is_file() or path.suffix not in SUFFIXES or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(SOURCE).as_posix()
        yield relative, manifest() if relative == "archipelago.json" else path.read_bytes()
    yield "LICENSE", LICENSE.read_bytes()


def package(output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, data in contents():
            entry = zipfile.ZipInfo(f"{NAME}/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, data)
    with zipfile.ZipFile(temp) as archive:
        if archive.testzip():
            raise ValueError("generated archive failed integrity check")
    temp.replace(output)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/botw.apworld")
    print(package(parser.parse_args().output))
