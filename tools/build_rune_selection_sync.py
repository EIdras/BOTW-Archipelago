"""Derive an immutable candidate whose companion can request a rune selection.

This is a stage of the native build chain, applied to any verified parent
whose injection carries the anchors below. Seed builds start from the
seed-independent base ``BASE_SOURCE`` + this stage (see
``tools/build_seed_bound_candidate.py``, which refuses a source without it).
Only ``patch_apInject.asm`` changes:

* five words appended at the END of the cave data block (after apScrTable),
  so no existing mailbox field moves; ``apSelMagic`` lets Python detect a
  stale patch, whose "new" fields would otherwise read code without error;
* one service block in the per-frame hook, between the rune counter and the
  item notification, that calls the game's own request function
  ``0x02A2D6D4(*(0x10463798), type)`` when Python asks for it.

The EventFlow, the delivery catalog and the seed binding are unchanged: the
persistent transaction stays flag + PlayerEquipItemType + cursor. See
``botw_client/rune_selection.py`` for the companion side.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path
                            if Path(p).resolve() != ROOT / "tools"]

from botw_client.rune_selection import (  # noqa: E402
    REQUEST_FUNCTION, RUNE_TYPES, SELECTION_GLOBAL)
from botw_patch.resources import digest  # noqa: E402
from tools.build_seed_bound_candidate import verified_files  # noqa: E402

SOURCE = ROOT / ".build/plateau-sensor-candidates/386f3df72c18dcb3"
# Seed-independent base of the seed builds (request-reject trace, placeholder token).
BASE_SOURCE = ROOT / ".build/request-reject-trace/c6f33f2902bd3da5"
OUTPUT = ROOT / ".build/rune-selection-sync-candidates"
INJECTION = "patch_apInject.asm"
MAGIC = 0x52534C31  # "RSL1"

DATA_ANCHOR = """apScrTable:
.int 0
.align 4
"""
DATA_FIELDS = f"""apScrTable:
.int 0
; --- rune selection requested from the game (apCheckSel) ------------------
; Appended at the END of the block: no existing field moves. apSelMagic is
; 0x{MAGIC:08X}; on a stale patch these words fall on code, and Python then
; refuses the request instead of writing blindly.
apSelMagic:
.int 0x{MAGIC:08X}
apSelReq:
.int 0
apSelType:
.int 0
apSelDone:
.int 0
; 1 = 0x02A2D6D4 called; 0 = nothing called (invalid type or no object)
apSelResult:
.int 0
.align 4
"""
BRANCH_ANCHOR = """    lwz   r12, apRuneReq@l(r11)
    cmpwi r12, 0
    beq   apCheckNotify
"""
BRANCH_PATCHED = """    lwz   r12, apRuneReq@l(r11)
    cmpwi r12, 0
    beq   apCheckSel
"""
SERVICE_ANCHOR = "\napCheckNotify:\n"
_TYPE_LIMIT = max(RUNE_TYPES) + 1
_SAVED = ("r0", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r10")
_SAVE = "\n".join(f"    stw   {r}, apS{r[1:]}@l(r11)" for r in _SAVED)
_RESTORE = "\n".join(f"    lwz   {r}, apS{r[1:]}@l(r11)" for r in reversed(_SAVED))
SERVICE = f"""
apCheckSel:
    ; --- ask the game to select a rune -------------------------------------
    ; The same path as the activation in the inventory (measured): the request
    ; is only WRITTEN, through the game's function 0x{REQUEST_FUNCTION:08X}(object,
    ; type). Its per-frame update then applies it and writes
    ; PlayerEquipItemType itself. The object is the singleton *(0x{SELECTION_GLOBAL:08X}),
    ; tested before use: it does not exist before the player is created.
    lwz   r12, apSelReq@l(r11)
    cmpwi r12, 0
    beq   apCheckNotify

    li    r12, 0
    stw   r12, apSelReq@l(r11)
    stw   r12, apSelResult@l(r11)

    lwz   r12, apSelType@l(r11)
    cmpwi r12, 0
    blt   apSelFinish               ; only the delivered rune types
    cmpwi r12, {_TYPE_LIMIT}
    bge   apSelFinish

    lis   r12, 0x{SELECTION_GLOBAL >> 16:04x}
    lwz   r12, 0x{SELECTION_GLOBAL & 0xFFFF:04x}(r12)
    cmpwi r12, 0
    beq   apSelFinish

{_SAVE}
    mflr  r0
    stw   r0, apSLR@l(r11)
    mfctr r0
    stw   r0, apSCTR@l(r11)

    mr    r3, r12
    lwz   r4, apSelType@l(r11)
    lis   r12, 0x{REQUEST_FUNCTION >> 16:04x}
    ori   r12, r12, 0x{REQUEST_FUNCTION & 0xFFFF:04x}
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
{_RESTORE}

    li    r12, 1
    stw   r12, apSelResult@l(r11)

apSelFinish:
    lwz   r12, apSelDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apSelDone@l(r11)
"""


def patch_injection(text: str) -> str:
    """Pure transform of the parent injection; each anchor must match once."""
    for anchor, label in ((DATA_ANCHOR, "data block end"),
                          (BRANCH_ANCHOR, "rune counter skip"),
                          (SERVICE_ANCHOR, "notification entry")):
        if text.count(anchor) != 1:
            raise ValueError(f"anchor not unique in parent injection: {label}")
    if "apCheckSel" in text or "apSelMagic" in text:
        raise ValueError("parent injection already has rune selection")
    text = text.replace(DATA_ANCHOR, DATA_FIELDS)
    text = text.replace(BRANCH_ANCHOR, BRANCH_PATCHED)
    return text.replace(SERVICE_ANCHOR, SERVICE + SERVICE_ANCHOR)


def build(source: Path = SOURCE, output: Path = OUTPUT) -> Path:
    source = source.resolve()
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if (INJECTION not in manifest.get("native_files", {})
            or not manifest.get("native_delivery_entries")
            or manifest.get("rune_selection_sync")):
        raise ValueError("source is not a verified native candidate without rune selection sync")
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
        "rune_selection_sync": {
            "parent_build": source.name,
            "injection_before_sha256": digest(parent_text.encode("utf-8")),
            "injection_after_sha256": digest(patched),
            "selection_global": hex(SELECTION_GLOBAL),
            "request_function": hex(REQUEST_FUNCTION),
            "magic": hex(MAGIC),
            "fields": ["apSelMagic", "apSelReq", "apSelType", "apSelDone", "apSelResult"],
            "accepted_types": sorted(RUNE_TYPES),
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
