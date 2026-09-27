"""Derive an immutable candidate that stops the champion powers coming back at load.

A stage of the native build chain, like tools/build_world_heart_withhold.py.

The ClearRemains recipe withholds the champion power when the Divine Beast is
freed, but the engine puts it back at the next load:

* a forged save with Clear_RemainsWater comes up with the power in the
  abilities menu and IsGet_Obj_HeroSoul_Zora at 1, although the save file holds
  0. The pouch really holds it (the Ballad guard's HasPorchItem says so);
* with one variable, Clear_RemainsWater: freed -> power, not freed -> nothing.
  A spy on the granted-object function 0x02b769c4 stayed at zero, and the
  itemGet counter too;
* a trace on 0x02EB3DF0, the single pouch item creation point of
  PauseMenuDataMgr (21 callers: itemGet, the event-flow grants, and the
  routines rebuilding the pouch from the save), named the caller. The freed
  load makes exactly one creation the unfreed load does not, from 0x02eb4d90.

That call sits in a run of four identical blocks, one per Divine Beast, in the
routine that rebuilds the pouch from GameData:

    li   r3, 0
    bl   <getter>            ; GameData bool Clear_Remains<X>
    cmpwi r3, 0
    beq  <next block>        ; not freed -> nothing to restore
    ...                      ; already in the pouch -> skip as well
    bl   0x02EB3DF0          ; create the champion power
    bl   <setter>            ; IsPlayed_Demo1XX_0

The getters are generated accessors reading cached GameData handles, which is
why no string and no crc32 of Clear_Remains* or Obj_HeroSoul_* appears anywhere
near this code, and why searching by name could never find it. Each handle was
traced to its name through the registration routine around 0x02de9600:
0x104644F0 Electric, 0x104644F4 Fire, 0x104644F8 Water, 0x104644FC Wind.

The stage turns the four `beq` into unconditional branches to the same target,
so each block is skipped whatever the flag says. Nothing else moves: the rest
of the rebuild, the other special items, itemGet and the event-flow path the AP
delivery uses are untouched, and the powers arrive only from Archipelago.

Only patch_apInject.asm changes: four address lines appended at its end.
EventFlow, delivery catalog and seed binding are unchanged.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path
                            if Path(p).resolve() != ROOT / "tools"]

from botw_patch.resources import digest  # noqa: E402
from tools.build_seed_bound_candidate import verified_files  # noqa: E402

# a003b02e801b0659: the Ballad guard asking the pouch.
SOURCE = ROOT / ".build/ballad-condition-candidates/a003b02e801b0659"
OUTPUT = ROOT / ".build/hero-soul-restore-candidates"
INJECTION = "patch_apInject.asm"

CREATE = 0x02EB3DF0          # PauseMenuDataMgr pouch item creation
# beast -> (getter call, its cached handle, the flag name, the guard branch,
#           its vanilla word, the creation call it protects)
BLOCKS = {
    "Rito": (0x02EB4C24, 0x104644FC, "Clear_RemainsWind",
             0x02EB4C2C, 0x41820078, 0x02EB4C90),
    "Goron": (0x02EB4CA8, 0x104644F4, "Clear_RemainsFire",
              0x02EB4CB0, 0x41820074, 0x02EB4D10),
    "Zora": (0x02EB4D28, 0x104644F8, "Clear_RemainsWater",
             0x02EB4D30, 0x41820074, 0x02EB4D90),
    "Gerudo": (0x02EB4DA8, 0x104644F0, "Clear_RemainsElectric",
               0x02EB4DB0, 0x41820080, 0x02EB4E10),
}
# This one was traced; the other three are the same shape, one per beast.
MEASURED = "Zora"
CALL_WORD = 0x48000000       # bl/b opcode bits, checked below


def _branch_target(address: int, word: int) -> int:
    offset = word & 0xFFFC
    return address + (offset - 0x10000 if offset & 0x8000 else offset)


def guard_lines() -> list[str]:
    lines = []
    for race, (_getter, _handle, flag, guard, word, _create) in BLOCKS.items():
        lines.append(f"0x{guard:08x} = b 0x{_branch_target(guard, word):08x}"
                     f"   ; {flag} -> Obj_HeroSoul_{race}")
    return lines


BLOCK = ("\n; --- champion powers: not restored at load ----------------------------------\n"
         "; PauseMenuDataMgr recreates the power in the pouch at every load when the\n"
         "; Divine Beast is freed (measured). The four guards become unconditional:\n"
         f"; the block is skipped, the creation 0x{CREATE:08x} no longer happens.\n"
         "; itemGet, the gifts by flow (AP delivery) and the rest of the pouch\n"
         "; rebuild are unchanged.\n"
         + "\n".join(guard_lines()) + "\n")


def rpx_words() -> dict[int, int]:
    sys.path.insert(0, str(ROOT / "tools/cemu"))
    from rpx import Rpx
    rpx = Rpx()
    addresses = set()
    for getter, _handle, _flag, guard, _word, create in BLOCKS.values():
        addresses |= {getter, guard, create}
    return {address: int.from_bytes(rpx.read(address, 4), "big") for address in sorted(addresses)}


def check_rpx(words: dict[int, int] | None = None) -> None:
    """Every anchor as measured: a call, a beq, and the creation call."""
    words = rpx_words() if words is None else words
    for race, (getter, handle, _flag, guard, word, create) in BLOCKS.items():
        if words[guard] != word:
            raise ValueError(f"{race}: guard word changed at {guard:#x}: {words[guard]:#010x}")
        for call in (getter, create):
            if words[call] & 0xFC000003 != 0x48000001:
                raise ValueError(f"{race}: {call:#x} is not a bl")
        if _branch_target(create, words[create] | 0) & ~1 != CREATE:
            raise ValueError(f"{race}: {create:#x} does not call the pouch creation")
        if handle != _getter_handle(getter, words):
            raise ValueError(f"{race}: getter {getter:#x} does not read {handle:#x}")


def _getter_handle(call_site: int, _words: dict[int, int]) -> int:
    """The GameData handle the generated accessor at this call site reads."""
    sys.path.insert(0, str(ROOT / "tools/cemu"))
    import struct
    from rpx import Rpx
    rpx = Rpx()
    word = int.from_bytes(rpx.read(call_site, 4), "big")
    offset = word & 0x03FFFFFC
    if offset & 0x02000000:
        offset -= 0x04000000
    thunk = (call_site + offset) & 0xFFFFFFFF
    lis, lwz = struct.unpack(">2I", rpx.read(thunk + 4, 8))
    if (lis >> 26) != 15 or (lwz >> 26) != 32:
        raise ValueError(f"accessor at {thunk:#x} is not the expected shape")
    high, low = lis & 0xFFFF, lwz & 0xFFFF
    return ((high << 16) + (low - 0x10000 if low & 0x8000 else low)) & 0xFFFFFFFF


def patch_injection(text: str) -> str:
    """Pure transform of the parent injection: append the four address lines."""
    lowered = text.lower()
    for _getter, _handle, _flag, guard, _word, _create in BLOCKS.values():
        if f"0x{guard:08x} =" in lowered:
            raise ValueError(f"parent injection already patches 0x{guard:08x}")
    sections = [line for line in text.splitlines() if line.startswith("[")]
    if sections != ["[BOTW_AP_InjectionTest_V208]"]:
        raise ValueError(f"unexpected parent injection sections: {sections}")
    return text.rstrip("\n") + "\n" + BLOCK


def build(source: Path = SOURCE, output: Path = OUTPUT) -> Path:
    source = source.resolve()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if (INJECTION not in manifest.get("native_files", {})
            or not manifest.get("native_delivery_entries")
            or manifest.get("hero_soul_restore_withhold")):
        raise ValueError("source is not a verified native candidate without the stage")
    check_rpx()
    files = verified_files(source, manifest)
    parent_text = files[INJECTION].decode("utf-8")
    patched = patch_injection(parent_text).encode("utf-8")
    files[INJECTION] = patched
    hashes = {name: digest(raw) for name, raw in sorted(files.items())}
    build_id = hashlib.sha256(json.dumps(hashes, sort_keys=True,
                              separators=(",", ":")).encode()).hexdigest()[:16]
    target = (output / build_id).resolve()
    if not target.is_relative_to(output.resolve()):
        raise ValueError("candidate escaped output root")
    for name, raw in files.items():
        path = (target / name).resolve()
        if not path.is_relative_to(target):
            raise ValueError("candidate member escaped output root")
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"immutable candidate changed: {name}")
        path.write_bytes(raw)
    result = dict(manifest)
    result.update({
        "status": "requires_in_game_validation",
        "hero_soul_restore_withhold": {
            "parent_build": source.name,
            "parent_path": source.relative_to(ROOT).as_posix(),
            "injection_before_sha256": digest(parent_text.encode("utf-8")),
            "injection_after_sha256": digest(patched),
            "creation_call": hex(CREATE),
            "blocks": {race: {"getter": hex(getter), "handle": hex(handle), "flag": flag,
                              "guard": hex(guard), "vanilla_word": hex(word),
                              "patched": f"b 0x{_branch_target(guard, word):08x}",
                              "skipped_creation": hex(create)}
                       for race, (getter, handle, flag, guard, word, create)
                       in BLOCKS.items()},
            "measured_block": MEASURED,
            "evidence": ["20260920T151602.539373Z-native-ballad-context",
                         "20260920T184539.772428Z-native-hero-soul-restore",
                         "20260921T000737.704468Z-native-pouch-insert"],
            "eventflow_and_catalog_unchanged": True,
        },
        "native_files": {name: hashes[name] for name in manifest["native_files"]},
    })
    encoded = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = target / "manifest.json"
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("immutable candidate manifest changed")
    path.write_bytes(encoded)
    return target


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    print(build(arguments.source, arguments.output))
