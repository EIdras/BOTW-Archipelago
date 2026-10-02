"""The isolated Cemu profile that play sessions run in.

    python tools/cemu_profile.py --cemu <Cemu.exe> [--user-data <Cemu user folder>]

Creating it copies, once, the Cemu executable, the BOTW EUR update and DLC, the
BOTW saves and the accounts of an existing Cemu installation, found and checked
by tools/cemu_install.py, into cemu-validation/ of the data folder
(botw_client/paths.py): nothing links back to the installation, which is never
modified. An existing profile is never reset. The base game is not copied:
Cemu launches it where it is.

A play session (tools/play_session.py) then uses its own Cemu account
(PLAY_ACCOUNT), derived from the copied one (SOURCE_ACCOUNT), so that a new
game never overwrites the copied saves, and a single graphic pack: the
verified pack of its seed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botw_client.paths import DATA  # noqa: E402
from tools import cemu_install  # noqa: E402
from tools.cemu_install import CemuInstall  # noqa: E402

PROFILE = DATA / "cemu-validation"
PORTABLE = PROFILE / "portable"
SOURCE_ACCOUNT = 0x80000001     # the account copied from the Cemu installation
PLAY_ACCOUNT = 0x80000003       # the account of play sessions
SAVES = PORTABLE / "mlc01/usr/save/00050000/101c9500/user"
ACCOUNTS = PORTABLE / "mlc01/usr/save/system/act"
PACK_PREFIX = "AP_Ledger_"


def create(executable: Path, install: CemuInstall | None = None, target: Path = PROFILE) -> Path:
    """Copy what BOTW needs from a Cemu installation into a new profile."""
    target = target.resolve()
    if not target.is_relative_to(DATA.resolve()):
        raise ValueError(f"the profile must be inside the data folder: {DATA}")
    if target.exists():
        raise FileExistsError(f"the profile already exists; refusing to reset it: {target}")
    if not executable.is_file():
        raise FileNotFoundError(f"Cemu.exe not found: {executable}")
    install = install or cemu_install.detect(executable)
    mlc, user_data = install.mlc, install.user_data
    # The update and DLC wherever Cemu has them, the game's saves and the
    # accounts (the play account is derived from the first one) from mlc01.
    copies = {install.update: "usr/title/0005000e/101c9500", install.dlc: "usr/title/0005000c/101c9500",
              mlc / "usr/save/00050000/101c9500": "usr/save/00050000/101c9500",
              mlc / "usr/save/system/act": "usr/save/system/act", mlc / "sys": "sys"}
    portable = target / "portable"
    portable.mkdir(parents=True)
    shutil.copy2(executable, target / "Cemu.exe")
    for name in ("resources", "gameProfiles"):
        if (executable.parent / name).is_dir():
            shutil.copytree(executable.parent / name, target / name)
    for source, name in copies.items():
        if source.exists():
            print(f"Copying {name}...", flush=True)
            shutil.copytree(source, portable / "mlc01" / name)
    for name in ("controllerProfiles",):
        if (user_data / name).exists():
            shutil.copytree(user_data / name, portable / name)
    # Keep graphics and input preferences, but never let this configuration
    # point back to the installation's saves, nor load its graphic packs.
    settings = ET.parse(user_data / "settings.xml")
    config = settings.getroot()
    if config.find("mlc_path") is None:
        ET.SubElement(config, "mlc_path")
    config.find("mlc_path").text = (portable / "mlc01").as_posix()
    packs = config.find("GraphicPack")
    if packs is not None:
        packs.clear()
    settings.write(portable / "settings.xml", encoding="utf-8", xml_declaration=True)
    saves = mlc / "usr/save/00050000/101c9500"
    manifest = {"schema": 1, "source_cemu": str(executable.resolve()),
                "source_user_data": str(user_data.resolve()), "game": str(install.game),
                "source_save_hashes": {
                    path.relative_to(saves).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in sorted(saves.rglob("*")) if path.is_file()}}
    (target / "isolation.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Isolated Cemu profile ready: {target}")
    return target


def game() -> Path:
    """What Cemu launches: the game found when the profile was made, else
    found again in the installation it was copied from."""
    manifest = json.loads((PROFILE / "isolation.json").read_text(encoding="utf-8"))
    recorded = manifest.get("game")
    if recorded and Path(recorded).exists():
        return Path(recorded)
    return cemu_install.base_game(Path(manifest["source_user_data"]))


def update() -> Path:
    """The profile's copy of the update, which packs are built from."""
    return PORTABLE / "mlc01/usr/title/0005000e/101c9500"


def check_isolated() -> None:
    """The profile exists and no link leads out of it; Cemu is not running."""
    if not (PROFILE / "isolation.json").is_file():
        raise RuntimeError("No Cemu profile: run tools/cemu_profile.py")
    for path in (PROFILE, PORTABLE, PORTABLE / "settings.xml", PORTABLE / "mlc01",
                 PORTABLE / "mlc01/usr/save"):
        if (not path.resolve().is_relative_to(PROFILE.resolve()) or path.is_symlink()
                or path.is_junction()):
            raise RuntimeError(f"Profile path not isolated: {path}")
    running = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-Process Cemu -ErrorAction SilentlyContinue "
                              "| Select-Object -ExpandProperty Id"],
                             capture_output=True, text=True, check=False)
    if running.stdout.strip():
        raise RuntimeError("Close Cemu before preparing a session "
                           "(no process is stopped automatically).")


def play_account_dat(source_account: str) -> str:
    """account.dat of the play account, derived from the copied one."""
    lines = source_account.splitlines()
    fields = dict(line.split("=", 1) for line in lines[1:] if "=" in line)
    if fields.get("PersistentId") != f"{SOURCE_ACCOUNT:08x}":
        raise ValueError("unexpected copied account")
    suffix = f"{PLAY_ACCOUNT & 0xFFFFFF:06x}"
    out = []
    for line in lines:
        key = line.split("=", 1)[0]
        if key == "PersistentId":
            line = f"PersistentId={PLAY_ACCOUNT:08x}"
        elif key == "TransferableIdBase":
            line = f"TransferableIdBase={fields[key][:-6]}{suffix}"
        elif key == "Uuid":
            line = f"Uuid={fields[key][:-6]}{suffix}"
        out.append(line)
    return "\n".join(out) + "\n"


def ensure_play_account() -> dict:
    """Create the play account in the profile if it is absent."""
    folder = ACCOUNTS / f"{PLAY_ACCOUNT:08x}"
    target = folder / "account.dat"
    if not target.resolve().is_relative_to(PROFILE.resolve()):
        raise RuntimeError("play account outside the profile")
    created = False
    if not target.is_file():
        raw = (ACCOUNTS / f"{SOURCE_ACCOUNT:08x}" / "account.dat").read_bytes()
        folder.mkdir(parents=True, exist_ok=True)
        text = play_account_dat(raw.decode("utf-8").replace("\r\n", "\n"))
        if b"\r\n" in raw:          # keep Cemu's own line endings
            text = text.replace("\n", "\r\n")
        target.write_bytes(text.encode("utf-8"))
        created = True
    return {"account": f"{PLAY_ACCOUNT:08x}", "created": created,
            "account_dat_sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


def prepare_play(pack: Path) -> Path:
    """Install a verified seed pack as the profile's only graphic pack, on the
    play account. Returns the portable folder Cemu runs from."""
    from tools.build_pack_from_source import verify_pack
    check_isolated()
    manifest = verify_pack(pack)
    if "patch_apInject.asm" not in manifest["native_files"]:
        raise RuntimeError("the pack lacks the base injection")
    settings = ET.parse(PORTABLE / "settings.xml")
    root = settings.getroot()
    root.find("mlc_path").text = (PORTABLE / "mlc01").as_posix()
    account = root.find("Account")
    if account is None:
        account = ET.SubElement(root, "Account")
    persistent = account.find("PersistentId")
    if persistent is None:
        persistent = ET.SubElement(account, "PersistentId")
    persistent.text = str(PLAY_ACCOUNT)
    packs = root.find("GraphicPack")
    if packs is None:
        packs = ET.SubElement(root, "GraphicPack")
    packs.clear()
    destination = PORTABLE / "graphicPacks" / (PACK_PREFIX + pack.name)
    if not destination.exists():
        shutil.copytree(pack, destination)
    # An installed copy is checked like the pack itself: any change refuses it.
    verify_pack(destination, manifest["seed_binding"])
    ET.SubElement(packs, "Entry", filename=f"graphicPacks/{destination.name}/rules.txt")
    settings.write(PORTABLE / "settings.xml", encoding="utf-8", xml_declaration=True)
    return PORTABLE


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cemu", type=Path, required=True, help="Cemu.exe of the installation")
    parser.add_argument("--user-data", type=Path,
                        help="Cemu's user folder (the one holding settings.xml), when it is not found")
    parser.add_argument("--output", type=Path, default=PROFILE)
    arguments = parser.parse_args()
    try:
        found = cemu_install.detect(arguments.cemu, arguments.user_data)
    except cemu_install.CemuInstallError as exc:
        raise SystemExit(str(exc))
    create(arguments.cemu, found, arguments.output)
