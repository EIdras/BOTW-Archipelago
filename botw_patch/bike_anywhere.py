"""The Master Cycle Zero anywhere outdoors (the world's bike_anywhere option).

* Native, a patch group after the injection's. Summoning the cycle (the rune at
  0x02D1325C) and riding it ask 0x02A329A0 whether a spot allows it: it refuses an
  indoor spot, and the climates (ksys::world::Climate) of the Gerudo Desert
  (GerudoDesertClimate 5, GerudoDesertClimateLv2 19) and of Death Mountain
  (EldinClimateLv1 13, EldinClimateLv2 14), read at 0x02A329FC by 0x036728C0. That
  call now reads climate 0, Hyrule Field's; indoors stay refused.
* Resources. The horse-only walls (AirWallHorse at the desert's and some villages'
  entrances, AirWallHorse_HiddnKorok around hidden Koroks) stop the cycle as well,
  unless the actor carries the tag IsDisableContactMotorcycle that the cycle's contact
  filter reads (0x020AD164) in its ActorLink, as AirWallHorseExceptMotorcycle does.
  The tag goes into the walls' actor packs and their ActorInfo entries.

Not lifted: the cycle flying from an allowed spot onto a forbidden climate throws Link
off just before it lands. Its cause is not found.
"""
from __future__ import annotations

import oead

from botw_patch.resources import unpack

MODULE = 0x6267BFD0     # moduleMatches of the v208 executable, in every version
GROUP = "BOTW_AP_BikeAnywhere_V208"
CLIMATE_CALL = 0x02A329FC
NATIVE = f"[{GROUP}]\nmoduleMatches = 0x{MODULE:08X}\n0x{CLIMATE_CALL:08X} = li r3, 0\n"
ACTOR_INFO = "Actor/ActorInfo.product.sbyml"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
WALLS = ("AirWallHorse", "AirWallHorse_HiddnKorok")
TAG = "IsDisableContactMotorcycle"
TAG_HASH = 0x8548144D   # crc32 of TAG
SOURCE_FILES = ("botw_patch/bike_anywhere.py",)


def enabled(status: dict | None) -> bool:
    """The slot asks for the cycle anywhere (the world's bike_anywhere)."""
    return bool(status and status.get("slot_data", {}).get("bike_anywhere"))


def patch_injection(text: str) -> str:
    """The injection with the climate patch group after its own."""
    if GROUP in text:
        raise ValueError("parent injection already has the cycle anywhere")
    return text.rstrip("\n") + "\n\n" + NATIVE


def _link(sarc, wall: str):
    return oead.aamp.ParameterIO.from_binary(bytes(sarc.get_file(f"Actor/ActorLink/{wall}.bxml").data))


def lets_through(raw: bytes, wall: str) -> bool:
    """The wall's actor pack already carries the tag."""
    return TAG in [str(p.v) for p in _link(oead.Sarc(unpack(raw)), wall).objects["Tags"].params.values()]


def wall_pack(raw: bytes, wall: str, sizes) -> bytes:
    """The wall's actor pack with the tag in its ActorLink. The link and the pack must
    fit their sizes in the resource size table `sizes`, which stays as it is."""
    if lets_through(raw, wall):
        raise ValueError(f"{wall} already lets the cycle through")
    sarc = oead.Sarc(unpack(raw))
    name = f"Actor/ActorLink/{wall}.bxml"
    link = _link(sarc, wall)
    tags = link.objects["Tags"].params
    tags[f"Tag{len(tags)}"] = oead.aamp.Parameter(TAG)
    data = bytes(link.to_binary())
    writer = oead.SarcWriter.from_sarc(sarc)
    writer.files[name] = data
    archive = bytes(writer.write()[1])
    for resource, size in ((name, len(data)), (f"Actor/Pack/{wall}.bactorpack", len(archive))):
        room = sizes.get_size(resource)
        if not room or size > room:
            raise ValueError(f"{resource}: {size} bytes do not fit the {room} of the resource size table")
    return bytes(oead.yaz0.compress(archive))


def tag_actor_info(raw: bytes) -> bytes:
    """ActorInfo with the tag in the walls' entries."""
    info = oead.byml.from_binary(unpack(raw))
    walls = [actor for actor in info["Actors"] if str(actor["name"]) in WALLS]
    if len(walls) != len(WALLS):
        raise ValueError("the horse-only walls are not all declared")
    for actor in walls:
        actor["tags"][f"tag{TAG_HASH:08x}"] = oead.U32(TAG_HASH)
    return bytes(oead.yaz0.compress(oead.byml.to_binary(info, big_endian=True)))


def generate(files: dict[str, bytes], content) -> tuple[dict[str, bytes], list[dict]]:
    """The walls' actor packs and ActorInfo, after the quest stage (ActorInfo and the
    size table are read from `files`).
    content: the update folder, or the game's files (botw_patch/game_files.py)."""
    import rstb
    from botw_patch.game_files import GameFiles
    game = GameFiles.of(content)
    for name in (ACTOR_INFO, TABLE):
        if name not in files:
            raise ValueError(f"{name} expected in the overlay")
    sizes = rstb.ResourceSizeTable(unpack(files[TABLE]), True)
    files = dict(files)
    files[ACTOR_INFO] = tag_actor_info(files[ACTOR_INFO])
    changes = [{"resource": ACTOR_INFO, "cycle_through": list(WALLS)}]
    for wall in WALLS:
        name = f"Actor/Pack/{wall}.sbactorpack"
        files[name] = wall_pack(files[name] if name in files else game.read(name), wall, sizes)
        changes.append({"resource": name, "tag": TAG})
    return files, changes
