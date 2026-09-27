"""Read native request snapshots, including stack-owned descriptor copies."""
import re
import struct
from tools.build_event_request_trace import SITES, CAPACITY, STRIDE, MAGIC, trace_source


def locate(log):
    matches = re.findall(r"BOTW_AP_EventRequest_V208.*?Codecave: ([0-9a-fA-F]+)-", log)
    return int(matches[-1], 16) if matches else None


def read_trace(process, base, address):
    if address is None or not 0x01000000 <= address < 0x50000000:
        raise ValueError("event request trace not located")
    def read(offset, size):
        data = process.read(base + address + offset, size)
        if data is None or len(data) != size:
            raise RuntimeError("short event request trace read")
        return data
    magic, version, capacity, stride, count, dropped, busy, contention = struct.unpack(">8I", read(0, 32))
    if magic != MAGIC or version != 1 or capacity not in (128, CAPACITY) or stride != STRIDE or count > capacity:
        raise ValueError("event request trace header mismatch")
    raw = read(32, count * stride) if count else b""
    events = []
    for index in range(count):
        record = raw[index * stride:(index + 1) * stride]
        seq, site, caller, r3, r4, manager, _, _ = struct.unpack_from(">8I", record)
        if seq != index + 1 or not 1 <= site <= len(SITES):
            raise ValueError("incomplete event request record")
        item = dict(sequence=seq, site=SITES[site - 1][2], return_address=caller,
                    r3=r3, r4=r4, manager=manager,
                    manager_174b4=struct.unpack_from(">I", record, 376)[0],
                    manager_175d0=struct.unpack_from(">I", record, 380)[0])
        if site == 1:
            item["request_hex"] = record[32:96].hex()
            descriptor = struct.unpack_from(">I", record, 32 + 0x34)[0]
            item["descriptor"] = descriptor
            item["descriptor_hex"] = record[96:376].hex() if descriptor else None
            # Native bounded string buffers follow SafeString objects at +14/+60.
            if descriptor:
                item["descriptor_name_candidate"] = record[96 + 0x20:96 + 0x60].split(b"\0")[0].decode("utf-8", "replace")
                item["descriptor_entry_candidate"] = record[96 + 0x6c:96 + 0xec].split(b"\0")[0].decode("utf-8", "replace")
        events.append(item)
    return dict(events=events, capacity=capacity, dropped=dropped, writer_busy=busy, contention_detected=bool(contention),
                limitation="Observed requests only. Candidate strings require verification; acceptance is not event completion.")


def descriptor_fields(descriptor: bytes) -> dict:
    """The request (evt::Metadata, 0x118 bytes on Wii U) as zeldaret/botw
    evtMetadata.h lays it out with 32-bit pointers and the vtable last:
    event name buffer +0x20, entry point +0x6c, type +0xf8, flags +0x108."""
    def text(start, size):
        return descriptor[start:start + size].split(b"\0")[0].decode("utf-8", "replace")
    return {"flow": text(0x20, 64), "entry": text(0x6c, 128), "type": text(0xf8, 16),
            "flags": struct.unpack_from(">I", descriptor, 0x108)[0]}


def reset(process, base, address):
    """Empty the trace (records and lost count), to watch one experiment."""
    for offset in (16, 20):
        process.write(base + address + offset, bytes(4))


def assess(evidence):
    """Separate a visual success from usable launch evidence."""
    reasons = []
    if evidence.get("status") != "collected":
        reasons.append("trace not collected")
    if evidence.get("dropped"):
        reasons.append("request records lost")
    if evidence.get("contention_detected") or evidence.get("read_errors"):
        reasons.append("contention or read errors")
    targets = [e["sequence"] for e in evidence.get("events", [])
               if e.get("descriptor_name_candidate") == "Demo007_1"]
    if not targets:
        reasons.append("campfire request not observed")
    return dict(status="needs_review" if reasons else "collected", reasons=reasons,
                target_sequences=targets)


def verify_hooks(process, base, address):
    offset, labels = 0, {}
    for line in trace_source().splitlines():
        line = line.split(";", 1)[0].strip()
        if not line or line.startswith("[") or "=" in line:
            continue
        if line.endswith(":"):
            labels[line[:-1]] = offset
        else:
            offset += 4
    result = []
    for index, (site, original, name, *_) in enumerate(SITES, 1):
        word = int.from_bytes(process.read(base + site, 4), "big")
        displacement = word & 0x03fffffc
        if displacement & 0x02000000:
            displacement -= 0x04000000
        target = address + labels[f"apEvent{index}"]
        if word & 0xfc000003 != 0x48000000 or site + displacement != target:
            raise ValueError(f"event request hook missing/conflicting at {site:#x}")
        if process.read(base + target, 4) != bytes.fromhex("9421ffe0"):
            raise ValueError("event request prologue mismatch")
        result.append(dict(name=name, address=site, target=target, original=original))
    return result
