"""Build an experimental Item_AP-only variant; never edit the legacy pack.

This is an actor-label filter, not yet a request identity or completion protocol.
"""
import hashlib
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.cemu.rpx import Rpx

LEGACY_SHA = "99fa97ee64cd691e1e4d24970de8a842079ff9193f97d16d337a8cad6f8e5f6d"
SOURCE = ROOT / ".build/ledger-validation/9bed01d0c46f146f"
# Site, stack SafeString, inline storage, exact label, exit before consumption.
SCOPES = ((0x030835C8, 0x16C, 0x178, b"Item_AP_Name\0", "apSubEnd", "apSubReq"),
          (0x03083860, 0x11C, 0x128, b"Item_AP_Desc\0", "apSubDescOrig", "apSubDescReq"))


def guard(offset, storage, label, end):
    # r0 is reloaded from the original saved LR in both epilogues. r12 is
    # already scratch in both legacy hooks. No pointer chasing or game calls.
    lines = ["    ; Item_AP exact label gate, including NUL; stack storage only.",
             f"    addi  r12, r1, {storage:#x}",
             f"    lwz   r0, {offset:#x}(r1)", "    cmpw  r0, r12", f"    bne   {end}"]
    for index, value in enumerate(label):
        lines += [f"    lbz   r12, {storage + index:#x}(r1)",
                  f"    cmpwi r12, {value}", f"    bne   {end}"]
    return "\n".join(lines) + "\n"


def scoped_source(raw):
    if hashlib.sha256(raw).hexdigest() != LEGACY_SHA:
        raise ValueError("legacy source hash mismatch")
    source = raw.decode("utf-8")
    for _, offset, storage, label, end, request in SCOPES:
        anchor = f"    lwz   r12, {request}@l(r11)"
        if source.count(anchor) != 1:
            raise ValueError("substitution anchor is not unique")
        source = source.replace(anchor, guard(offset, storage, label, end) + anchor)
    return source.encode("utf-8")


def verify_rpx(rpx):
    # Instructions establish inline storage, label argument, output and hook.
    expected = {
        0x03083564: "3801017893810170", 0x03083570: "9001016c",
        0x030835A0: "3c80102680a100143861016c3884dd58",
        0x030835B8: "7fa5eb783881016c386100604bfff6ad8381027883a1027c8001028c",
        0x03083820: "39010128938100143861011c9101011c",
        0x030836D0: "3c8010267fc3f37880a1000c3884dd70",
        0x03083850: "386100103881011c7fa5eb784bfff415bb61022c80010244",
        0x1025DD58: "25735f4e616d6500", 0x1025DD70: "25735f4465736300",
    }
    for address, hex_bytes in expected.items():
        raw = bytes.fromhex(hex_bytes)
        if rpx.read(address, len(raw)) != raw:
            raise ValueError(f"RPX context mismatch at {address:#x}")
    return {f"{a:08x}": b for a, b in expected.items()}


def build(*, partitioned=False):
    context = verify_rpx(Rpx())
    legacy = (ROOT / "native/cemu/legacy/patch_apInject.asm").read_bytes()
    installed = ROOT / ".build/cemu-validation/portable/graphicPacks/BOTW_Archipelago/patch_apInject.asm"
    if installed.read_bytes() != legacy:
        raise ValueError("installed base differs from the audited legacy source")
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    files = {}
    for prefix, group in (("content/", "files"), ("", "native_files")):
        for name, expected in manifest[group].items():
            path = (SOURCE / (prefix + name)).resolve()
            if not path.is_relative_to(SOURCE.resolve()):
                raise ValueError("source path escapes build")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("source artifact changed")
            files[prefix + name] = raw
    files["patch_apInject.asm"] = scoped_source(legacy)
    if partitioned:
        from tools.build_ui_lifecycle import SITES, trace_source
        rpx = Rpx()
        for site, word, *_ in SITES:
            if rpx.read(site, 4) != word.to_bytes(4, "big"):
                raise ValueError("lifecycle RPX site mismatch")
        files["patch_ui_lifecycle.asm"] = trace_source(version=2).encode()
        manifest["lifecycle_version"] = 2
        manifest["lifecycle_reserve"] = "256 action boundary/native open records; 3840 ambient records"
    hashes = {n: hashlib.sha256(b).hexdigest() for n, b in sorted(files.items())}
    manifest.update(source_build=SOURCE.name, replaces_base_injection=True,
                    scoped_text="exact Item_AP label; request identity still pending",
                    legacy_sha256=LEGACY_SHA, scoped_text_rpx_context=context,
                    autonomous_text=False,
                    native_files={n: h for n, h in hashes.items() if not n.startswith("content/")})
    files["rules.txt"] = (SOURCE / "rules.txt").read_bytes()
    files["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    target = SOURCE.parent / hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:16]
    for name, raw in files.items():
        path = target / name
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("immutable build changed")
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    print(target)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--partitioned", action="store_true")
    build(partitioned=parser.parse_args().partitioned)
