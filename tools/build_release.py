"""Build a release: the folder a player unzips and runs, and the world for the host.

    python tools/build_release.py [--output dist] [--allow-dirty] [--tag vX.Y.Z]

dist/BOTW-Archipelago-<version>/ holds:
  * python/: the Python this checkout runs on (3.12, Windows, from its base
    installation), with only the packages the player's tools import, copied
    from this environment with their dependencies, at the versions of
    requirements-player.txt (checked);
  * the project's tracked files the player's tools read: botw_client/,
    botw_patch/, tools/, native/, data/, the world's data, the Archipelago
    item's icon and model, the options template players/BOTW.yaml, the
    world's guides (botw_world/docs);
  * BOTW Archipelago.cmd, README.md, LICENSE, and release.json (version,
    commit, Python and packages), whose presence makes the tools write their
    files to the player's data folder (botw_client/paths.py).
It is zipped as dist/BOTW-Archipelago-<version>-Windows.zip, next to
dist/botw.apworld: a name of its own, apart from the source archive GitHub
attaches to every release (BOTW-Archipelago-<version>.zip, without Python).
The version is the project's (botw_client/version.py). A release is made
from committed work: a checkout with changes is refused unless --allow-dirty.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path if Path(p).resolve() != ROOT / "tools"]

from botw_client.paths import RELEASE_MARKER  # noqa: E402
from botw_client.version import VERSION  # noqa: E402

NAME = "BOTW-Archipelago"
# What the player's tools import beyond the standard library (tests/test_release.py).
PACKAGES = ("oead", "evfl", "rstb", "aiohttp", "numpy")
PINS = ROOT / "requirements-player.txt"
PROJECT = ("botw_client", "botw_patch", "tools", "native", "data", "botw_world/data", "botw_world/docs",
           "botw_world/catalog.py",
           "botw_world/archipelago.json", "assets/wiiu",
           "assets/models/ap_item/wiiu", "players/BOTW.yaml", "BOTW Archipelago.cmd", "README.md", "LICENSE")
# Test aids of source checkouts, never in a release: the speed multiplier, the play aids.
DEVELOPMENT_ONLY = ("tools/play_speed.py", "tools/build_plateau_speed.py", "tools/play_aids.py")
PYTHON_FILES = ("python.exe", "pythonw.exe", "python3.dll", f"python3{sys.version_info.minor}.dll",
                "vcruntime140.dll", "vcruntime140_1.dll", "LICENSE.txt")
PYTHON_FOLDERS = ("DLLs", "Lib", "tcl")
# The standard library minus what no player tool uses.
LIB_LEFT_OUT = {"site-packages", "test", "idlelib", "ensurepip", "lib2to3", "turtledemo", "__pycache__"}


def version() -> str:
    return VERSION


def git(*arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout


def project_files() -> list[str]:
    """The tracked files of PROJECT, as they are in the working tree, test aids apart."""
    return sorted(name for name in git("ls-files", "-z", "--", *PROJECT).split("\0")
                  if name and name not in DEVELOPMENT_ONLY)


def _requirement_name(requirement: str) -> str:
    return re.split(r"[\s;<>=!~\[(]", requirement.strip(), maxsplit=1)[0]


def distributions(names=PACKAGES) -> dict:
    """The installed distributions of `names` and of what they require (extras
    apart; a requirement not installed here is not needed here)."""
    from importlib import metadata
    found, todo = {}, list(names)
    while todo:
        name = todo.pop().lower().replace("_", "-")
        if name in found:
            continue
        try:
            distribution = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        found[name] = distribution
        todo.extend(_requirement_name(requirement) for requirement in distribution.requires or []
                    if "extra ==" not in requirement)
    missing = [name for name in names if name.lower() not in found]
    if missing:
        raise RuntimeError(f"not installed in this environment: {', '.join(missing)}")
    return found


def pins(path: Path = PINS) -> dict[str, str]:
    """{name: version} of the pinned requirements."""
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            name, _, pinned = line.partition("==")
            found[name.strip().lower().replace("_", "-")] = pinned.strip()
    return found


def check_pins(found: dict, pinned: dict[str, str]) -> None:
    """The release ships exactly the pinned versions, and nothing unpinned."""
    problems = [f"{name} {distribution.version} installed, {pinned[name]} pinned"
                for name, distribution in found.items() if name in pinned and distribution.version != pinned[name]]
    problems += [f"{name} {distribution.version} is shipped but not pinned"
                 for name, distribution in found.items() if name not in pinned]
    problems += [f"{name}=={pinned[name]} is pinned but not needed" for name in pinned if name not in found]
    if problems:
        raise RuntimeError(f"this environment does not match {PINS.name} "
                           f"(pip install -r {PINS.name}): " + "; ".join(problems))


def copy_python(target: Path) -> None:
    base = Path(sys.base_prefix)
    target.mkdir(parents=True)
    for name in PYTHON_FILES:
        if (base / name).is_file():
            shutil.copy2(base / name, target / name)
    for name in PYTHON_FOLDERS:
        left_out = LIB_LEFT_OUT if name == "Lib" else {"__pycache__"}
        shutil.copytree(base / name, target / name,
                        ignore=lambda folder, names: [n for n in names if n in left_out])


def copy_packages(site: Path) -> dict[str, str]:
    """The packages' installed files into `site`; {name: version}."""
    installed = {}
    found = distributions()
    check_pins(found, pins())
    for name, distribution in sorted(found.items()):
        root = Path(distribution.locate_file(""))
        for file in distribution.files or []:
            source = Path(distribution.locate_file(file))
            if not source.resolve().is_relative_to(root.resolve()) or "__pycache__" in file.parts:
                continue        # scripts outside site-packages, bytecode
            if source.is_file():
                destination = site / file
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        installed[name] = distribution.version
    return installed


def zip_folder(folder: Path, archive: Path) -> Path:
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipped:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zipped.write(path, Path(folder.name, path.relative_to(folder)).as_posix())
    return archive


def check_tag(tag: str) -> None:
    """A release published for a git tag is the version the tag names."""
    if tag != f"v{VERSION}":
        raise RuntimeError(f"the tag {tag} does not name this version, {VERSION}: tag v{VERSION}, "
                           "or change world_version in botw_world/archipelago.json")


def build(output: Path = ROOT / "dist", *, allow_dirty: bool = False) -> Path:
    if sys.platform != "win32" or sys.version_info[:2] != (3, 12):
        raise RuntimeError("a release is built on Windows with Python 3.12, the one it ships")
    dirty = bool(git("status", "--porcelain", "--", *PROJECT).strip())
    if dirty and not allow_dirty:
        raise RuntimeError("the release's files have uncommitted changes: commit them, or --allow-dirty")
    release = output / f"{NAME}-{version()}"
    if release.exists():
        shutil.rmtree(release)
    copy_python(release / "python")
    packages = copy_packages(release / "python/Lib/site-packages")
    for name in project_files():
        destination = release / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    commit = git("rev-parse", "HEAD").strip()
    (release / RELEASE_MARKER).write_text(json.dumps({
        "version": version(), "commit": commit + ("-dirty" if dirty else ""),
        "python": sys.version.split()[0], "packages": packages}, indent=2) + "\n", encoding="utf-8")
    archive = zip_folder(release, output / f"{release.name}-Windows.zip")
    from tools.package_native import package
    package(output / "botw.apworld")
    return archive


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="build from a checkout whose release files have uncommitted changes")
    parser.add_argument("--tag", help="the git tag the release is published for (vX.Y.Z): checked first")
    arguments = parser.parse_args()
    try:
        if arguments.tag:
            check_tag(arguments.tag)
        print(build(arguments.output, allow_dirty=arguments.allow_dirty))
    except RuntimeError as exc:
        raise SystemExit(f"Error: {exc}")
