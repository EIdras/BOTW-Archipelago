"""Experimental resource-scoped request ownership and native text cleanup."""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [str(ROOT)] + [p for p in sys.path
    if Path(p).resolve() not in (ROOT / "tools", ROOT / "tools/cemu")]
from botw_patch.events import read_flow, write_flow, graph_snapshot
from botw_patch.resources import ResourceBuilder
from tools.cemu.guest import MEM2_END, below
from tools.cemu.rpx import Rpx
sys.path[:] = [str(ROOT)] + [p for p in sys.path
    if Path(p).resolve() not in (ROOT / "tools", ROOT / "tools/cemu")]

SOURCE = ROOT / ".build/ledger-validation/f85f1b1d3c52d7fa"
MARKER = "AP_Request_Display"
# New anchors adjacent to, not replacing, the existing lifecycle probes.
SITES = ((0x0234BDEC, 0x389E001C, "Bind"),
         (0x0234BC24, 0x61080004, "Complete"),
         (0x0234BE28, 0x3FE01048, "Leave"),
         (0x0234BB9C, 0x99830025, "Reset"))


def mark_action(raw):
    flow = read_flow(raw)
    before = graph_snapshot(flow)
    target = next(e for e in flow.flowchart.events if e.name == "APStandalone_Dialog")
    if (str(target.data.actor_action.v) != "Demo_OpenGetDemoDialog"
            or target.data.params.data["TargetActorName"] != "Item_AP"):
        raise ValueError("unexpected standalone dialog")
    target.data.params.data["TargetActorName"] = MARKER
    result = write_flow(flow)
    expected = copy.deepcopy(before)
    expected["events"]["APStandalone_Dialog"]["params"]["TargetActorName"] = MARKER
    if graph_snapshot(read_flow(result)) != expected:
        raise ValueError("unrelated EventFlow change")
    return result, ["mark only APStandalone_Dialog; native adapter retains Item_AP display"]


def ints(raw):
    raw += bytes((-len(raw)) % 4)
    return [f".int 0x{int.from_bytes(raw[i:i+4], 'big'):08x}" for i in range(0, len(raw), 4)]


def lock(base, busy):
    return [f"addi r12, r{base}, 48", ".int 0x7d206028 ; lwarx r9,0,r12",
            "cmpwi r9, 0", f"bne {busy}", "li r9, 1",
            ".int 0x7d20612d ; stwcx. r9,0,r12", f"bne {busy}",
            ".int 0x7c0004ac ; sync acquire"]


def unlock(base):
    return [".int 0x7c0004ac ; sync release", "li r9, 0", f"stw r9, 48(r{base})"]


def clear_text():
    return ["lis r10, apTick@ha", "li r0, 0", "stw r0, apSubReq@l(r10)",
            "stw r0, apSubDescReq@l(r10)", "stw r0, apSubAuto@l(r10)"]


def phase(base, value):
    return [f"li r0, {value}", ".int 0x7c0004ac ; publish phase last", f"stw r0, 8(r{base})"]


def resource_ready_guard(*, event_gate=False):
    """Final native gate for the manager predicate isolated at 0x031c8050.

    Return 2 without calling the presentation wrapper when its resource object
    is absent or its vtable+0xb4 readiness method returns zero.
    """
    lines = ["lis r12, 0x1047", "lwz r12, -0x2c54(r12)",
            "cmpwi r12, 0", "beq apOwnedDeferred",
            "addis r12, r12, 1"]
    if event_gate:
        # 031c8318 loads r25+fc, with r25=manager+174b4.
        # Nonzero rejects ordinary (r26=0) requests before insertion.
        lines += ["lwz r0, 0x75b0(r12)", "cmpwi r0, 0", "bne apOwnedDeferred"]
    return lines + ["lwz r3, 0x74a4(r12)",
            "cmpwi r3, 0", "beq apOwnedDeferred", "lwz r8, 0(r3)",
            "lwz r0, 0xb4(r8)", "mtctr r0", "bctrl", "cmpwi r3, 0",
            "beq apOwnedDeferred"]


def owner_source(version=1, *, retired_guard=False, resource_gate=True, event_gate=False,
                 mem2_end=MEM2_END):
    # mem2_end: where the game's main memory ends (tools/cemu/guest.py), the
    # bound of the pointers this code follows.
    if event_gate and not resource_gate:
        raise ValueError('event gate requires resource gate')
    if version == 2:
        from tools.native_presentation_join import extend
        return extend(owner_source(resource_gate=resource_gate, event_gate=event_gate, mem2_end=mem2_end),
                      retired_guard=retired_guard, mem2_end=mem2_end)
    if version != 1:
        raise ValueError('Unknown owner protocol version')
    # Header is 64 bytes. Generation is incremented by native submission, never
    # supplied by Python. Phase: idle0/staged1/submitting2/accepted3/bound4/
    # action_complete5/released6/refused7/uncertain8. Released is NOT event end.
    lines = ["; Owned presentation extension v1; experimental, no grants.", "apOwnedData:",
             ".int 0x41504f57", ".int 1"] + [".int 0"] * 8 + [".int 2"] + [".int 0"] * 5
    lines += ["apOwnedFlow:"] + ints(b"Demo007_1\0")
    lines += ["apOwnedEntry:"] + ints(b"APDisplayStandalone\0")
    lines += ["apOwnedActor:"] + ints(b"Item_AP\0")
    lines += ["apOwnedFlowSafe:", ".int apOwnedFlow", ".int 0x10263910",
              "apOwnedEntrySafe:", ".int apOwnedEntry", ".int 0x10263910",
              "apOwnedActorSafe:", ".int apOwnedActor", ".int 0x10263910"]
    lines += ["apOwnedSubmit:", "stwu r1, -32(r1)", "mflr r0", "stw r0, 36(r1)",
              "stw r31, 28(r1)", "lis r31, apOwnedData@ha", "addi r31, r31, apOwnedData@l"]
    lines += lock(31, "apOwnedSubmitBusy")
    lines += ["lwz r0, 52(r31)", "cmpwi r0, 0", "bne apOwnedBadStage",
              "lwz r0, 8(r31)", "cmpwi r0, 1", "bne apOwnedBadStage",
              "lwz r0, 40(r31)", "cmpwi r0, 2", "beq apOwnedQuotaValid", "cmpwi r0, 4",
              "bne apOwnedBadStage", "apOwnedQuotaValid:"]
    if resource_gate:
        lines += resource_ready_guard(event_gate=event_gate)
    lines += [
              "lwz r9, 12(r31)", "cmpwi r9, -1", "beq apOwnedBadStage",
              "addi r9, r9, 1", "stw r9, 12(r31)", "li r0, 0",
              "stw r0, 16(r31)", "stw r0, 24(r31)", "stw r0, 28(r31)",
              "stw r0, 32(r31)", "stw r0, 36(r31)", "stw r0, 56(r31)", "stw r0, 60(r31)",
              "li r0, -1", "stw r0, 20(r31)"]
    lines += clear_text() + phase(31, 2) + unlock(31)
    lines += ["li r3, 0", "lis r4, apOwnedFlowSafe@ha", "addi r4, r4, apOwnedFlowSafe@l",
              "lis r5, apOwnedEntrySafe@ha", "addi r5, r5, apOwnedEntrySafe@l",
              "li r6, 1", "li r7, 0", "bl 0x02ddf744"]
    lines += lock(31, "apOwnedSubmitBusy")
    lines += ["stw r3, 20(r31)", "cmpwi r3, 1", "beq apOwnedAccepted",
              "cmpwi r3, 0", "bne apOwnedUnknown", "lwz r0, 8(r31)",
              "cmpwi r0, 2", "bne apOwnedUnknown"]
    lines += clear_text() + phase(31, 7) + ["b apOwnedReturnUnlock", "apOwnedAccepted:",
              "lwz r0, 8(r31)", "cmpwi r0, 2", "bne apOwnedReturnUnlock"]
    lines += phase(31, 3) + ["b apOwnedReturnUnlock", "apOwnedUnknown:"]
    lines += clear_text() + phase(31, 8) + ["li r0, 1", "stw r0, 52(r31)",
              "b apOwnedReturnUnlock"]
    if resource_gate:
        lines += ["apOwnedDeferred:"] + clear_text() + phase(31, 0) + [
                  "li r3, 2", "b apOwnedReturnUnlock"]
    lines += ["apOwnedBadStage:", "li r3, -1",
              "apOwnedReturnUnlock:"] + unlock(31) + ["b apOwnedReturn",
              "apOwnedSubmitBusy:", "li r0, 1", "stw r0, 52(r31)", "li r3, -1",
              "apOwnedReturn:", "lwz r31, 28(r1)", "lwz r0, 36(r1)",
              "mtlr r0", "addi r1, r1, 32", "blr"]
    for site, original, name in SITES:
        label = "apOwned" + name
        lines += [label + ":", f".int 0x{original:08x} ; replay original before instrumentation",
                  "stwu r1, -32(r1)", "stw r0, 8(r1)", "stw r9, 12(r1)",
                  "stw r10, 16(r1)", "stw r11, 20(r1)", "stw r12, 24(r1)",
                  ".int 0x7c000026 ; mfcr r0", "stw r0, 28(r1)",
                  "lis r11, apOwnedData@ha", "addi r11, r11, apOwnedData@l"]
        if name == "Bind":
            # Original r4 is action+0x1c. The game passes this SafeString to
            # native_open immediately next. Verify each byte, including NUL.
            lines += ["lwz r12, 0(r4)", "lis r10, 0x0100", "cmplw r12, r10",
                      f"blt {label}Done", *below(mem2_end, "r12", "r10", f"{label}Done", margin=0x40)]
            for index, value in enumerate(MARKER.encode() + b"\0"):
                lines += [f"lbz r0, {index}(r12)", f"cmpwi r0, {value}", f"bne {label}Done"]
            # Remap this resource marker only; no mutation of the action's
            # SafeString, inventory or actor database. Unowned display uses
            # native Item_AP fallback with text gates shut.
            lines += ["lis r4, apOwnedActorSafe@ha", "addi r4, r4, apOwnedActorSafe@l"]
        else:
            # Unrelated actions never contend for the ownership lock. Recheck
            # under lock below before making any state change.
            reg = 30 if name == "Complete" else 3
            lines += ["lwz r0, 16(r11)", f"cmpw r0, r{reg}", f"bne {label}Done"]
        lines += lock(11, label + "Busy")
        lines += ["lwz r0, 52(r11)", "cmpwi r0, 0", f"bne {label}Unlock"]
        if name == "Bind":
            lines += ["lwz r0, 8(r11)", "cmpwi r0, 2", f"beq {label}Claim",
                      "cmpwi r0, 3", f"beq {label}Claim", "cmpwi r0, 4", f"beq {label}Duplicate",
                      "cmpwi r0, 5", f"bne {label}Unlock", label + "Duplicate:"]
            lines += clear_text() + phase(11, 8) + ["li r0, 1", "stw r0, 52(r11)", f"b {label}Unlock", label + "Claim:",
                      "lwz r0, 12(r11)", "cmpwi r0, 0", f"beq {label}Unlock",
                      "stw r0, 32(r11)", "stw r30, 16(r11)", "lis r10, apTick@ha",
                      "lwz r0, 40(r11)", "stw r0, apSubReq@l(r10)", "stw r0, apSubDescReq@l(r10)"]
            lines += phase(11, 4)
        else:
            reg = 30 if name == "Complete" else 3
            lines += ["lwz r0, 16(r11)", f"cmpw r0, r{reg}", f"bne {label}Unlock",
                      "lwz r0, 8(r11)", "cmpwi r0, 4"]
            if name == "Complete":
                lines += [f"bne {label}Unlock", "lwz r0, 12(r11)", "stw r0, 24(r11)"] + phase(11, 5)
            else:
                lines += [f"beq {label}Active", "cmpwi r0, 5", f"bne {label}Unlock", label + "Active:"]
                if name == "Leave":
                    lines += ["lis r10, apTick@ha", "lwz r0, apSubReq@l(r10)", "stw r0, 56(r11)",
                              "lwz r0, apSubDescReq@l(r10)", "stw r0, 60(r11)",
                              "lwz r0, 12(r11)", "stw r0, 28(r11)", "lwz r0, 8(r11)",
                              "cmpwi r0, 5", f"bne {label}Aborted"]
                    lines += clear_text() + phase(11, 6) + [f"b {label}Unlock", label + "Aborted:"]
                lines += ["lwz r0, 12(r11)", "stw r0, 36(r11)"] + clear_text() + phase(11, 8)
        lines += [label + "Unlock:"] + unlock(11) + [f"b {label}Done", label + "Busy:",
                  "li r0, 1", "stw r0, 52(r11)", label + "Done:",
                  "lwz r0, 28(r1)", ".int 0x7c0ff120 ; mtcrf 255,r0", "lwz r0, 8(r1)",
                  "lwz r9, 12(r1)", "lwz r10, 16(r1)", "lwz r11, 20(r1)", "lwz r12, 24(r1)",
                  "addi r1, r1, 32", f"b 0x{site+4:08x}", f"0x{site:08x} = b {label}"]
    return "\n".join(lines) + "\n"


def gate(end):
    return ("    lis r12, apOwnedData@ha\n    addi r12, r12, apOwnedData@l\n"
            f"    lwz r0, 52(r12)\n    cmpwi r0, 0\n    bne {end}\n"
            f"    lwz r0, 8(r12)\n    cmpwi r0, 4\n    bne {end}\n")


def patch_native(raw):
    from tools.build_scoped_text import SCOPES, guard
    text = raw.decode()
    for _, offset, storage, label, end, _ in SCOPES:
        anchor = guard(offset, storage, label, end)
        if text.count(anchor) != 1:
            raise ValueError("scoped gate missing")
        text = text.replace(anchor, gate(end) + anchor)
    return (text + "\n" + owner_source()).encode()


def build():
    rpx = Rpx()
    for site, original, _ in SITES:
        if rpx.read(site, 4) != original.to_bytes(4, "big"):
            raise ValueError(f"RPX anchor mismatch: {site:#x}")
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    files = {}
    for prefix, key in (("content/", "files"), ("", "native_files")):
        for name, expected in manifest[key].items():
            path = (SOURCE / (prefix+name)).resolve()
            if not path.is_relative_to(SOURCE.resolve()):
                raise ValueError("source path escapes build")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError("source changed")
            files[prefix+name] = raw
    builder = ResourceBuilder(SOURCE / "content")
    builder.patch_archive("Pack/TitleBG.pack", {"EventFlow/Demo007_1.bfevfl": mark_action})
    files.update({"content/"+n: raw for n, raw in builder.finish().items()})
    files["patch_apInject.asm"] = patch_native(files["patch_apInject.asm"])
    hashes = {n: hashlib.sha256(raw).hexdigest() for n, raw in sorted(files.items())}
    target = SOURCE.parent / hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:16]
    manifest.update(source_build=SOURCE.name, owned_presentation=1, owned_marker=MARKER,
                    changes=builder.changes, autonomous_text=False,
                    files={n[8:]: h for n, h in hashes.items() if n.startswith("content/")},
                    native_files={n: h for n, h in hashes.items() if not n.startswith("content/")})
    files["rules.txt"] = (SOURCE / "rules.txt").read_bytes()
    files["manifest.json"] = (json.dumps(manifest, indent=2)+"\n").encode()
    for name, raw in files.items():
        path = target / name
        if path.exists() and path.read_bytes() != raw:
            raise ValueError("immutable target changed")
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    print(target)
    return target


if __name__ == "__main__":
    build()
