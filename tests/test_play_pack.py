import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from tests.test_pack_from_source import write_seed
from tools import play_seed, play_pack


class PreparationTests(unittest.TestCase):
    def test_new_seed_is_identified_then_built_and_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report, archive = write_seed(root)
            data = json.loads(report.read_text())
            identity = data["delivery"]["sessions"]["1"]
            with patch.object(play_seed, "PLAY_SEEDS", root / "play"), \
                    patch.object(play_seed, "audit_zip", return_value=data["audit"]), \
                    patch.object(play_seed, "identify", new_callable=AsyncMock, return_value=identity) as identify, \
                    patch("tools.build_pack_from_source.build", return_value=root / "pack") as build, \
                    patch("tools.play_pack.select_pack") as select:
                new_report, pack = play_seed.prepare(archive, content=root / "dump", rpx=root / "game.rpx")
                identify.assert_awaited_once_with(new_report.parent / archive.name, "Simon")
                build.assert_called_once()
                select.assert_called_once_with(new_report.parent, pack)
                self.assertEqual(play_pack.load_seed(new_report, 1)["token"], identity["token"])

    def test_existing_progress_is_not_reidentified_and_uses_source_builder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "test-seed"
            folder.mkdir()
            report, archive = write_seed(folder)
            original = report.read_bytes()
            (folder / "seed.apsave").write_bytes(b"server progress")
            audit = json.loads(original)["audit"]
            with patch.object(play_seed, "PLAY_SEEDS", root), \
                    patch.object(play_seed, "audit_zip", return_value=audit), \
                    patch.object(play_seed, "identify", new_callable=AsyncMock) as identify, \
                    patch("tools.build_pack_from_source.build", return_value=root / "pack") as build, \
                    patch("tools.play_pack.select_pack") as select:
                result = play_seed.prepare(archive, content=root / "dump", rpx=root / "game.rpx")
                identify.assert_not_called()
                build.assert_called_once_with(root / "dump", root / "game.rpx", report, 1,
                                               play_seed.ROOT / ".build/packs-from-source",
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
            with patch.object(play_seed, "PLAY_SEEDS", root), \
                    patch.object(play_seed, "audit_zip", return_value=json.loads(report.read_text())["audit"]), \
                    patch("tools.build_pack_from_source.build", side_effect=ValueError("bad dump")), \
                    patch("tools.play_pack.select_pack") as select:
                with self.assertRaisesRegex(ValueError, "bad dump"):
                    play_seed.prepare(archive, content=root, rpx=root / "game.rpx")
                select.assert_not_called()
            self.assertEqual(pointer.read_bytes(), b"previous selection")


class SelectionTests(unittest.TestCase):
    def test_no_implicit_fallback_without_selection(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, "aucun pack sélectionné"):
                play_pack.selected_pack(Path(temp))

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
