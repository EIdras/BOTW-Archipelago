"""The slot file, what a Breath of the Wild player builds the game pack of a seed from.

An Archipelago player container (".apbotw", worlds.Files.APPlayerContainer): its
archipelago.json names the game and the player, so that a room on archipelago.gg
offers each player their own to download, with the room's address written in as
"server"; its slot.json holds the manifest (placements, shop prices, slot data)
that BOTW Archipelago's tools read (tools/build_pack_from_source.py).
"""
from __future__ import annotations

import json
import zipfile

from worlds.Files import APPlayerContainer

from .catalog import GAME

SLOT_MEMBER = "slot.json"


class BotwSlotFile(APPlayerContainer):
    game = GAME
    patch_file_ending = ".apbotw"

    def __init__(self, manifest: dict, path: str, player: int, player_name: str):
        super().__init__(path, player, player_name)
        self.manifest = manifest

    def write_contents(self, opened_zipfile: zipfile.ZipFile) -> None:
        super().write_contents(opened_zipfile)
        opened_zipfile.writestr(SLOT_MEMBER, json.dumps(self.manifest, indent=2, ensure_ascii=False) + "\n")
