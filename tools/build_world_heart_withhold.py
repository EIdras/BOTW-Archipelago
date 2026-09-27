"""Derive an immutable candidate that withholds the heart of a picked-up container actor.

A stage of the native build chain. With the Divine Beast heart containers
turned into AP checks, the vanilla +1 heart of the map actor
``Obj_HeartUtuwa_A_01`` must not be granted, while everything else of the
pickup stays: GetDemo, the actor's death and its ``DeadUp`` link, which sets
``Get_HeartUtuwa_X`` (the check) and the per-actor flag.

Measured in the game:
* the heart is added during the GetDemo, without itemGet, by the obtain core
  ``0x02B76C08`` -> container effect ``0x02B766D4`` -> setMaxLife; the flags
  follow at the end of the event;
* a trace at the effect call saw the world pickup (item
  ``Obj_HeartUtuwa_A_01``) and **not** the AP ``Heart Container`` delivery,
  which adds its heart through the GetItemByName path.

In ``0x02B76C08`` the actor's tags pick the branch: tag ``HeartContainer``
(hash ``0xF9C66DEC``) jumps from ``SITE`` to the effect call; tag
``StaminaContainer`` falls through to it. The stage retargets only that
first conditional branch to the instruction after the effect call, so a
heart-container actor skips ``bl 0x02B766D4`` and continues through the
normal tail (``r31+4`` test, 0x032BC730, 0x03073DFC). Stamina vessels and
every other item keep the vanilla path. The only actors with that tag are
``Obj_HeartUtuwa_A_01`` (ActorInfo), placed in the four Divine Beasts and
in front of the Goddess Statues (``SyncLink``, ``Npc_FirstColony010_Appear
Heart``); the statue exchange grants through GetItemByName like the AP
delivery, so it is outside this branch.

Only ``patch_apInject.asm`` changes: one address line appended at its end.
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

# The seed pack of the chain's reference seed.
SOURCE = ROOT / ".build/seed-bound-candidates/d5315269711d8330"
OUTPUT = ROOT / ".build/world-heart-withhold-candidates"
INJECTION = "patch_apInject.asm"

FUNCTION = 0x02B76C08       # obtain-item core
TAG_TEST = 0x02B76C40       # bl 0x033949BC (actor has tag r4?)
TAG_HASH = 0xF9C66DEC       # "HeartContainer"
SITE = 0x02B76C48           # bne cr0, 0x02B76C64
EFFECT_CALL = 0x02B76C68    # bl 0x02B766D4 (container effect, +4 max life)
RESUME = 0x02B76C6C         # lwz r7, 0x4(r31)
# Vanilla words, checked against U-King.rpx before building.
VANILLA = {
    0x02B76C34: 0x3C80F9C6,  # lis r4, 0xf9c6
    0x02B76C3C: 0x38846DEC,  # addi r4, r4, 0x6dec
    TAG_TEST: 0x4881DD7D,
    0x02B76C44: 0x2C030000,  # cmpwi r3, 0
    SITE: 0x4082001C,
    0x02B76C64: 0x7FC3F378,  # mr r3, r30
    EFFECT_CALL: 0x4BFFFA6D,
    RESUME: 0x80FF0004,
}
PATCHED_WORD = 0x40820000 | (RESUME - SITE)   # bne cr0, RESUME
PATCH_LINE = f"0x{SITE:08x} = bne 0x{RESUME:08x}"
BLOCK = f"""
; --- Divine Beast heart container: no vanilla heart ------------------------
; An actor with the HeartContainer tag (Obj_HeartUtuwa_A_01) skips the effect
; 0x{EFFECT_CALL:08x} (bl 0x02b766d4, +4 max life). Pickup, the actor's death,
; the DeadUp link and the check's flag are unchanged. Stamina: vanilla path.
{PATCH_LINE}
"""


def rpx_words() -> dict[int, int]:
    sys.path.insert(0, str(ROOT / "tools/cemu"))
    from rpx import Rpx
    rpx = Rpx()
    return {address: int.from_bytes(rpx.read(address, 4), "big") for address in VANILLA}


def check_rpx(words: dict[int, int] | None = None) -> None:
    words = rpx_words() if words is None else words
    changed = {hex(a): hex(w) for a, w in words.items() if VANILLA[a] != w}
    if changed:
        raise ValueError(f"U-King.rpx differs from the audited heart branch: {changed}")
    high = words[0x02B76C34] & 0xFFFF
    low = words[0x02B76C3C] & 0xFFFF
    if ((high << 16) + (low - 0x10000 if low & 0x8000 else low)) & 0xFFFFFFFF != TAG_HASH:
        raise ValueError("heart container tag hash mismatch")


def patch_injection(text: str) -> str:
    """Pure transform of the parent injection: append one address line."""
    lowered = text.lower()
    for address in range(TAG_TEST, RESUME + 4, 4):
        if f"0x{address:08x} =" in lowered:
            raise ValueError(f"parent injection already patches 0x{address:08x}")
    sections = [line for line in text.splitlines() if line.startswith("[")]
    if sections != ["[BOTW_AP_InjectionTest_V208]"]:
        raise ValueError(f"unexpected parent injection sections: {sections}")
    return text.rstrip("\n") + "\n" + BLOCK


def build(source: Path = SOURCE, output: Path = OUTPUT) -> Path:
    source = source.resolve()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if (INJECTION not in manifest.get("native_files", {})
            or not manifest.get("native_delivery_entries")
            or manifest.get("world_heart_withhold")):
        raise ValueError("source is not a verified native candidate without heart withholding")
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
        "world_heart_withhold": {
            "parent_build": source.name,
            # The same build id can live in several .build folders (identical
            # bytes): name the one used.
            "parent_path": source.relative_to(ROOT).as_posix(),
            "injection_before_sha256": digest(parent_text.encode("utf-8")),
            "injection_after_sha256": digest(patched),
            "function": hex(FUNCTION),
            "site": hex(SITE),
            "vanilla_word": hex(VANILLA[SITE]),
            "patched_word": hex(PATCHED_WORD),
            "skipped_call": hex(EFFECT_CALL),
            "tag_hash": hex(TAG_HASH),
            "evidence": ["20260918T172815.886075Z-native-divine-heart-probe",
                         "20260918T213849.644955Z-native-heart-grant-trace"],
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
