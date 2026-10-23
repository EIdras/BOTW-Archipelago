"""Test aids for the play sessions of source checkouts, to get through the game fast:
Link protected from damage, endless stamina, unbreakable gear, weapons that hit
harder, and a turbo for the whole game. A release never ships them (tools/build_release.py).

Each aid is a graphic pack of its own, enabled next to the seed's pack (which stays
as it was verified):
  * the first three are Cemu community cheats, for the Wii U v208 module only;
  * the damage aid ships a copy of every sword, spear, two-handed weapon and bow
    whose Attack.Power is multiplied. Each still fits its size in the seed pack's
    resource size table, which stays as it is (checked at every build).
    Enemies wielding these weapons hit harder too: it goes with protected Link;
  * the turbo raises the frequency of the vsync Cemu emulates (rules.txt
    [Control] vsyncFrequency, 60 Hz on the Wii U). The game paces its frames on
    that vsync, so all of it runs faster, cutscenes, events and dialogues
    included, as far as the computer can emulate it. No code of the game is
    patched. Its presets offer the other factors in Cemu's graphic pack window.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zlib

MODULE = "0x6267BFD0"           # U-King v208
PREFIX = "AP_Aid_"
# key: (name, original authors, patch)
PATCHES = {
    "Invincible": ("Protected Link (hearts never drop)", "C313571N and Xalphenos",
                   "0x02D452A4 = nop\n"),
    "Stamina": ("Endless stamina", "C313571N and Xalphenos",
                "0x02D90CC0 = fmr f29, f1\n"),
    "Unbreakable": ("Unbreakable gear", "Nopt",
                    ".origin = codecave\n_modifierValue:\n.float 0\n"
                    "0x024ACBF0 = lis r3, _modifierValue@ha\n"
                    "0x024ACBF4 = lfs f31, _modifierValue@l(r3)\n"),
}
DAMAGE = "Damage"
WEAPON_KINDS = ("Sword", "Lsword", "Spear", "Bow", "Goron")
MAX_DAMAGE = 100
TURBO = "Turbo"
WII_U_VSYNC = 60
MAX_TURBO = 8
TURBO_PRESETS = (1, 2, 3, 4, 6, 8)


def turbo_argument(value) -> int:
    import argparse
    try:
        factor = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"turbo: a whole number from 2 to {MAX_TURBO}") from None
    if not 2 <= factor <= MAX_TURBO:
        raise argparse.ArgumentTypeError(f"turbo: a whole number from 2 to {MAX_TURBO}")
    return factor


def turbo_rules(factor: int) -> bytes:
    """The turbo's rules.txt: one preset per factor, `factor` the default one."""
    lines = [_rules(TURBO, "Turbo", f"The whole game x{factor}: emulated vsync at "
                    f"{WII_U_VSYNC * factor} Hz. x1 turns it off.", 7).decode("utf-8"),
             "[Default]", f"$turbo:int = {factor}", ""]
    for preset in sorted({*TURBO_PRESETS, factor}):
        lines += ["[Preset]", f"name = x{preset}" + (" (off)" if preset == 1 else ""),
                  "category = Game speed", *(["default = 1"] if preset == factor else []),
                  f"$turbo:int = {preset}", ""]
    lines += ["[Control]", f"vsyncFrequency = {WII_U_VSYNC} * $turbo", ""]
    return "\n".join(lines).encode("utf-8")


def damage_argument(value) -> int:
    import argparse
    try:
        factor = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"damage: a whole number from 2 to {MAX_DAMAGE}") from None
    if not 2 <= factor <= MAX_DAMAGE:
        raise argparse.ArgumentTypeError(f"damage: a whole number from 2 to {MAX_DAMAGE}")
    return factor


def stronger_weapon(raw: bytes, factor: int, room: int) -> tuple[bytes, int, int] | None:
    """The weapon's actor pack with Attack.Power multiplied, its power before and
    after; None when the pack carries no parameter list of its own. The list is
    written again (AAMP pools equal values: the power may share its bytes with
    other parameters), every other parameter checked unchanged, and the pack
    must fit in `room`, its size in the resource size table."""
    import oead
    sarc = oead.Sarc(oead.yaz0.decompress(raw))
    lists = [f for f in sarc.get_files() if f.name.endswith(".bgparamlist")]
    if not lists:
        return None
    if len(lists) != 1:
        raise ValueError(f"{len(lists)} parameter lists in one weapon")
    parsed = oead.aamp.ParameterIO.from_binary(bytes(lists[0].data))
    before = parsed.objects["Attack"].params["Power"].v
    after = before * factor
    changed = oead.aamp.ParameterIO.from_binary(bytes(lists[0].data))
    changed.objects["Attack"].params["Power"] = oead.aamp.Parameter(oead.S32(after))
    data = bytes(changed.to_binary())
    if _values(oead.aamp.ParameterIO.from_binary(data)) != _values(parsed, after):
        raise ValueError("the power patch changed something else")
    writer = oead.SarcWriter.from_sarc(sarc)
    writer.files[lists[0].name] = data
    archive = bytes(writer.write()[1])
    if len(archive) > room:
        raise ValueError(f"{len(archive)} bytes do not fit the {room} of the resource size table")
    return bytes(oead.yaz0.compress(archive)), before, after


def _values(plist, power: int | None = None, path: str = "") -> dict[str, str]:
    """Every parameter of a parameter list, by its path; Attack.Power replaced by
    `power` when given."""
    out = {}
    for key, obj in plist.objects.items():
        for name, param in obj.params.items():
            value = param.v     # AAMP pools equal values: one patch may reach several
            parts = [getattr(value, axis) for axis in "xyzwrgba" if hasattr(value, axis)]
            out[f"{path}/{key}/{name}"] = repr(parts) if parts else (
                str(value) if "String" in type(value).__name__ else repr(value))
    for key, child in plist.lists.items():
        out.update(_values(child, None, f"{path}/{key}"))
    if power is not None:       # names print as their crc32
        out[f"/{zlib.crc32(b'Attack')}/{zlib.crc32(b'Power')}"] = repr(int(power))
    return out


def _write(folder: Path, files: dict[str, bytes]) -> dict[str, str]:
    hashes = {}
    for name, data in files.items():
        target = folder / name
        if not target.resolve().is_relative_to(folder.resolve()) or target.is_symlink():
            raise RuntimeError(f"aid file outside its pack: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    return hashes


def _rules(key: str, name: str, description: str, version: int) -> bytes:
    return ("[Definition]\n"
            "titleIds = 00050000101C9300,00050000101C9400,00050000101C9500\n"
            f"name = AP test aid - {name}\n"
            f'path = "The Legend of Zelda: Breath of the Wild/AP/Test aids/{key}"\n'
            f"description = {description}\n"
            f"version = {version}\n").encode("utf-8")


def install(graphic_packs: Path, keys: list[str], damage: int, update: Path, table: Path,
            turbo: int = 1) -> list[dict]:
    """Writes the chosen aids into the profile's graphic packs; returns one entry
    per pack (its rules.txt relative to the portable folder). `update` holds the
    game's weapons, `table` is the resource size table the game will load (the
    seed pack's)."""
    entries = []
    if turbo > 1:
        folder = graphic_packs / f"{PREFIX}{TURBO}"
        entries.append({"aid": TURBO, "name": f"Turbo x{turbo}", "factor": turbo,
                        "entry": f"graphicPacks/{folder.name}/rules.txt",
                        "files": _write(folder, {"rules.txt": turbo_rules(turbo)})})
    for key in keys:
        name, author, patch = PATCHES[key]
        folder = graphic_packs / f"{PREFIX}{key}"
        hashes = _write(folder, {
            "rules.txt": _rules(key, name, f"Original by {author}.", 6),
            "patch_aid.asm": f"[BotW_APAid_{key}_V208]\nmoduleMatches = {MODULE}\n{patch}".encode("utf-8"),
        })
        entries.append({"aid": key, "name": name, "entry": f"graphicPacks/{folder.name}/rules.txt",
                        "files": hashes})
    if damage > 1:
        folder = graphic_packs / f"{PREFIX}{DAMAGE}_x{damage}"
        record = folder / "aid.json"
        sources = sorted(p for kind in WEAPON_KINDS for p in (update / "Actor/Pack").glob(f"Weapon_{kind}_*.sbactorpack"))
        source_hash = hashlib.sha256(b"".join(hashlib.sha256(p.read_bytes()).digest()
                                             for p in (*sources, table))).hexdigest()
        built = json.loads(record.read_text(encoding="utf-8")) if record.is_file() else None
        if not built or built.get("source_sha256") != source_hash or not _intact(folder, built["files"]):
            import rstb
            from botw_patch.resources import unpack
            sizes = rstb.ResourceSizeTable(unpack(table.read_bytes()), True)
            files, powers = {}, {}
            for path in sources:
                room = sizes.get_size(f"Actor/Pack/{path.stem}.bactorpack")
                if room is None:
                    raise ValueError(f"{path.name}: no size in the resource size table")
                result = stronger_weapon(path.read_bytes(), damage, room)
                if result:
                    data, before, after = result
                    files[f"content/Actor/Pack/{path.name}"] = data
                    powers[path.stem] = [before, after]
            files["rules.txt"] = _rules(DAMAGE, f"Weapons hit x{damage}",
                                        f"Attack.Power of {len(powers)} weapons multiplied by {damage}.", 7)
            built = {"factor": damage, "source_sha256": source_hash, "powers": powers}
            built["files"] = _write(folder, files)
            record.write_text(json.dumps(built, indent=1), encoding="utf-8")
        entries.append({"aid": DAMAGE, "name": f"Weapons hit x{damage}", "weapons": len(built["powers"]),
                        "entry": f"graphicPacks/{folder.name}/rules.txt", "files": built["files"]})
    return entries


def _intact(folder: Path, hashes: dict[str, str]) -> bool:
    return all((folder / name).is_file() and hashlib.sha256((folder / name).read_bytes()).hexdigest() == sha
               for name, sha in hashes.items())


def enable(portable: Path, entries: list[dict]) -> None:
    """Adds the aid packs after the ones settings.xml already enables."""
    settings = ET.parse(portable / "settings.xml")
    packs = settings.getroot().find("GraphicPack")
    for entry in entries:
        ET.SubElement(packs, "Entry", filename=entry["entry"])
    settings.write(portable / "settings.xml", encoding="utf-8", xml_declaration=True)
