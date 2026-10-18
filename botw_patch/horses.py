"""The names a stable gives the horses AP delivers, in every language of the game.

A stable registers Epona under her name in the game's language, the one of her
actor (ActorType/Horse.msbt, GameRomHorseEpona_Name: "Épona" in French). The
client writes it itself (botw_client/horse_stable.py), in the language Cemu's
console runs the game in: the delivery catalog carries every language's.
"""
from __future__ import annotations

from pathlib import Path

import oead

from botw_client import regions
from botw_patch.resources import digest, unpack, vanilla_digest
from botw_patch.shop_items import read_labels

HORSES = ("GameRomHorseEpona",)
MESSAGES = "ActorType/Horse.msbt"


def names(content: Path) -> dict[str, dict[str, str]]:
    """{actor: {language: name}} from the update's message archives."""
    from botw_patch.ap_quest import INPUT_HASHES
    hashes = regions.inputs(INPUT_HASHES, content)
    out: dict[str, dict[str, str]] = {actor: {} for actor in HORSES}
    for language in regions.of_content(content).languages:
        name = f"Pack/Bootup_{language}.pack"
        raw = (content / name).read_bytes()
        if vanilla_digest(raw) != hashes[name]:
            raise ValueError(f"unexpected update resource: {name}")
        boot = oead.Sarc(unpack(raw))
        archive = oead.Sarc(unpack(bytes(boot.get_file(f"Message/Msg_{language}.product.ssarc").data)))
        labels = read_labels(bytes(archive.get_file(MESSAGES).data))
        for actor in HORSES:
            text = labels.get(f"{actor}_Name", "").rstrip("\0")
            if not text or len(text.encode("utf-8")) >= 0x40:
                raise ValueError(f"{language}: no usable name for {actor}: {text!r}")
            out[actor][language] = text
    return out
