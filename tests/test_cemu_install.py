"""The player's Cemu installation (tools/cemu_install.py) and the profile made from it."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from tools import cemu_install as ci
from tools import cemu_profile

RPX = b"the v208 executable"


def meta(folder: Path, version: int) -> None:
    (folder / "meta").mkdir(parents=True, exist_ok=True)
    (folder / "meta/meta.xml").write_text(
        f'<?xml version="1.0"?><menu><title_version type="unsignedInt">{version}</title_version></menu>')


class Install:
    """A Cemu user folder: settings, game list, mlc01 with the update and DLC."""

    def __init__(self, root: Path, *, mlc: Path | None = None, region: str = ci.EUR,
                 update: int | None = 208, dlc: int | None = 80, base_format: int = ci.FOLDER):
        self.user = root / "Cemu"
        self.user.mkdir()
        self.mlc = mlc or self.user / "mlc01"
        settings = ET.Element("content")
        ET.SubElement(settings, "mlc_path").text = mlc.as_posix() if mlc else ""
        ET.SubElement(ET.SubElement(settings, "GraphicPack"), "Entry", filename="graphicPacks/x/rules.txt")
        ET.ElementTree(settings).write(self.user / "settings.xml")
        titles = ET.Element("title_list")
        if base_format == ci.FOLDER:
            self.base = root / "games" / "BOTW"
            (self.base / "code").mkdir(parents=True)
            (self.base / "code/U-King.rpx").write_bytes(b"base")
        else:
            self.base = root / "games" / "BOTW.wua"
            self.base.parent.mkdir(parents=True)
            self.base.write_bytes(b"archive")
        self.title(titles, ci.BASE + region, self.base, base_format, 0)
        self.update = self.mlc / "usr/title" / ci.UPDATE / region
        if update is not None:
            (self.update / "content/Pack").mkdir(parents=True)
            (self.update / "code").mkdir(parents=True)
            (self.update / "code/U-King.rpx").write_bytes(RPX)
            meta(self.update, update)
            self.title(titles, ci.UPDATE + region, self.update, ci.FOLDER, update)
        self.dlc = self.mlc / "usr/title" / ci.DLC / region
        if dlc is not None:
            (self.dlc / "content").mkdir(parents=True)
            meta(self.dlc, dlc)
        save = self.mlc / "usr/save/00050000" / region / "user/80000001"
        save.mkdir(parents=True)
        (save / "game_data.sav").write_bytes(b"save")
        (self.mlc / "usr/save/system/act/80000001").mkdir(parents=True)
        (self.mlc / "usr/save/system/act/80000001/account.dat").write_text("PersistentId=80000001\n")
        ET.ElementTree(titles).write(self.user / "title_list_cache.xml")

    @staticmethod
    def title(parent, title_id, path, form, version):
        entry = ET.SubElement(parent, "title", titleId=title_id.upper(), version=str(version))
        ET.SubElement(entry, "path").text = path.as_posix()
        ET.SubElement(entry, "format").text = str(form)


def detect(install: Install):
    with mock.patch("tools.build_native_from_source.RPX_SHA256", hashlib.sha256(RPX).hexdigest()):
        return ci.detect(user_data=install.user)


class UserFolderTests(unittest.TestCase):
    def test_portable_next_to_the_executable_then_the_roaming_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / "Cemu" / "Cemu.exe"
            exe.parent.mkdir()
            self.assertEqual(ci.user_data_of(exe, {"APPDATA": "C:/Roaming"}), Path("C:/Roaming/Cemu"))
            (exe.parent / "settings.xml").write_text("<content/>")
            self.assertEqual(ci.user_data_of(exe, {}), exe.parent)
            (exe.parent / "portable").mkdir()
            self.assertEqual(ci.user_data_of(exe, {}), exe.parent / "portable")


class DetectionTests(unittest.TestCase):
    def test_the_three_titles_wherever_cemu_has_them(self):
        with tempfile.TemporaryDirectory() as temp:
            install = Install(Path(temp), mlc=Path(temp) / "elsewhere" / "mlc01")
            found = detect(install)
            self.assertEqual((found.mlc, found.update, found.dlc), (install.mlc, install.update, install.dlc))
            self.assertEqual(found.game, install.base / "code/U-King.rpx")
            self.assertEqual((found.content, found.rpx), (install.update / "content",
                                                          install.update / "code/U-King.rpx"))

    def test_a_base_game_archive_is_launched_as_it_is(self):
        with tempfile.TemporaryDirectory() as temp:
            install = Install(Path(temp), base_format=ci.WUA)
            self.assertEqual(detect(install).game, install.base)

    def test_another_region_is_named(self):
        with tempfile.TemporaryDirectory() as temp:
            install = Install(Path(temp), region="101c9400")
            with self.assertRaisesRegex(ci.CemuInstallError, "American .* only the European"):
                detect(install)

    def test_a_game_cemu_does_not_list(self):
        with tempfile.TemporaryDirectory() as temp:
            install = Install(Path(temp))
            (install.user / "title_list_cache.xml").unlink()
            with self.assertRaisesRegex(ci.CemuInstallError, "game paths"):
                detect(install)

    def test_a_listed_game_that_moved(self):
        with tempfile.TemporaryDirectory() as temp:
            install = Install(Path(temp))
            (install.base / "code/U-King.rpx").unlink()
            with self.assertRaisesRegex(ci.CemuInstallError, "not there any more"):
                detect(install)

    def test_the_installed_update_version_wins_over_the_game_list(self):
        with tempfile.TemporaryDirectory() as temp:
            install = Install(Path(temp))
            meta(install.update, 192)       # installed since Cemu listed v208
            with self.assertRaisesRegex(ci.CemuInstallError, "v192 .* v208"):
                detect(install)

    def test_missing_update_or_dlc(self):
        for kwargs, message in (({"update": None}, "update v208 .* not installed"),
                                ({"dlc": None}, "DLC .* not installed"),
                                ({"dlc": 48}, "DLC v48 .* v80")):
            with self.subTest(kwargs), tempfile.TemporaryDirectory() as temp:
                with self.assertRaisesRegex(ci.CemuInstallError, message):
                    detect(Install(Path(temp), **kwargs))

    def test_another_executable_is_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            install = Install(Path(temp))
            with mock.patch("tools.build_native_from_source.RPX_SHA256", "0" * 64):
                with self.assertRaisesRegex(ci.CemuInstallError, "not the executable"):
                    ci.detect(user_data=install.user)

    def test_no_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ci.CemuInstallError, "start Cemu once"):
                ci.detect(user_data=Path(temp))


class ProfileTests(unittest.TestCase):
    def test_the_profile_copies_the_titles_saves_and_accounts_and_records_the_game(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            install = Install(root, mlc=root / "elsewhere" / "mlc01")
            exe = root / "bin" / "Cemu.exe"
            exe.parent.mkdir()
            exe.write_bytes(b"cemu")
            data = root / "data"
            with mock.patch.object(cemu_profile, "DATA", data):
                target = cemu_profile.create(exe, detect(install), data / "profile")
            mlc = target / "portable/mlc01"
            for name in ("usr/title/0005000e/101c9500/content", "usr/title/0005000c/101c9500/content",
                         "usr/save/00050000/101c9500/user/80000001/game_data.sav",
                         "usr/save/system/act/80000001/account.dat"):
                self.assertTrue((mlc / name).exists(), name)
            settings = ET.parse(target / "portable/settings.xml").getroot()
            self.assertEqual(settings.findtext("mlc_path"), mlc.as_posix())
            self.assertEqual(list(settings.find("GraphicPack")), [])
            manifest = json.loads((target / "isolation.json").read_text())
            self.assertEqual(manifest["game"], str(install.base / "code/U-King.rpx"))
            self.assertEqual(list(manifest["source_save_hashes"]), ["user/80000001/game_data.sav"])

    def test_the_game_is_found_again_when_it_moved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            install = Install(root)
            profile = root / "profile"
            profile.mkdir()
            manifest = {"source_user_data": str(install.user), "game": str(root / "gone.rpx")}
            (profile / "isolation.json").write_text(json.dumps(manifest))
            with mock.patch.object(cemu_profile, "PROFILE", profile):
                self.assertEqual(cemu_profile.game(), install.base / "code/U-King.rpx")
                del manifest["game"]        # a profile made before the game was recorded
                (profile / "isolation.json").write_text(json.dumps(manifest))
                self.assertEqual(cemu_profile.game(), install.base / "code/U-King.rpx")


if __name__ == "__main__":
    unittest.main()
