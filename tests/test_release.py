"""The release (tools/build_release.py): what it ships is what the player's tools need."""
import ast
from pathlib import Path
import sys
import unittest

from tools import build_release

ROOT = Path(__file__).resolve().parents[1]
# Archipelago's own modules: only imported where Archipelago is (a source
# checkout's runtime: generation, the local server, a seed's whole zip).
ARCHIPELAGO = {"Generate", "Main", "MultiServer", "NetUtils", "Utils", "websockets", "worlds"}
PROJECT = {"botw_client", "botw_patch", "botw_world", "tools"}


def imported(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


class ContentTests(unittest.TestCase):
    def test_every_package_the_shipped_code_imports_is_shipped(self):
        local = {path.stem for path in (ROOT / "tools/cemu").glob("*.py")}     # put on sys.path by the client
        names = set().union(*(imported(ROOT / name) for name in build_release.project_files()
                              if name.endswith(".py")))
        outside = names - set(sys.stdlib_module_names) - local - PROJECT - ARCHIPELAGO
        self.assertEqual(outside, set(build_release.PACKAGES))

    def test_the_packages_come_with_their_dependencies(self):
        found = build_release.distributions()
        self.assertLessEqual({"oead", "evfl", "rstb", "aiohttp", "numpy", "yarl", "multidict"}, set(found))
        self.assertFalse({"pyyaml", "websockets", "jinja2"} & set(found))      # Archipelago's, not the player's

    def test_the_player_gets_the_launcher_and_the_data_not_the_lab_or_the_tests(self):
        files = build_release.project_files()
        for name in ("BOTW Archipelago.cmd", "tools/launcher.py", "botw_client/paths.py", "tools/cemu/mailbox.py",
                     "botw_world/data/locations.json", "data/item_map.json", "assets/wiiu/Item_AP.sbitemico",
                     "native/cemu/legacy/patch_apInject.asm", "players/BOTW.yaml", "LICENSE"):
            self.assertIn(name, files)
        self.assertFalse([name for name in files if name.startswith(("tests/", "lab/", "botw_world/test", ".build"))])

    def test_the_pack_sources_are_all_shipped(self):
        # A pack records the hash of each source it is built from: each must be in the release.
        from tools import build_native_from_source, build_resources_from_source
        from botw_patch import shops, stalls, status_item
        sources = {*build_native_from_source.SOURCE_FILES, *build_resources_from_source.SOURCE_FILES,
                   *shops.SOURCE_FILES, *stalls.SOURCE_FILES, *status_item.SOURCE_FILES,
                   "tools/build_pack_from_source.py", "botw_client/session.py"}
        self.assertLessEqual(sources, set(build_release.project_files()))

    def test_the_version_is_the_worlds(self):
        self.assertRegex(build_release.version(), r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
