"""Where a seed is played: the room that hosts it, or this computer.

The choice is remembered in the seed's folder (launcher.json), never the
password. A seed can be hosted here when it was prepared from its whole zip and
Archipelago's server is importable (the runtime of a source checkout).
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from tools import play_seed

from . import seeds

FILE = "launcher.json"
LOCAL = "local"             # the "room" recorded for a seed hosted on this computer


@dataclass
class Room:
    address: str = ""               # archipelago.gg:12345
    hosted_here: bool = False
    open_to_network: bool = False   # hosted for the other players too, on every network interface


def normalized(address: str) -> str:
    """The address as the client takes it; ValueError when it is not one."""
    from botw_client.protocol import server_url
    address = address.strip()
    if not address:
        raise ValueError("Type the room's address, as its page shows it: archipelago.gg:12345")
    try:
        server_url(address)
    except ValueError:
        raise ValueError(f"Not a room address: {address}. Type it as the room's page shows it: "
                         "archipelago.gg:12345") from None
    return address


def can_host(seed: seeds.PreparedSeed) -> bool:
    return seed.from_zip and play_seed.archipelago_here()


def remembered(seed: seeds.PreparedSeed) -> Room:
    """The room chosen last time; the first time, the one written in a slot
    file downloaded from the room's page."""
    try:
        saved = json.loads((seed.folder / FILE).read_text(encoding="utf-8"))
        room = str(saved.get("room", ""))
    except (OSError, ValueError, AttributeError):
        return Room(address=_slot_file_room(seed.folder))
    if room.lower() == LOCAL:
        return Room(hosted_here=can_host(seed), open_to_network=bool(saved.get("open")))
    return Room(address=room)


def remember(seed: seeds.PreparedSeed, room: Room) -> None:
    saved = {"room": LOCAL if room.hosted_here else room.address, "open": room.open_to_network}
    (seed.folder / FILE).write_text(json.dumps(saved) + "\n", encoding="utf-8")


def _slot_file_room(folder: Path) -> str:
    from tools.build_pack_from_source import slot_server
    try:
        report = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
        return slot_server(Path(report["archive"])) or ""
    except (OSError, ValueError, KeyError):
        return ""
