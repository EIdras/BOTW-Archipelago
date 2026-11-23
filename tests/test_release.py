"""The release (tools/build_release.py): botw.apworld, whose client carries
what the player's tools need, Archipelago and the pinned libraries giving the rest."""
import ast
import io
import json
from pathlib import Path
import sys
import unittest
import zipfile

from tools import build_release
from tools.package_native import PAYLOAD, client_payload

ROOT = Path(__file__).resolve().parents[1]
# Archipelago's own modules: only imported where Archipelago is (a source
# checkout's runtime: generation, the local server, a seed's whole zip; the client).
ARCHIPELAGO = {"Generate", "Main", "MultiServer", "NetUtils", "Utils", "websockets", "worlds"}
# What the installed Archipelago ships that the tools import (its frozen library).
ARCHIPELAGO_SHIPS = {"aiohttp", "certifi"}
PROJECT = {"botw_client", "botw_launcher", "botw_patch", "botw_world", "tools"}
PINS = json.loads((ROOT / "botw_world/client/wheels.json").read_bytes())["libraries"]


def imported(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def requirements() -> dict[str, str]:
    found = {}
    for line in (ROOT / "requirements-player.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            name, _, pinned = line.partition("==")
            found[name.strip().lower()] = pinned.strip()
    return found


class ContentTests(unittest.TestCase):
    files = build_release.project_files(untracked=True)

    def test_every_package_the_shipped_code_imports_is_archipelagos_or_pinned(self):
        local = {path.stem for path in (ROOT / "tools/cemu").glob("*.py")}     # put on sys.path by the client
        names = set().union(*(imported(ROOT / name) for name in self.files if name.endswith(".py")))
        outside = names - set(sys.stdlib_module_names) - local - PROJECT - ARCHIPELAGO
        self.assertEqual(outside, ARCHIPELAGO_SHIPS | set(PINS))

    def test_the_player_gets_the_launcher_and_the_data_not_the_lab_or_the_tests(self):
        for name in ("botw_launcher/__main__.py", "botw_launcher/tk/app.py", "botw_launcher/assets/icon.png",
                     "botw_client/paths.py", "tools/cemu/mailbox.py",
                     "botw_world/data/locations.json", "data/item_map.json", "assets/wiiu/Item_AP.sbitemico",
                     "assets/wiiu/Item_AP_Jewel.sbitemico", "native/cemu/legacy/patch_apInject.asm",
                     "players/BOTW.yaml", "botw_world/docs/setup_en.md", "botw_world/docs/setup_fr.md"):
            self.assertIn(name, self.files)
        self.assertFalse([name for name in self.files if name.startswith(("tests/", "lab/", "botw_world/test", ".build"))])
        self.assertFalse(set(build_release.DEVELOPMENT_ONLY) & set(self.files))     # no cheat in a release

    def test_the_pack_sources_are_all_shipped(self):
        # A pack records the hash of each source it is built from: each must be in the release.
        from tools import build_native_from_source, build_resources_from_source
        from botw_patch import ap_quest, shops, stalls
        sources = {*build_native_from_source.SOURCE_FILES, *build_resources_from_source.SOURCE_FILES,
                   *shops.SOURCE_FILES, *stalls.SOURCE_FILES, *ap_quest.SOURCE_FILES,
                   "tools/build_pack_from_source.py", "botw_client/session.py"}
        self.assertLessEqual(sources, set(self.files))

    def test_the_payload_names_its_version_and_makes_the_tools_write_to_the_players_folder(self):
        payload = zipfile.ZipFile(io.BytesIO(client_payload(build_release.payload_files("abc", untracked=True))))
        marker = json.loads(payload.read(build_release.RELEASE_MARKER))
        self.assertEqual((marker["version"], marker["commit"]), (build_release.version(), "abc"))
        self.assertIn("plays", marker)
        self.assertIn("botw_launcher/tk/app.py", payload.namelist())
        self.assertEqual(PAYLOAD, "client/payload.zip")

    def test_the_version_is_the_worlds(self):
        self.assertRegex(build_release.version(), r"^\d+\.\d+\.\d+$")
        self.assertIn("botw_world/archipelago.json", self.files)


class VersionTests(unittest.TestCase):
    def test_the_client_downloads_the_versions_a_checkout_runs(self):
        pinned = requirements()
        self.assertEqual({name: entry["version"] for name, entry in PINS.items()},
                         {name: pinned[name] for name in PINS})
        self.assertIn("-r requirements-player.txt",
                      (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines())

    def test_the_tag_names_the_version(self):
        build_release.check_tag(f"v{build_release.version()}")
        with self.assertRaisesRegex(RuntimeError, "does not name this version"):
            build_release.check_tag("v0.0.0")


if __name__ == "__main__":
    unittest.main()
