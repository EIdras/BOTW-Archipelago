"""Where the tools write their files (botw_client/paths.py)."""
from pathlib import Path
import os
import tempfile
import unittest

from botw_client import paths


class DataFolderTests(unittest.TestCase):
    def test_a_source_checkout_writes_in_its_build_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(paths.data_folder(root, {"LOCALAPPDATA": "C:/Local"}), root / ".build")

    def test_a_release_writes_in_the_local_application_data(self):
        if os.name != 'nt':
            self.skipTest('LOCALAPPDATA is a Windows environment variable')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / paths.RELEASE_MARKER).write_text("{}")
            self.assertEqual(paths.data_folder(root, {"LOCALAPPDATA": "C:/Local"}),
                             Path("C:/Local/BOTW Archipelago"))
            self.assertEqual(paths.data_folder(root, {}),
                             Path.home() / "AppData/Local/BOTW Archipelago")

    def test_a_release_writes_in_the_xdg_data_directory(self):
        if os.name == 'nt':
            self.skipTest('an XDG data directory is a Linux environment')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / paths.RELEASE_MARKER).write_text("{}")
            self.assertEqual(paths.data_folder(root, {}),
                             Path.home() / ".local" / "share" / "BOTW Archipelago")
            self.assertEqual(paths.data_folder(root, {"XDG_DATA_HOME": "/tmp/xdg"}),
                             Path("/tmp/xdg") / "BOTW Archipelago")

    def test_the_variable_names_another_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / paths.RELEASE_MARKER).write_text("{}")
            self.assertEqual(paths.data_folder(root, {paths.DATA_VARIABLE: "D:/AP"}), Path("D:/AP"))

    def test_this_checkout_is_not_a_release(self):
        self.assertFalse((paths.ROOT / paths.RELEASE_MARKER).exists())


if __name__ == "__main__":
    unittest.main()
