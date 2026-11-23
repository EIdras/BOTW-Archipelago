"""Where the tools write their files (botw_client/paths.py)."""
from pathlib import Path
import tempfile
import unittest

from botw_client import paths


class DataFolderTests(unittest.TestCase):
    def test_a_source_checkout_writes_in_its_build_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(paths.data_folder(root, {"LOCALAPPDATA": "C:/Local"}), root / ".build")

    def test_a_release_writes_in_the_local_application_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / paths.RELEASE_MARKER).write_text("{}")
            self.assertEqual(paths.data_folder(root, {"LOCALAPPDATA": "C:/Local"}),
                             Path("C:/Local/BOTW Archipelago"))
            self.assertEqual(paths.data_folder(root, {}),
                             Path.home() / "AppData/Local/BOTW Archipelago")

    def test_off_windows_a_release_writes_in_the_shared_data_folder(self):
        self.assertEqual(paths.default_data_folder({"XDG_DATA_HOME": "/data"}, "linux"),
                         Path("/data/BOTW Archipelago"))
        self.assertEqual(paths.default_data_folder({}, "linux"), Path.home() / ".local/share/BOTW Archipelago")

    def test_a_release_follows_the_folder_the_player_moved_the_data_to(self):
        with tempfile.TemporaryDirectory() as temp:
            root, local = Path(temp) / "release", Path(temp) / "local"
            (local / paths.RELEASE_FOLDER).mkdir(parents=True)
            root.mkdir()
            (root / paths.RELEASE_MARKER).write_text("{}")
            pointer = local / paths.RELEASE_FOLDER / paths.LOCATION_FILE
            pointer.write_text('{"data": "D:/Games/BOTW AP"}')
            self.assertEqual(paths.data_folder(root, {"LOCALAPPDATA": str(local)}), Path("D:/Games/BOTW AP"))
            pointer.write_text("not json")      # unreadable: the default, never an error at start
            self.assertEqual(paths.data_folder(root, {"LOCALAPPDATA": str(local)}), local / paths.RELEASE_FOLDER)

    def test_the_variable_names_another_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / paths.RELEASE_MARKER).write_text("{}")
            self.assertEqual(paths.data_folder(root, {paths.DATA_VARIABLE: "D:/AP"}), Path("D:/AP"))

    def test_this_checkout_is_not_a_release(self):
        self.assertFalse((paths.ROOT / paths.RELEASE_MARKER).exists())


if __name__ == "__main__":
    unittest.main()
