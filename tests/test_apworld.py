"""The world as Archipelago uses it: its own tests on the official runtime, and
the packaged botw.apworld imported from its zip."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]

from tools.package_native import CONTAINER_VERSION, package
from tools.prepare_ap_runtime import RUNTIME, sync_world

HAVE_RUNTIME = (RUNTIME / "worlds/AutoWorld.py").is_file()


def run_in_runtime(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *arguments], cwd=RUNTIME, text=True,
                          capture_output=True, timeout=600,
                          env={**os.environ, "SKIP_REQUIREMENTS_UPDATE": "1"})


class PackageTests(unittest.TestCase):
    def test_the_apworld_is_the_world_folder_with_a_complete_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = package(Path(folder) / "botw.apworld")
            with zipfile.ZipFile(archive) as zipped:
                names = set(zipped.namelist())
                manifest = json.loads(zipped.read("botw/archipelago.json"))
        self.assertIn("botw/__init__.py", names)
        self.assertIn("botw/docs/en_Breath of the Wild.md", names)
        self.assertIn("botw/data/locations.json", names)
        self.assertIn("botw/LICENSE", names)
        self.assertTrue(all(name.startswith("botw/") for name in names))
        self.assertFalse([name for name in names if "__pycache__" in name])
        self.assertEqual((manifest["game"], manifest["version"], manifest["compatible_version"]),
                         ("Breath of the Wild", CONTAINER_VERSION, CONTAINER_VERSION))
        self.assertRegex(manifest["world_version"], r"^\d+\.\d+\.\d+$")

    def test_the_folder_manifest_leaves_the_container_fields_to_packaging(self):
        manifest = json.loads((ROOT / "botw_world/archipelago.json").read_text(encoding="utf-8"))
        self.assertNotIn("version", manifest)
        self.assertNotIn("compatible_version", manifest)

    def test_the_package_is_reproducible(self):
        with tempfile.TemporaryDirectory() as folder:
            first = package(Path(folder) / "a.apworld").read_bytes()
            second = package(Path(folder) / "b.apworld").read_bytes()
        self.assertEqual(first, second)


@unittest.skipUnless(HAVE_RUNTIME, "prepare the official AP runtime first (tools/prepare_ap_runtime.py)")
class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sync_world()

    def test_the_world_tests_pass(self):
        result = run_in_runtime("-m", "unittest", "discover", "-s", "worlds/botw/test", "-t", ".")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_the_slot_file_checksum_is_the_clients(self):
        # A pack is bound from the slot file alone: the world must write the
        # checksum the client computes from the DataPackage the server sends.
        script = (
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "import worlds\n"
            "from worlds.botw import BotwWorld\n"
            "from botw_client.session import data_package_checksum\n"
            "package = worlds.network_data_package['games']['Breath of the Wild']\n"
            "served = data_package_checksum('Breath of the Wild',\n"
            "    {v: k for k, v in package['item_name_to_id'].items()}, package['location_name_to_id'])\n"
            "assert BotwWorld.data_package_checksum() == served, (BotwWorld.data_package_checksum(), served)\n"
            "print('same')\n")
        result = run_in_runtime("-c", script, str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("same", result.stdout)

    def test_the_zipped_world_imports_and_reads_its_data(self):
        script = (
            "import sys, zipimport\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "import worlds\n"
            "from worlds.botw import BotwWorld\n"
            "print(len(BotwWorld.item_name_to_id), len(BotwWorld.location_name_to_id), BotwWorld.__file__)\n")
        with tempfile.TemporaryDirectory() as folder:
            archive = package(Path(folder) / "botw.apworld")
            # The runtime's own copy steps aside: the world must come from the zip.
            copy = RUNTIME / "worlds/botw"
            aside = RUNTIME / "worlds/_botw_folder"
            copy.rename(aside)
            try:
                target = RUNTIME / "worlds/botw.apworld"
                target.write_bytes(archive.read_bytes())
                try:
                    result = run_in_runtime("-c", script, str(RUNTIME))
                finally:
                    target.unlink()
            finally:
                aside.rename(copy)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        counts = result.stdout.strip().splitlines()[-1].split()
        self.assertEqual(counts[:2], ["159", "212"])
        self.assertIn("botw.apworld", counts[2])

    def test_a_host_generates_with_the_apworld_and_each_player_prepares_from_their_slot_file(self):
        # The host's way: Archipelago with botw.apworld in custom_worlds, two
        # players. Each slot file must be offered by archipelago.gg's room page
        # (its name gives the slot, as the upload reads it), and bind the same
        # identity as the whole seed.
        from tools import play_seed
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            players, output = folder / "players", folder / "output"
            players.mkdir()
            for name in ("Alice", "Bob"):
                (players / f"{name}.yaml").write_text(
                    f"name: {name}\ngame: Breath of the Wild\nBreath of the Wild:\n  goal: ganon\n",
                    encoding="utf-8")
            archive = package(folder / "botw.apworld")
            copy, aside = RUNTIME / "worlds/botw", RUNTIME / "worlds/_botw_folder"
            custom = RUNTIME / "custom_worlds"
            created = not custom.exists()
            copy.rename(aside)
            try:
                custom.mkdir(exist_ok=True)
                (custom / "botw.apworld").write_bytes(archive.read_bytes())
                try:
                    result = run_in_runtime("Generate.py", "--player_files_path", str(players),
                                            "--outputpath", str(output))
                finally:
                    (custom / "botw.apworld").unlink()
                    if created:
                        custom.rmdir()
            finally:
                aside.rename(copy)
            self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-2000:])
            seed_zip = next(output.glob("AP_*.zip"))
            with zipfile.ZipFile(seed_zip) as zipped:
                slots = sorted(name for name in zipped.namelist() if name.endswith(".apbotw"))
                zipped.extractall(folder / "slots", slots)
            self.assertEqual(len(slots), 2)
            for player, name in enumerate(slots, 1):
                self.assertEqual(name.split(".")[0].split("_", 3)[2], f"P{player}")
                # What the room page asks to offer a download (worlds.Files.is_ap_player_container),
                # and the file ending it serves it with.
                with zipfile.ZipFile(folder / "slots" / name) as container:
                    manifest = json.loads(container.read("archipelago.json"))
                self.assertEqual((manifest["game"], manifest["player"], manifest["patch_file_ending"]),
                                 ("Breath of the Wild", player, ".apbotw"))
                slot_name = ("Alice", "Bob")[player - 1]
                _, alone = play_seed.read_seed(folder / "slots" / name)
                _, whole = play_seed.read_seed(seed_zip, slot_name)
                self.assertEqual(alone, whole)


if __name__ == "__main__":
    unittest.main()
