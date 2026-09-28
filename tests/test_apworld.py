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
        self.assertEqual(counts[:2], ["36", "212"])
        self.assertIn("botw.apworld", counts[2])


if __name__ == "__main__":
    unittest.main()
