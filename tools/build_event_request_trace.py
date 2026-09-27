"""6i: observe native EventFlow requests and their returns, without issuing any."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path if Path(p).resolve() != ROOT / "tools"]
from tools.build_ui_lifecycle import trace_source as lifecycle_source, CAPACITY as LIFE_CAPACITY

# Request wrapper and both return paths; r31 remains the manager at the exits.
SITES = [(0x031CA008, 0x7C0802A6, "request_enter", 3, 0, 4),
         (0x031CA050, 0x80010014, "request_accepted", 31, 0, 4),
         (0x031CA068, 0x38600000, "request_rejected", 31, 0, 4)]
CAPACITY, STRIDE, MAGIC = 1024, 512, 0x41504551


def trace_source():
    source = lifecycle_source(SITES).replace("BOTW_AP_UILifecycle_V208", "BOTW_AP_EventRequest_V208")
    source = source.replace("apLife", "apEvent").replace("0x41504c46", "0x41504551")
    source = source.replace(".int 2048\n.int 32", f".int {CAPACITY}\n.int {STRIDE}")
    # The original lifecycle buffer is 64 KiB; resize storage as well as header.
    start = source.index("apEventData:")
    end = source.index("; request_enter", start)
    source = (source[:start] + "apEventData:\n" + "\n".join(
        [f".int 0x{MAGIC:08x}", ".int 1", f".int {CAPACITY}", f".int {STRIDE}"]
        + [".int 0"] * (4 + CAPACITY * STRIDE // 4)) + "\n" + source[end:])
    source = source.replace(f"cmplwi r9, {LIFE_CAPACITY}", f"cmplwi r9, {CAPACITY}").replace("slwi r10, r9, 5", "slwi r10, r9, 9")
    for index, (_, _, _, reg, *_) in enumerate(SITES, 1):
        anchor = f"stw r{reg}, 20(r10)"
        # Snapshot manager words already used by the native request code.
        lines = [anchor, f"addis r12, r{reg}, 1", "lwz r0, 0x74b4(r12)",
                 "stw r0, 376(r10)", "lwz r0, 0x75d0(r12)", "stw r0, 380(r10)"]
        if index == 1:
            # Request structure is 0x40 bytes. Its optional descriptor at +0x34
            # is a native 0x118-byte object (constructor 0x031cf5fc).
            for offset in range(0, 64, 4):
                lines += [f"lwz r0, {offset}(r4)", f"stw r0, {32 + offset}(r10)"]
            lines += ["lwz r12, 0x34(r4)", "cmpwi r12, 0", "beq apEventNoDescriptor"]
            for offset in range(0, 280, 4):
                lines += [f"lwz r0, {offset}(r12)", f"stw r0, {96 + offset}(r10)"]
            lines += ["apEventNoDescriptor:"]
        position = source.index(anchor, source.index(f"apEvent{index}:"))
        source = source[:position] + "\n".join(lines) + source[position + len(anchor):]
    return source


def build():
    sys.path.insert(0, str(ROOT / "tools/cemu"))
    from rpx import Rpx
    rpx = Rpx()
    for site, word, *_ in SITES:
        if rpx.read(site, 4) != word.to_bytes(4, "big"):
            raise ValueError(f"unexpected request instruction at {site:#x}")
    source = ROOT / ".build/ledger-validation/b1e5347f73ac58ed"
    manifest = json.loads((source / "manifest.json").read_text())
    files = {}
    for prefix, group in [("content/", "files"), ("", "native_files")]:
        for name, expected in manifest[group].items():
            path = (source / (prefix + name)).resolve()
            if not path.is_relative_to(source.resolve()):
                raise ValueError("source path escapes build")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("source build changed")
            files[prefix + name] = raw
    files["patch_event_request.asm"] = trace_source().encode()
    hashes = {n: hashlib.sha256(raw).hexdigest() for n, raw in sorted(files.items())}
    target = source.parent / hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:16]
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("immutable build changed")
        path.write_bytes(raw)
    (target / "rules.txt").write_bytes((source / "rules.txt").read_bytes())
    manifest.update(source_build=source.name, event_request_trace=True,
                    native_files={n: h for n, h in hashes.items() if not n.startswith("content/")},
                    event_request_sites=[dict(id=i, address=a, original=w, name=n)
                                         for i, (a, w, n, *_) in enumerate(SITES, 1)])
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(target)
    return target


if __name__ == "__main__":
    build()
