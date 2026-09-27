"""Add the save-backed Archipelago delivery cursor to BOTW's Bootup.pack.

The cursor and seed token deliberately live in GameData and saveformat: when a
BOTW save rolls back, the cursor rolls back with the inventory. The client can
then replay exactly the ReceivedItems entries missing from that save.
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import zlib

import oead

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_PACK = (pathlib.Path.home() / "AppData/Roaming/Cemu/graphicPacks" /
                "BOTW_Archipelago")
DEFAULT_SOURCE = (pathlib.Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title" /
                  "0005000e/101c9500/content/Pack/Bootup.pack")
FLAGS = ("APReceivedCursor", "APSeedToken")


def signed_crc(name: str) -> int:
    value = zlib.crc32(name.encode("utf-8"))
    return value - (1 << 32) if value >= 1 << 31 else value


def open_yaz_sarc(data: bytes) -> oead.Sarc:
    return oead.Sarc(oead.yaz0.decompress(data) if data[:4] == b"Yaz0" else data)


def write_sarc(sarc: oead.Sarc, replacements: dict[str, bytes]) -> bytes:
    writer = oead.SarcWriter.from_sarc(sarc)
    for name, data in replacements.items():
        writer.files[name] = data
    return bytes(writer.write()[1])


def definition(name: str, is_save: bool, kind: str = "s32",
               init: int = 0) -> oead.byml.Hash:
    if kind == "bool":
        # As vanilla IsGet_ flags, but not one-trigger: ours are set back to false.
        return oead.byml.Hash({
            "DataName": name, "DeleteRev": oead.S32(-1),
            "HashValue": oead.S32(signed_crc(name)), "InitValue": oead.S32(int(bool(init))),
            "IsEventAssociated": False, "IsOneTrigger": False,
            "IsProgramReadable": True, "IsProgramWritable": True, "IsSave": is_save,
            "MaxValue": True, "MinValue": False, "ResetType": oead.S32(0),
        })
    return oead.byml.Hash({
        "DataName": name,
        "DeleteRev": oead.S32(-1),
        "HashValue": oead.S32(signed_crc(name)),
        "InitValue": oead.S32(0),
        "IsEventAssociated": False,
        "IsOneTrigger": False,
        "IsProgramReadable": True,
        "IsProgramWritable": True,
        "IsSave": is_save,
        "MaxValue": oead.S32(2147483647),
        "MinValue": oead.S32(0),
        "ResetType": oead.S32(0),
    })


def modify_gamedata_flags(raw: bytes, flags, is_save: bool, kind: str = "s32",
                          init: int = 0) -> bytes:
    """Append flag definitions of `kind` (s32 or bool) to its last page."""
    if kind not in ("s32", "bool"):
        raise ValueError(f"flag type not supported: {kind}")
    sarc = open_yaz_sarc(raw)
    names = sorted(
        (file.name for file in sarc.get_files()
         if file.name.startswith(f"/{kind}_data_") and file.name.endswith(".bgdata")),
        key=lambda name: int(name.rsplit("_", 1)[1].split(".", 1)[0]))
    objects = []
    entries = []
    for name in names:
        obj = oead.byml.from_binary(bytes(sarc.get_file(name).data))
        objects.append(obj)
        entries.extend(oead.byml.Hash(dict(entry)) for entry in obj[f"{kind}_data"])
    existing = {str(dict(entry)["DataName"]) for entry in entries}
    hashes = {int(dict(entry)["HashValue"]): str(dict(entry)["DataName"])
              for entry in entries}
    for flag in flags:
        if flag not in existing:
            collision = hashes.get(signed_crc(flag))
            if collision:
                raise RuntimeError(
                    f"collision CRC32: {flag} et {collision} ({signed_crc(flag)})")
            objects[-1][f"{kind}_data"].append(definition(flag, is_save, kind, init))
    # In-game isolation on 2026-08-25 proved that round-tripping the stock
    # table works and appending one definition works, while globally sorting
    # the same definitions crashes TriggerParam construction. Preserve every
    # existing entry and its order; only append to the final non-full page.
    if len(objects[-1][f"{kind}_data"]) > 4096:
        raise RuntimeError(
            f"last {kind}_data page full; page creation not implemented")
    replacements = {
        names[-1]: bytes(oead.byml.to_binary(
            objects[-1], big_endian=True, version=2))
    }
    return bytes(oead.yaz0.compress(write_sarc(sarc, replacements)))


def modify_gamedata(raw: bytes, is_save: bool) -> bytes:
    return modify_gamedata_flags(raw, FLAGS, is_save)


def repack_gamedata_without_changes(raw: bytes) -> bytes:
    """Rebuild only the nested SARC, preserving every member byte-for-byte."""
    return bytes(oead.yaz0.compress(write_sarc(open_yaz_sarc(raw), {})))


def repack_s32_byml_without_changes(raw: bytes) -> bytes:
    """Round-trip the stock s32 BYML without changing its logical contents."""
    sarc = open_yaz_sarc(raw)
    name = "/s32_data_0.bgdata"
    obj = oead.byml.from_binary(bytes(sarc.get_file(name).data))
    encoded = bytes(oead.byml.to_binary(obj, big_endian=True, version=2))
    return bytes(oead.yaz0.compress(write_sarc(sarc, {name: encoded})))


def append_one_volatile_flag(raw: bytes) -> bytes:
    """Preserve the stock table order and append one diagnostic flag."""
    sarc = open_yaz_sarc(raw)
    name = "/s32_data_0.bgdata"
    obj = oead.byml.from_binary(bytes(sarc.get_file(name).data))
    entries = obj["s32_data"]
    flag = FLAGS[0]
    if any(str(entry["DataName"]) == flag for entry in entries):
        raise RuntimeError(f"definition already present: {flag}")
    entries.append(definition(flag, is_save=False))
    encoded = bytes(oead.byml.to_binary(obj, big_endian=True, version=2))
    return bytes(oead.yaz0.compress(write_sarc(sarc, {name: encoded})))


def modify_saveformat(raw: bytes, flags=FLAGS) -> bytes:
    sarc = open_yaz_sarc(raw)
    objects = {}
    headers = {}
    all_entries = []
    page_names = [f"/saveformat_{number}.bgsvdata" for number in range(6)]
    for name in page_names:
        obj = oead.byml.from_binary(bytes(sarc.get_file(name).data))
        objects[name] = obj
        # Copy BYML nodes: pybind views are owned by their parent document and
        # become empty when the loop releases that document.
        headers[name] = oead.byml.Hash(dict(obj["file_list"][0]))
        all_entries.extend(oead.byml.Hash(dict(entry))
                           for entry in obj["file_list"][1])

    existing = {str(dict(entry)["DataName"]) for entry in all_entries}
    for flag in flags:
        if flag not in existing:
            all_entries.append(oead.byml.Hash({
                "DataName": flag, "HashValue": oead.S32(signed_crc(flag))}))
    all_entries.sort(key=lambda entry: int(dict(entry)["HashValue"]))

    replacements = {}
    offset = 0
    for number, name in enumerate(page_names):
        count = 8192 if number < 5 else len(all_entries) - offset
        page = oead.byml.Array(all_entries[offset:offset + count])
        objects[name]["file_list"] = oead.byml.Array([headers[name], page])
        replacements[name] = bytes(oead.byml.to_binary(
            objects[name], big_endian=True, version=2))
        offset += count
    if offset != len(all_entries):
        raise RuntimeError("saveformat pages did not consume every entry")
    return bytes(oead.yaz0.compress(write_sarc(sarc, replacements)))


def build(source: pathlib.Path, destination: pathlib.Path,
          variant: str = "ledger"):
    if not source.is_file():
        raise FileNotFoundError(
            f"Bootup.pack of the v208 update not found: {source}")
    # The graphic-pack replacement shadows the mounted update. Building from
    # the disc/base archive (v0) produces a structurally valid SARC containing
    # resources incompatible with the v208 executable and crashes its resource
    # loader at boot. This size is diagnostic only; do not silently accept the
    # known base-game archive used during the failed first attempt.
    if source.stat().st_size == 31_197_052:
        raise RuntimeError(
            "base game Bootup.pack refused; use the v208 update's")
    outer = oead.Sarc(source.read_bytes())
    game_name = "GameData/gamedata.ssarc"
    save_name = "GameData/savedataformat.ssarc"
    replacements = {}
    if variant == "gamedata-noop":
        replacements[game_name] = repack_gamedata_without_changes(
            bytes(outer.get_file(game_name).data))
    elif variant == "s32-byml-noop":
        replacements[game_name] = repack_s32_byml_without_changes(
            bytes(outer.get_file(game_name).data))
    elif variant == "one-volatile":
        replacements[game_name] = append_one_volatile_flag(
            bytes(outer.get_file(game_name).data))
    elif variant in ("volatile", "ledger"):
        replacements[game_name] = modify_gamedata(
            bytes(outer.get_file(game_name).data), is_save=variant == "ledger")
    if variant == "ledger":
        replacements[save_name] = modify_saveformat(
            bytes(outer.get_file(save_name).data))
    result = write_sarc(outer, replacements)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(result)
    expected_flags = (FLAGS if variant in ("volatile", "ledger")
                      else FLAGS[:1] if variant == "one-volatile" else ())
    verify(destination, expected_flags=expected_flags,
           expect_saved=variant == "ledger",
           expect_definition_saved=variant == "ledger")
    print(f"Bootup.pack AP ({variant}): "
          f"{source.stat().st_size} -> {len(result)} octets")
    print(f"ecrit: {destination}")


def verify(path: pathlib.Path, expected_flags: tuple[str, ...] = FLAGS,
           expect_saved: bool = True,
           expect_definition_saved: bool = True):
    outer = oead.Sarc(path.read_bytes())
    outer_count = sum(1 for _ in outer.get_files())
    if outer_count != 147:
        raise RuntimeError(
            f"unexpected Bootup.pack: {outer_count}/147 files")
    game = open_yaz_sarc(bytes(outer.get_file("GameData/gamedata.ssarc").data))
    obj = oead.byml.from_binary(bytes(game.get_file("/s32_data_0.bgdata").data))
    definitions = {str(dict(entry)["DataName"]): dict(entry)
                   for entry in obj["s32_data"]}
    save = open_yaz_sarc(bytes(outer.get_file("GameData/savedataformat.ssarc").data))
    saved = set()
    for number in range(6):
        obj = oead.byml.from_binary(bytes(
            save.get_file(f"/saveformat_{number}.bgsvdata").data))
        saved.update(str(dict(entry)["DataName"])
                     for entry in obj["file_list"][1])
    for flag in FLAGS:
        expect_flag = flag in expected_flags
        if expect_flag:
            if flag not in definitions:
                raise RuntimeError(f"definition missing: {flag}")
            actual_is_save = bool(definitions[flag]["IsSave"])
            if actual_is_save != expect_definition_saved:
                raise RuntimeError(
                    f"{flag}: IsSave={actual_is_save}, "
                    f"expected {expect_definition_saved}")
        elif flag in definitions:
            raise RuntimeError(f"unexpected definition in the no-op: {flag}")
        if expect_saved and flag not in saved:
            raise RuntimeError(f"saveformat missing: {flag}")
        if not expect_saved and flag in saved:
            raise RuntimeError(f"unexpected saveformat: {flag}")
        if expect_flag:
            print(f"  {flag}: hash={signed_crc(flag)}, "
                  f"saved={'yes' if expect_saved else 'no'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=pathlib.Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--variant",
                        choices=("noop", "gamedata-noop", "s32-byml-noop",
                                 "one-volatile", "volatile", "ledger"),
                        default="ledger")
    args = parser.parse_args()
    if args.install and args.output:
        parser.error("--install and --output are exclusive")
    if args.install:
        destination = DEFAULT_PACK / "content/Pack/Bootup.pack"
        if destination.exists():
            backup = destination.with_suffix(".pack.pre_ledger")
            if not backup.exists():
                shutil.copy2(destination, backup)
                print(f"backup: {backup}")
    else:
        destination = args.output or ROOT / ".build/Bootup_AP.pack"
    build(args.source, destination, args.variant)


if __name__ == "__main__":
    main()
