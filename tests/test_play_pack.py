import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from botw_client.session import session_token
from tests.test_pack_from_source import write_seed
from tools import build_pack_from_source, play_seed, play_pack
from tools.build_resources_from_source import digest, encode


def slot_file(folder, *, name="Player", slot=1, checksum="checksum", **extra):
    """A BOTW slot file, as the world writes it (placements left empty)."""
    manifest = {"schema": 1, "game": "Breath of the Wild", "seed": "test-seed", "slot": slot,
                "slot_name": name, "slot_data": {"world_schema": 4, "client_schema": 3},
                "placements": [], "shops": [], **extra}
    if checksum is not None:
        manifest["data_package_checksum"] = checksum
    manifest["content_sha256"] = digest(json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                                                   separators=(",", ":")).encode())
    path = folder / f"AP_test-seed_P{slot}_{name}.apbotw.json"
    path.write_bytes(encode(manifest))
    return path


class SlotFileTests(unittest.TestCase):
    """A seed hosted elsewhere (archipelago.gg): the slot file alone binds the pack."""

    def read(self, path, name=None):
        with patch.object(play_seed, "expected_placements", return_value=0):
            return play_seed.read_seed(path, name)

    def test_the_slot_file_gives_the_servers_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            audit, identity = self.read(slot_file(Path(temp), slot=3, name="Simon"))
        self.assertEqual(identity, {"seed": "test-seed", "team": 0, "slot": 3,
                                    "data_package_checksum": "checksum",
                                    "token": session_token(("test-seed", 0, 3, "checksum"))})
        self.assertEqual((audit["slots"], audit["hostable"]), ({"3": "Simon"}, False))

    def test_an_older_slot_file_asks_for_the_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "from its zip"):
                self.read(slot_file(Path(temp), checksum=None))

    def test_an_altered_slot_file_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = slot_file(Path(temp))
            path.write_bytes(path.read_bytes().replace(b'"Player"', b'"Other"'))
            with self.assertRaisesRegex(ValueError, "manifest hash"):
                self.read(path)

    def test_a_zip_with_several_botw_players_needs_a_name(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / "seed.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                for slot, name in ((1, "Alice"), (2, "Bob")):
                    path = slot_file(root, slot=slot, name=name)
                    zipped.writestr(path.name, path.read_bytes())
            with self.assertRaisesRegex(ValueError, "--slot: Alice, Bob"):
                self.read(archive)
            with self.assertRaisesRegex(ValueError, "named Carol"):
                self.read(archive, "Carol")

    def test_a_slot_file_seed_is_prepared_for_its_slot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = slot_file(root, slot=4, name="Simon")
            with patch.object(play_seed, "PLAY_SEEDS", root / "play"), \
                    patch.object(play_seed, "expected_placements", return_value=0), \
                    patch("tools.build_pack_from_source.build", return_value=root / "pack") as build,                     patch("botw_client.gamedata_table.build") as table, \
                    patch("tools.play_pack.select_pack"):
                report, _ = play_seed.prepare(source, content=root / "dump", rpx=root / "game.rpx")
            self.assertEqual(build.call_args.args[3], 4)
            table.assert_called_once_with(root / "dump")     # the flag table, from the same game
            self.assertEqual(build_pack_from_source.seed_slot(report), 4)
            binding = play_pack.load_seed(report, 4)
            self.assertEqual((binding["slot"], binding["slot_name"]), (4, "Simon"))


class PreparationTests(unittest.TestCase):
    def test_new_seed_is_identified_then_built_and_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report, archive = write_seed(root)
            data = json.loads(report.read_text())
            identity = data["delivery"]["sessions"]["1"]
            with patch.object(play_seed, "PLAY_SEEDS", root / "play"), \
                    patch.object(play_seed, "read_seed", return_value=(data["audit"], identity)) as read, \
                    patch("tools.build_pack_from_source.build", return_value=root / "pack") as build,                     patch("botw_client.gamedata_table.build") as table, \
                    patch("tools.play_pack.select_pack") as select:
                new_report, pack = play_seed.prepare(archive, content=root / "dump", rpx=root / "game.rpx")
                read.assert_called_once_with(archive, None)
                build.assert_called_once()
                select.assert_called_once_with(new_report.parent, pack)
                self.assertEqual(play_pack.load_seed(new_report, 1)["token"], identity["token"])

    def test_existing_progress_keeps_its_report_and_uses_source_builder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "test-seed"
            folder.mkdir()
            report, archive = write_seed(folder)
            original = report.read_bytes()
            (folder / "seed.apsave").write_bytes(b"server progress")
            data = json.loads(original)
            with patch.object(play_seed, "PLAY_SEEDS", root), \
                    patch.object(play_seed, "read_seed",
                                 return_value=(data["audit"], data["delivery"]["sessions"]["1"])), \
                    patch("tools.build_pack_from_source.build", return_value=root / "pack") as build,                     patch("botw_client.gamedata_table.build") as table, \
                    patch("tools.play_pack.select_pack") as select:
                result = play_seed.prepare(archive, content=root / "dump", rpx=root / "game.rpx")
                build.assert_called_once_with(root / "dump", root / "game.rpx", report, 1,
                                               play_seed.PACKS,
                                               resource_gate=True, event_gate=True)
                select.assert_called_once_with(folder, root / "pack")
                self.assertEqual(result, (report, root / "pack"))
            self.assertEqual(report.read_bytes(), original)
            self.assertEqual((folder / "seed.apsave").read_bytes(), b"server progress")

    def test_failed_build_does_not_replace_selected_pack(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "test-seed"
            folder.mkdir()
            report, archive = write_seed(folder)
            pointer = folder / "play-pack.json"
            pointer.write_bytes(b"previous selection")
            data = json.loads(report.read_text())
            with patch.object(play_seed, "PLAY_SEEDS", root), \
                    patch.object(play_seed, "read_seed",
                                 return_value=(data["audit"], data["delivery"]["sessions"]["1"])), \
                    patch("tools.build_pack_from_source.build", side_effect=ValueError("bad dump")), \
                    patch("tools.play_pack.select_pack") as select:
                with self.assertRaisesRegex(ValueError, "bad dump"):
                    play_seed.prepare(archive, content=root, rpx=root / "game.rpx")
                select.assert_not_called()
            self.assertEqual(pointer.read_bytes(), b"previous selection")


class SelectionTests(unittest.TestCase):
    def test_no_implicit_fallback_without_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, "no pack selected"):
                play_pack.selected_pack(Path(temp))

    def test_the_selection_is_relative_to_the_data_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp).resolve()
            pack = data / "packs-from-source" / "abc"
            pack.mkdir(parents=True)
            (pack / "manifest.json").write_text("{}")
            folder = data / "play-seeds" / "seed"
            folder.mkdir(parents=True)
            with patch.object(play_pack, "DATA", data), patch.object(play_pack, "verify_pack"),                     patch.object(play_pack, "seed_binding"):
                play_pack.select_pack(folder, pack)
                pointer = json.loads((folder / "play-pack.json").read_text())
                self.assertEqual((pointer["schema"], pointer["pack"]), (2, "packs-from-source/abc"))
                self.assertEqual(play_pack.selected_pack(folder), pack)
                with self.assertRaisesRegex(ValueError, "inside the data folder"):
                    play_pack.select_pack(folder, Path(temp).parent)

    def test_a_checkout_selection_from_before_the_data_folder_still_reads(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            pack = root / ".build/packs-from-source/abc"
            pack.mkdir(parents=True)
            (pack / "manifest.json").write_text("{}")
            (root / "play-pack.json").write_bytes(encode({
                "schema": 1, "pack": ".build/packs-from-source/abc",
                "manifest_sha256": digest(b"{}")}))
            with patch.object(play_pack, "ROOT", root), patch.object(play_pack, "verify_pack"),                     patch.object(play_pack, "seed_binding"):
                self.assertEqual(play_pack.selected_pack(root), pack)

    @unittest.skipUnless((play_pack.ROOT / ".build/packs-from-source/7f24dccb5d326bda").is_dir(),
                         "validated play pack absent")
    def test_real_selection_checks_manifest_and_preserves_report(self):
        import shutil
        candidate = play_pack.ROOT / ".build/packs-from-source/7f24dccb5d326bda"
        report = play_pack.ROOT / ".build/play-seeds/08278964164390492688/analysis.json"
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            shutil.copyfile(report, folder / "analysis.json")
            play_pack.select_pack(folder, candidate)
            self.assertEqual(play_pack.selected_pack(folder), candidate)
            pointer = folder / "play-pack.json"
            data = json.loads(pointer.read_text())
            self.assertFalse(Path(data["pack"]).is_absolute())
            data["manifest_sha256"] = "wrong"
            pointer.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "manifest changed"):
                play_pack.selected_pack(folder)
            self.assertEqual((folder / "analysis.json").read_bytes(), report.read_bytes())
