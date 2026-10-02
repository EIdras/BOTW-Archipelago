"""The project's version, one for the world, the client and the release: the
world's world_version (botw_world/archipelago.json)."""
from __future__ import annotations

import json

from .paths import ROOT

VERSION = json.loads((ROOT / "botw_world/archipelago.json").read_text(encoding="utf-8"))["world_version"]


def parse(version: str) -> tuple[int, ...]:
    """'1.2.0' -> (1, 2, 0), to compare versions."""
    return tuple(int(part) for part in version.split("."))
