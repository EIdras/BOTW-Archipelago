"""The game's Cemu profile: a copy of the player's Cemu the Archipelago game
runs in, made once (tools/cemu_profile.py). The player's own Cemu is only read.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from tools import cemu_install, cemu_profile

# What the profile copies: Cemu, the update, the DLC and the saves.
EXPECTED_SIZE = 5 * 2**30
CemuInstallError = cemu_install.CemuInstallError


@dataclass(frozen=True)
class Found:
    """What the game needs, found in a Cemu installation."""
    executable: Path
    game: Path
    update: Path
    dlc: Path
    install: cemu_install.CemuInstall


@dataclass(frozen=True)
class Summary:
    folder: Path
    source_cemu: str
    game: str


def exists() -> bool:
    return (cemu_profile.PROFILE / "isolation.json").is_file()


def detect(executable: Path) -> Found:
    """Find the game, its update and its DLC from the player's Cemu; CemuInstallError
    says what is missing."""
    install = cemu_install.detect(executable)
    return Found(executable, install.game, install.update, install.dlc, install)


def create(executable: Path) -> Path:
    return cemu_profile.create(executable, cemu_install.detect(executable))


def summary() -> Summary | None:
    try:
        manifest = json.loads((cemu_profile.PROFILE / "isolation.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return Summary(cemu_profile.PROFILE, manifest.get("source_cemu", ""), manifest.get("game", ""))


def cemu_running() -> bool:
    return cemu_profile.cemu_running()
