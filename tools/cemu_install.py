"""The player's Cemu installation, and their Breath of the Wild in it.

    python tools/cemu_install.py [--cemu <Cemu.exe>] [--user-data <Cemu user folder>]

Cemu keeps its settings (settings.xml) and the list of the games it found
(title_list_cache.xml: path, format and version of every title) in its user
folder: the "portable" folder next to Cemu.exe when there is one, else
%APPDATA%\\Cemu. The update and the DLC are titles installed in its mlc01
folder (settings.xml can move it); the base game is wherever its game paths
found it, as a folder or a .wud/.wua file.

detect() finds the three titles of a supported version (botw_client/regions.py:
the European one first, then the American and the Japanese ones, unless one is named) and checks
what the game pack is built for: update v208 installed as a folder, whose
U-King.rpx is the expected executable, and the DLC. Every failure says what to do.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from botw_client import regions  # noqa: E402

EUR = regions.EUR.title
BASE, UPDATE, DLC = "00050000", "0005000e", "0005000c"
UPDATE_VERSION = 208
DLC_VERSION = 80                # DLC 3.0, The Champions' Ballad
# Cemu's TitleDataFormat: a folder, a disc image, a Wii U archive.
FOLDER, WUD, WUA = 1, 2, 3


class CemuInstallError(RuntimeError):
    pass


@dataclass(frozen=True)
class Title:
    path: Path
    format: int
    version: int


@dataclass(frozen=True)
class CemuInstall:
    user_data: Path
    mlc: Path
    game: Path          # what Cemu launches (-g): the base game's U-King.rpx, or its .wud/.wua
    update: Path        # the v208 update folder: code/, content/, meta/
    dlc: Path
    region: regions.Region = regions.EUR

    @property
    def content(self) -> Path:
        return self.update / "content"

    @property
    def rpx(self) -> Path:
        return self.update / "code" / "U-King.rpx"


def user_data_of(executable: Path | None = None, environ=os.environ) -> Path:
    """Cemu's user folder: portable next to Cemu.exe, else %APPDATA%\\Cemu."""
    if executable is not None:
        folder = Path(executable).parent
        if (folder / "portable").is_dir():
            return folder / "portable"
        if (folder / "settings.xml").is_file():     # Cemu 1.x kept it next to the executable
            return folder
    appdata = environ.get("APPDATA")
    return (Path(appdata) if appdata else Path.home() / "AppData" / "Roaming") / "Cemu"


def mlc_of(user_data: Path) -> Path:
    settings = user_data / "settings.xml"
    if not settings.is_file():
        raise CemuInstallError(f"Cemu's settings are not in {user_data}: start Cemu once, "
                               "or name its user folder (the one holding settings.xml)")
    configured = ET.parse(settings).getroot().findtext("mlc_path")
    return Path(configured) if configured and configured.strip() else user_data / "mlc01"


def _meta_version(folder: Path) -> int | None:
    meta = folder / "meta" / "meta.xml"
    try:
        return int(ET.parse(meta).getroot().findtext("title_version"))
    except (OSError, ET.ParseError, TypeError, ValueError):
        return None


def titles(user_data: Path, mlc: Path) -> dict[str, Title]:
    """Every title Cemu knows, by lowercase title id: installed in mlc01 first
    (their meta.xml is current), then from its game list."""
    found: dict[str, Title] = {}
    root = mlc / "usr" / "title"
    for kind in (BASE, UPDATE, DLC):
        for folder in (root / kind).glob("*") if (root / kind).is_dir() else ():
            version = _meta_version(folder)
            if version is not None:
                found[kind + folder.name.lower()] = Title(folder, FOLDER, version)
    cache = user_data / "title_list_cache.xml"
    if cache.is_file():
        for entry in ET.parse(cache).getroot().iter("title"):
            try:
                title = Title(Path(entry.findtext("path", "")), int(entry.findtext("format", "0")),
                              int(entry.get("version", "0")))
            except ValueError:
                continue
            found.setdefault(entry.get("titleId", "").lower(), title)
    return found


def _launch_path(base: Title, region: regions.Region) -> Path:
    if base.format == FOLDER:
        rpx = base.path / "code" / "U-King.rpx"
        if rpx.is_file():
            return rpx
    elif base.format in (WUD, WUA) and base.path.is_file():
        return base.path
    raise CemuInstallError(f"Breath of the Wild ({region.key}) is listed by Cemu at {base.path}, but is not "
                           "there any more: start Cemu so that it lists it again")


def base_game(user_data: Path, region: regions.Region = regions.EUR) -> Path:
    """What Cemu launches for Breath of the Wild (`region`): its U-King.rpx or its .wud/.wua."""
    known = titles(user_data, mlc_of(user_data))
    return _base(known, _region(known, region))


def _region(known: dict[str, Title], region: regions.Region | None = None) -> regions.Region:
    """The version played: `region`, else the first supported one Cemu lists,
    one with its update and DLC installed first."""
    if region is not None:
        if BASE + region.title not in known:
            raise CemuInstallError(f"Cemu does not list Breath of the Wild ({region.key}): add the folder "
                                   "holding it to Cemu's game paths, then start the game once")
        return region
    listed = [r for r in regions.REGIONS if BASE + r.title in known]
    if not listed:
        raise CemuInstallError("Cemu does not list Breath of the Wild: add the folder holding it to "
                               "Cemu's game paths, then start the game once")
    complete = [r for r in listed if UPDATE + r.title in known and DLC + r.title in known]
    return (complete or listed)[0]


def _base(known: dict[str, Title], region: regions.Region) -> Path:
    return _launch_path(known[BASE + region.title], region)


def detect(executable: Path | None = None, user_data: Path | None = None,
           environ=os.environ, region: regions.Region | None = None) -> CemuInstall:
    """The Breath of the Wild of a Cemu installation (`region`, else the first
    supported version it has), checked."""
    user_data = Path(user_data) if user_data is not None else user_data_of(executable, environ)
    mlc = mlc_of(user_data)
    known = titles(user_data, mlc)
    region = _region(known, region)
    game = _base(known, region)
    update = known.get(UPDATE + region.title)
    if update is None:
        raise CemuInstallError(f"The update v{UPDATE_VERSION} of Breath of the Wild is not installed in Cemu: "
                               "install it (File > Install game title, update or DLC)")
    if update.version != UPDATE_VERSION:
        raise CemuInstallError(f"Cemu has the update v{update.version} of Breath of the Wild: "
                               f"v{UPDATE_VERSION} (1.5.0) is needed")
    if update.format != FOLDER or not (update.path / "content").is_dir():
        raise CemuInstallError(f"The update of Breath of the Wild must be installed in Cemu (as a folder), "
                               f"not read from an archive: {update.path}")
    dlc = known.get(DLC + region.title)
    if dlc is None or dlc.format != FOLDER or not (dlc.path / "content").is_dir():
        raise CemuInstallError("The DLC of Breath of the Wild is not installed in Cemu: install it "
                               "(File > Install game title, update or DLC)")
    if dlc.version < DLC_VERSION:
        raise CemuInstallError(f"Cemu has the DLC v{dlc.version} of Breath of the Wild: v{DLC_VERSION} "
                               "(DLC 3.0, The Champions' Ballad) is needed")
    install = CemuInstall(user_data, mlc, game, update.path, dlc.path, region)
    check_rpx(install.rpx)
    return install


def check_rpx(rpx: Path) -> None:
    from tools.build_native_from_source import RPX_SHA256
    try:
        digest = hashlib.sha256(rpx.read_bytes()).hexdigest()
    except OSError as exc:
        raise CemuInstallError(f"The game's executable is unreadable: {rpx} ({exc})") from exc
    if digest != RPX_SHA256:
        raise CemuInstallError(f"{rpx} is not the executable of Breath of the Wild v{UPDATE_VERSION}: "
                               "reinstall the update from your console")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cemu", type=Path, help="Cemu.exe (for a portable Cemu)")
    parser.add_argument("--user-data", type=Path, help="Cemu's user folder, the one holding settings.xml")
    parser.add_argument("--region", choices=[r.key for r in regions.REGIONS],
                        help="the version, when Cemu has several")
    arguments = parser.parse_args()
    try:
        found = detect(arguments.cemu, arguments.user_data,
                       region=regions.by_key(arguments.region) if arguments.region else None)
    except CemuInstallError as exc:
        raise SystemExit(str(exc))
    print(f"{'region':>9}: {found.region.name} ({found.region.key})")
    for name in ("user_data", "mlc", "game", "update", "dlc"):
        print(f"{name:>9}: {getattr(found, name)}")
