"""The player's Cemu installation (tools/cemu_install.py) and the profile made from it."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from botw_client import regions
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
        elif base_format == ci.NUS:
            self.base = root / "games" / "BOTW" / "title.tmd"
            self.base.parent.mkdir(parents=True)
            self.base.write_bytes(b"tmd")
            (self.base.parent / "title.tik").write_bytes(b"ticket")
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

    def region_titles(self, region: str) -> Path:
        """Another version's base game, update v208 and DLC, listed beside the first."""
        titles = ET.parse(self.user / "title_list_cache.xml").getroot()
        base = self.base.parent / f"BOTW-{region}"
        (base / "code").mkdir(parents=True)
        (base / "code/U-King.rpx").write_bytes(b"base")
        self.title(titles, ci.BASE + region, base, ci.FOLDER, 0)
        update = self.mlc / "usr/title" / ci.UPDATE / region
        (update / "content/Pack").mkdir(parents=True)
        (update / "code").mkdir(parents=True)
        (update / "code/U-King.rpx").write_bytes(RPX)
        meta(update, 208)
        dlc = self.mlc / "usr/title" / ci.DLC / region
        (dlc / "content").mkdir(parents=True)
        meta(dlc, 80)
        ET.ElementTree(titles).write(self.user / "title_list_cache.xml")
        return update

    @staticmethod
    def title(parent, title_id, path, form, version):
        entry = ET.SubElement(parent, "title", titleId=title_id.upper(), version=str(version))
        ET.SubElement(entry, "path").text = path.as_posix()
        ET.SubElement(entry, "format").text = str(form)


def detect(install: Install):
    with mock.patch("tools.build_native_from_source.RPX_SHA256", hashlib.sha256(RPX).hexdigest()):
        return ci.detect(user_data=install.user)


class ConsoleLanguageTests(unittest.TestCase):
    def test_the_games_language_follows_cemus_console(self):
        # The name a stable gives Epona is the one in the game's language.
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(cemu_profile, "region", lambda: regions.EUR):
            settings = Path(temp) / "settings.xml"
            for value, expected in (("2", "EUfr"), ("1", "EUen"), ("10", "EUru"), ("0", "EUen"), ("x", "EUen")):
                settings.write_text(f"<content><console_language>{value}</console_language></content>",
                                    encoding="utf-8")
                self.assertEqual(cemu_profile.console_language(settings), expected, value)
            self.assertEqual(cemu_profile.console_language(Path(temp) / "missing.xml"), "EUen")

    def test_the_american_version_has_three_languages(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = Path(temp) / "settings.xml"
            with mock.patch.object(cemu_profile, "region", lambda: regions.USA):
                for value, expected in (("2", "USfr"), ("1", "USen"), ("5", "USes"), ("3", "USen"), ("x", "USen")):
                    settings.write_text(f"<content><console_language>{value}</console_language></content>",
                                        encoding="utf-8")
                    self.assertEqual(cemu_profile.console_language(settings), expected, value)

    def test_the_japanese_version_has_one_language(self):
        with tempfile.TemporaryDirectory() as temp:
            settings = Path(temp) / "settings.xml"
            with mock.patch.object(cemu_profile, "region", lambda: regions.JPN):
                for value in ("0", "1", "x"):
                    settings.write_text(f"<content><console_language>{value}</console_language></content>",
                                        encoding="utf-8")
                    self.assertEqual(cemu_profile.console_language(settings), "JPja", value)


class UserFolderTests(unittest.TestCase):
    def test_portable_next_to_the_executable_then_the_roaming_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / "Cemu" / "Cemu.exe"
            exe.parent.mkdir()
            self.assertEqual(ci.user_data_of(exe, {"APPDATA": "C:/Roaming"}, "win32"), Path("C:/Roaming/Cemu"))
            self.assertEqual(ci.data_of(Path("C:/Roaming/Cemu"), {"APPDATA": "C:/Roaming"}, "win32"),
                             Path("C:/Roaming/Cemu"))
            (exe.parent / "settings.xml").write_text("<content/>")
            self.assertEqual(ci.user_data_of(exe, {}), exe.parent)
            (exe.parent / "portable").mkdir()
            self.assertEqual(ci.user_data_of(exe, {}), exe.parent / "portable")
            self.assertEqual(ci.data_of(exe.parent / "portable"), exe.parent / "portable")

    def test_linux_splits_settings_and_data_unless_portable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            environ = {"XDG_CONFIG_HOME": str(root / "config"), "XDG_DATA_HOME": str(root / "data")}
            appimage = root / "Apps" / "Cemu-2.6-x86_64.AppImage"
            appimage.parent.mkdir()
            self.assertEqual(ci.user_data_of(appimage, environ, "linux"), root / "config" / "Cemu")
            self.assertEqual(ci.data_of(root / "config" / "Cemu", environ, "linux"), root / "data" / "Cemu")
            self.assertEqual(ci.user_data_of(None, {}, "linux"), Path.home() / ".config" / "Cemu")
            self.assertEqual(ci.data_of(Path.home() / ".config" / "Cemu", {}, "linux"),
                             Path.home() / ".local" / "share" / "Cemu")
            (appimage.parent / "portable").mkdir()          # next to the AppImage: one folder
            self.assertEqual(ci.user_data_of(appimage, environ, "linux"), appimage.parent / "portable")
            self.assertEqual(ci.data_of(appimage.parent / "portable", environ, "linux"), appimage.parent / "portable")


class DetectionTests(unittest.TestCase):
    def test_a_linux_cemu_with_its_settings_apart_from_its_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data").mkdir()
            install = Install(root / "data")                # mlc01 and the game list: the data folder
            config = root / "config" / "Cemu"
            config.mkdir(parents=True)
            (install.user / "settings.xml").replace(config / "settings.xml")
            environ = {"XDG_CONFIG_HOME": str(root / "config"), "XDG_DATA_HOME": str(root / "data")}
            with mock.patch("tools.build_native_from_source.RPX_SHA256", hashlib.sha256(RPX).hexdigest()):
                found = ci.detect(environ=environ, platform="linux")
            self.assertEqual(found.user_data, config)
            self.assertEqual((found.mlc, found.update, found.dlc), (install.mlc, install.update, install.dlc))
            self.assertEqual(found.game, install.base / "code/U-King.rpx")

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

    def test_a_base_game_in_nus_form_is_launched_by_its_title_tmd(self):
        for region in (ci.EUR, "101c9400", "101c9300"):
            with self.subTest(region=region), tempfile.TemporaryDirectory() as temp:
                install = Install(Path(temp), region=region, base_format=ci.NUS)
                self.assertEqual(detect(install).game, install.base)

    def test_a_base_game_in_an_unknown_form_is_said(self):
        with tempfile.TemporaryDirectory() as temp:
            install = Install(Path(temp), base_format=5)
            with self.assertRaisesRegex(ci.CemuInstallError, "does not know.*format 5"):
                detect(install)

    def test_the_japanese_version_is_found(self):
        with tempfile.TemporaryDirectory() as temp:
            install = Install(Path(temp), region="101c9300")
            self.assertIs(detect(install).region, regions.JPN)

    def test_the_american_version_is_found(self):
        with tempfile.TemporaryDirectory() as temp:
            install = Install(Path(temp), region="101c9400")
            found = detect(install)
            self.assertIs(found.region, regions.USA)
            self.assertEqual((found.update, found.dlc), (install.update, install.dlc))

    def test_with_both_versions_the_european_one_unless_named(self):
        with tempfile.TemporaryDirectory() as temp:
            install = Install(Path(temp))
            us = Install.region_titles(install, "101c9400")
            self.assertIs(detect(install).region, regions.EUR)
            with mock.patch("tools.build_native_from_source.RPX_SHA256", hashlib.sha256(RPX).hexdigest()):
                found = ci.detect(user_data=install.user, region=regions.USA)
            self.assertEqual((found.region, found.update), (regions.USA, us))

    def test_a_complete_version_before_one_without_its_update(self):
        with tempfile.TemporaryDirectory() as temp:
            install = Install(Path(temp), update=None)
            Install.region_titles(install, "101c9400")
            self.assertIs(detect(install).region, regions.USA)

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

    def test_the_profile_runs_the_executable_it_copied(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            found = detect(Install(root, mlc=root / "elsewhere" / "mlc01"))
            data = root / "data"
            (root / "bin").mkdir()
            for platform, source, name in (("win32", "Cemu.exe", "Cemu.exe"),
                                           ("linux", "Cemu-2.6-x86_64.AppImage", "Cemu.AppImage"),
                                           ("linux", "Cemu", "Cemu")):
                exe = root / "bin" / source
                exe.write_bytes(b"cemu")
                with mock.patch.object(cemu_profile, "DATA", data), \
                        mock.patch.object(cemu_profile, "PROFILE", data / source):
                    target = cemu_profile.create(exe, found, data / source, platform)
                    self.assertEqual(json.loads((target / "isolation.json").read_text())["executable"], name)
                    self.assertEqual((target / name).read_bytes(), b"cemu")
                    self.assertEqual(cemu_profile.cemu_executable(), data / source / name)
                if platform == "linux" and os.name == "posix":
                    self.assertTrue(os.access(target / name, os.X_OK), name)

    def test_a_profile_made_before_the_executable_was_recorded_runs_cemu_exe(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / "isolation.json").write_text(json.dumps({"schema": 1}))
            with mock.patch.object(cemu_profile, "PROFILE", Path(temp)):
                self.assertEqual(cemu_profile.cemu_executable(), Path(temp) / "Cemu.exe")

    def test_a_sandboxed_linux_cemu_is_refused(self):
        for path in ("/var/lib/flatpak/app/info.cemu.Cemu/current/active/files/bin/Cemu",
                     "/home/player/.local/share/flatpak/app/info.cemu.Cemu/x/files/bin/Cemu",
                     "/snap/cemu/12/usr/bin/Cemu"):
            with self.assertRaisesRegex(ValueError, "Flatpak or Snap"):
                cemu_profile.check_reachable(Path(path), "linux")
        cemu_profile.check_reachable(Path("/home/player/Apps/Cemu-2.6-x86_64.AppImage"), "linux")
        cemu_profile.check_reachable(Path("C:/snap/Cemu/Cemu.exe"), "win32")

    def test_cemu_starts_without_what_archipelagos_appimage_adds(self):
        appimage = {"PATH": "/usr/bin", "HOME": "/home/player", "APPIMAGE": "/home/player/Apps/Archipelago.AppImage",
                    "APPDIR": "/tmp/.mount_ArchiX1", "ARGV0": "Archipelago.AppImage", "OWD": "/home/player",
                    "LD_LIBRARY_PATH": "/opt/vulkan/lib:/tmp/.mount_ArchiX1/opt/Archipelago/lib"}
        self.assertEqual(cemu_profile.cemu_environment(appimage, "linux"),
                         {"PATH": "/usr/bin", "HOME": "/home/player", "LD_LIBRARY_PATH": "/opt/vulkan/lib"})
        only_archipelago = dict(appimage, LD_LIBRARY_PATH="/tmp/.mount_ArchiX1/opt/Archipelago/lib")
        self.assertEqual(cemu_profile.cemu_environment(only_archipelago, "linux"),
                         {"PATH": "/usr/bin", "HOME": "/home/player"})
        # Its AppRun run from an extracted folder: no APPDIR, the frozen Python's folder tells.
        extracted = {"PATH": "/usr/bin", "LD_LIBRARY_PATH": "/opt/Archipelago/lib"}
        self.assertEqual(cemu_profile.cemu_environment(extracted, "linux", "/opt/Archipelago/ArchipelagoLauncher"),
                         {"PATH": "/usr/bin"})
        # A terminal, a source checkout, Windows: Cemu gets this process's own environment.
        terminal = {"PATH": "/usr/bin", "LD_LIBRARY_PATH": "/opt/vulkan/lib"}
        self.assertIsNone(cemu_profile.cemu_environment(terminal, "linux"))
        self.assertIsNone(cemu_profile.cemu_environment({"PATH": "/usr/bin"}, "linux"))
        self.assertIsNone(cemu_profile.cemu_environment(appimage, "win32"))

    def test_a_cemu_without_a_controller_for_player_1_is_said(self):
        import contextlib
        import io
        for controller in (False, True):
            with self.subTest(controller=controller), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                install = Install(root)
                if controller:
                    (install.user / "controllerProfiles").mkdir()
                    (install.user / cemu_profile.CONTROLLER).write_text("<emulated_controller/>")
                exe = root / "Cemu.exe"
                exe.write_bytes(b"cemu")
                output = io.StringIO()
                with mock.patch.object(cemu_profile, "DATA", root / "data"), contextlib.redirect_stdout(output):
                    target = cemu_profile.create(exe, detect(install), root / "data/profile")
                self.assertEqual((target / "portable" / cemu_profile.CONTROLLER).is_file(), controller)
                self.assertEqual("no controller set up" in output.getvalue(), not controller)

    def test_a_profile_plays_its_version_and_switches_to_another(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            install = Install(root)
            Install.region_titles(install, "101c9400")
            exe = root / "Cemu.exe"
            exe.write_bytes(b"cemu")
            data = root / "data"
            with mock.patch.object(cemu_profile, "DATA", data),                     mock.patch.object(cemu_profile, "PROFILE", data / "profile"),                     mock.patch.object(cemu_profile, "PORTABLE", data / "profile/portable"):
                cemu_profile.create(exe, detect(install), data / "profile")
                self.assertIs(cemu_profile.region(), regions.EUR)
                self.assertEqual(cemu_profile.update(), data / "profile/portable/mlc01/usr/title/0005000e/101c9500")
                self.assertEqual(cemu_profile.SAVES,
                                 data / "profile/portable/mlc01/usr/save/00050000/101c9500/user")
                with mock.patch("tools.build_native_from_source.RPX_SHA256", hashlib.sha256(RPX).hexdigest()):
                    cemu_profile.switch(ci.detect(user_data=install.user, region=regions.USA))
                self.assertIs(cemu_profile.region(), regions.USA)
                self.assertEqual(cemu_profile.update(), data / "profile/portable/mlc01/usr/title/0005000e/101c9400")
                self.assertTrue((cemu_profile.update() / "code/U-King.rpx").is_file())
                self.assertTrue((data / "profile/portable/mlc01/usr/title/0005000e/101c9500").is_dir())
                self.assertEqual(cemu_profile.game(), root / "games/BOTW-101c9400/code/U-King.rpx")

    def test_a_profile_made_before_the_version_was_recorded_is_european(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = Path(temp)
            (profile / "isolation.json").write_text(json.dumps({"game": "x"}))
            with mock.patch.object(cemu_profile, "PROFILE", profile):
                self.assertIs(cemu_profile.region(), regions.EUR)

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
