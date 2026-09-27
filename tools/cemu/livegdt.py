"""Read and write the GameData flags the game REALLY consults, live.

A flag has two storages:

  * an array of 8-byte entries `{hash, value}`, the one gdt_index.py locates.
    The save serializes it, but the engine does not consult it during play.
    Writing there only takes effect after a reload.

  * the live flag objects, reached from the GameDataMgr singleton. They are
    what the game's getters read. A raw write here is volatile: it bypasses
    the change recording of the native setters. AP flags changed this way
    were measured still at zero on disk after a save. Do not use this method
    as proof of a persistent delivery.

Access chain, found by disassembly then checked in memory:

    *(0x1046D5B0)          -> GameDataMgr
    mgr->0x710             -> pointer
    *(mgr->0x710)          -> TriggerParam
    TriggerParam->0x04     -> number of bools
    TriggerParam->0x0C     -> array of POINTERS (4 bytes each)
    array[index]           -> flag object, 16 bytes

Flag object:

    +0x00  shared pointer (identical for every flag)
    +0x04  properties in the high 16 bits, VALUE in the low 16 bits
           -> the boolean's low byte is therefore at +0x07
    +0x08  hash
    +0x0C  0

Use:

    python tools/cemu/livegdt.py IsGet_Obj_IceMaker          # read
    python tools/cemu/livegdt.py IsGet_Obj_IceMaker 1 --write # write
    python tools/cemu/livegdt.py CurrentHart --watch          # changes
"""
import pathlib
import struct
import sys
import time
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winmem import Process
from mailbox import be, cemu_pid, find_cave, guest_base
from gdt_index import load_flags

GDT_MGR_PTR = 0x1046D5B0

# These flags belong to the mod, so they are not in the index extracted from
# the vanilla game. They become visible once the AP Bootup.pack is installed
# and Cemu fully restarted.
CUSTOM_FLAGS = {
    "APReceivedCursor": (zlib.crc32(b"APReceivedCursor") & 0xFFFFFFFF, "s32"),
    "APSeedToken": (zlib.crc32(b"APSeedToken") & 0xFFFFFFFF, "s32"),
}

# Wii U 1.5.0. TriggerParam begins with a u32 then one 12-byte PtrArray per
# scalar type.  The bool offsets below are the layout measured in game.  S32
# and F32 are the immediately following arrays; their Flag<T> layout follows
# the same prefix, with {initial, min, max, value, hash} starting at +0x08.
# S32/F32 offsets were first identified from the type layout, then measured:
# MaxHartValue=12, StaminaMax=1000.0, KorokNutsNum=1 and CurrentRupee=0 were
# read, rewritten unchanged, and read back identically. Their memory layout is
# verified; what a changed value does in the game is a separate question.
TYPE_LAYOUT = {
    "bool": {"count": 0x04, "array": 0x0C, "size": 0x10,
             "value": 0x07, "hash": 0x08},
    "s32":  {"count": 0x10, "array": 0x18, "size": 0x20,
             "value": 0x14, "hash": 0x18},
    "f32":  {"count": 0x1C, "array": 0x24, "size": 0x20,
             "value": 0x14, "hash": 0x18},
}


def read_u32(p, address, label):
    raw = p.read(address, 4)
    if raw is None or len(raw) != 4:
        raise RuntimeError(f"memory read failed: {label}")
    return be(raw)


class LiveGdt:
    """Index (type, hash) -> guest address of the live flag object."""

    def __init__(self, p, base):
        self.p = p
        self.base = base
        mgr = read_u32(p, base + GDT_MGR_PTR, "GameDataMgr")
        if not (0x10000000 <= mgr < 0x60000000):
            raise RuntimeError(f"invalid GameDataMgr ({mgr:#010x}) - is a save loaded?")
        self.mgr = mgr
        tp_ptr = read_u32(p, base + mgr + 0x710, "TriggerParam pointer")
        self.tp = read_u32(p, base + tp_ptr, "TriggerParam")
        self.index = {kind: {} for kind in TYPE_LAYOUT}

    def build(self, kinds=("bool", "s32", "f32")):
        """Read the pointer arrays of the requested scalar types."""
        total = 0
        for kind in kinds:
            layout = TYPE_LAYOUT[kind]
            count = read_u32(
                self.p, self.base + self.tp + layout["count"],
                f"{kind} count")
            array = read_u32(
                self.p, self.base + self.tp + layout["array"],
                f"{kind} array")
            if not count or not (0x10000000 <= array < 0x60000000):
                continue
            raw = self.p.read(self.base + array, count * 4)
            if not raw or len(raw) != count * 4:
                continue
            ptrs = struct.unpack(f">{count}I", raw)
            valid = [q for q in ptrs if 0x10000000 <= q < 0x60000000]
            if not valid:
                continue
            low, high = min(valid), max(valid) + layout["size"]
            blob = self.p.read(self.base + low, high - low) if (
                high - low < 64 << 20) else None
            for q in valid:
                offset = q - low + layout["hash"]
                hraw = (blob[offset:offset + 4] if blob is not None
                        else self.p.read(self.base + q + layout["hash"], 4))
                if hraw is not None and len(hraw) == 4:
                    self.index[kind].setdefault(be(hraw), q)
            total += len(self.index[kind])
        return total

    def get(self, hash_u32, kind="bool"):
        """Read a scalar value in the live object.

        For a bool, bit 0 alone is the value. For s32/f32, the value is the
        word at +0x14 in the Wii U Flag<T>.
        """
        layout = TYPE_LAYOUT[kind]
        a = self.index[kind].get(hash_u32)
        if a is None:
            return None
        raw = self.p.read(self.base + a + layout["value"], 1 if kind == "bool" else 4)
        if not raw:
            return None
        if kind == "bool":
            return raw[0] & 1
        if kind == "s32":
            return struct.unpack(">i", raw)[0]
        return struct.unpack(">f", raw)[0]

    def set(self, hash_u32, value, kind="bool"):
        """A raw memory write, with no persistence guarantee nor native setter."""
        layout = TYPE_LAYOUT[kind]
        a = self.index[kind].get(hash_u32)
        if a is None:
            return False
        addr = self.base + a + layout["value"]
        if kind == "bool":
            current = self.p.read(addr, 1)
            if not current:
                return False
            cur = current[0]
            data = bytes([(cur & 0xFE) | (1 if value else 0)])
        elif kind == "s32":
            data = struct.pack(">i", int(value))
        else:
            data = struct.pack(">f", float(value))
        return self.p.write(addr, data)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    flag = args[0]
    value = float(args[1]) if len(args) > 1 and "." in args[1] else (
        int(args[1]) if len(args) > 1 else None)
    do_write = "--write" in sys.argv

    pid = cemu_pid()
    if not pid:
        sys.exit("Cemu is not running")
    _, type_of, hash_of = load_flags()
    custom = CUSTOM_FLAGS.get(flag)
    h = custom[0] if custom else hash_of.get(flag)
    if h is None:
        sys.exit(f"unknown flag: {flag}")

    with Process(pid, writable=do_write) as p:
        cave = find_cave(p)
        if cave is None:
            sys.exit("code cave not found - is the graphic pack enabled?")
        base, _, _ = guest_base(p, cave - 12)
        g = LiveGdt(p, base)
        n = g.build()
        print(f"TriggerParam {g.tp:#010x}, {n} scalars indexed")

        kind = custom[1] if custom else type_of.get(h)
        if kind not in TYPE_LAYOUT:
            sys.exit(f"type {kind} not supported (bool, s32 and f32 only)")
        cur = g.get(h, kind)
        if cur is None:
            sys.exit(f"{flag} missing from the live array "
                     f"(type {kind})")
        obj = g.index[kind][h]
        value_address = obj + TYPE_LAYOUT[kind]["value"]
        print(f"{flag} = {cur}   object {obj:#010x}   value {value_address:#010x}")

        if "--watch" in sys.argv:
            print("watching at 20 Hz; Ctrl+C to stop")
            started = time.monotonic()
            previous = cur
            try:
                while True:
                    time.sleep(0.05)
                    current = g.get(h, kind)
                    if current != previous:
                        elapsed = time.monotonic() - started
                        print(f"{elapsed:9.3f}s  {flag}: {previous} -> {current}",
                              flush=True)
                        previous = current
            except KeyboardInterrupt:
                print("stopped")
            return

        if value is None or not do_write:
            if value is not None:
                print("\ndry run - add --write to apply")
            return
        g.set(h, value, kind)
        print(f"-> {g.get(h, kind)}")


if __name__ == "__main__":
    main()
