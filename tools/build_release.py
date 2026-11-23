"""Build a release: botw.apworld, the one file a player and a host install.

    python tools/build_release.py [--output dist] [--allow-dirty] [--tag vX.Y.Z]

dist/botw.apworld is the world (tools/package_native.py) and the BOTW
Archipelago window the Archipelago Launcher opens (botw_world/client). The
window's code travels inside it as client/payload.zip:
  * the project's tracked files the player's tools read: botw_launcher/,
    botw_client/, botw_patch/, tools/, native/, data/, the world's data and
    guides, the Archipelago item's icon and model, the options template
    players/BOTW.yaml; never the test aids of a source checkout
    (DEVELOPMENT_ONLY);
  * release.json (version, the seeds it plays, commit), whose presence makes the
    tools write their files to the player's data folder (botw_client/paths.py).
The libraries the tools need beyond Archipelago's (oead, numpy, evfl, rstb) are
not shipped: the window downloads them once, pinned by
botw_world/client/wheels.json (tools/pin_client_wheels.py).

The version is the project's (botw_client/version.py). A release is made from
committed work: a checkout with changes is refused unless --allow-dirty.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path if Path(p).resolve() != ROOT / "tools"]

from botw_client.paths import RELEASE_MARKER  # noqa: E402
from botw_client.version import VERSION  # noqa: E402

PROJECT = ("botw_launcher", "botw_client", "botw_patch", "tools", "native", "data", "botw_world/data",
           "botw_world/docs", "botw_world/catalog.py", "botw_world/archipelago.json", "assets/wiiu",
           "assets/models/ap_item/wiiu", "players/BOTW.yaml")
# Test aids of source checkouts, never in a release: the speed multiplier, the play aids.
DEVELOPMENT_ONLY = ("tools/play_speed.py", "tools/build_plateau_speed.py", "tools/play_aids.py")


def version() -> str:
    return VERSION


def git(*arguments: str) -> str:
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, text=True,
                          check=True).stdout


def project_files(untracked: bool = False) -> list[str]:
    """The tracked files of PROJECT, as they are in the working tree, test aids apart.
    `untracked`: and the new files git does not ignore (a build to try, the tests)."""
    others = ("--cached", "--others", "--exclude-standard") if untracked else ()
    return sorted(name for name in git("ls-files", "-z", *others, "--", *PROJECT).split("\0")
                  if name and name not in DEVELOPMENT_ONLY and (ROOT / name).is_file())


def payload_files(commit: str, untracked: bool = False) -> dict[str, bytes]:
    """The client's payload: the project's files and release.json."""
    from botw_client import compatibility
    files = {name: (ROOT / name).read_bytes() for name in project_files(untracked)}
    files[RELEASE_MARKER] = (json.dumps({"version": version(), compatibility.KEY: compatibility.statement(),
                                         "commit": commit}, indent=2) + "\n").encode("utf-8")
    return files


def check_tag(tag: str) -> None:
    """A release published for a git tag is the version the tag names."""
    if tag != f"v{VERSION}":
        raise RuntimeError(f"the tag {tag} does not name this version, {VERSION}: tag v{VERSION}, "
                           "or change world_version in botw_world/archipelago.json")


def build(output: Path = ROOT / "dist", *, allow_dirty: bool = False) -> Path:
    from tools.package_native import client_payload, package
    dirty = bool(git("status", "--porcelain", "--", *PROJECT, "botw_world").strip())
    if dirty and not allow_dirty:
        raise RuntimeError("the release's files have uncommitted changes: commit them, or --allow-dirty")
    commit = git("rev-parse", "HEAD").strip() + ("-dirty" if dirty else "")
    return package(output / "botw.apworld", client_payload(payload_files(commit)))


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
