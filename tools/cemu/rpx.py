"""Read U-King.rpx offline: sections, bytes, disassembly.

Useful when Cemu is not running, and authoritative: it is the binary itself,
not a memory image that a graphic pack may already have patched.

    python tools/cemu/rpx.py sections
    python tools/cemu/rpx.py dis 0x02EB53E4 20
    python tools/cemu/rpx.py str 0x1021b694
"""
import pathlib
import struct
import sys
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from disasm import disasm

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
RPX = ROOT / "U-King.rpx"
ZLIB_FLAG = 0x08000000


class Rpx:
    def __init__(self, path=RPX):
        self.d = pathlib.Path(path).read_bytes()
        shoff, = struct.unpack_from(">I", self.d, 0x20)
        shentsize, shnum, shstrndx = struct.unpack_from(">HHH", self.d, 0x2E)
        self.sections = []
        for i in range(shnum):
            f = struct.unpack_from(">10I", self.d, shoff + i * shentsize)
            self.sections.append(dict(i=i, name=f[0], typ=f[1], flags=f[2],
                                      addr=f[3], off=f[4], size=f[5]))
        self._strtab = self._raw(self.sections[shstrndx])

    def _raw(self, h):
        raw = self.d[h["off"]: h["off"] + h["size"]]
        if h["flags"] & ZLIB_FLAG and len(raw) > 4:
            try:
                return zlib.decompress(raw[4:])
            except zlib.error:
                return raw
        return raw

    def name(self, h):
        x = h["name"]
        e = self._strtab.find(b"\x00", x)
        return self._strtab[x:e].decode("ascii", "replace")

    def find(self, addr):
        """Section containing a guest address, with its decompressed bytes."""
        for h in self.sections:
            if not h["addr"] or not (h["flags"] & 0x2):
                continue
            data = self._raw(h)
            if h["addr"] <= addr < h["addr"] + len(data):
                return h, data
        return None, None

    def read(self, addr, n):
        h, data = self.find(addr)
        if h is None:
            return None
        o = addr - h["addr"]
        return data[o:o + n]


def cmd_sections(r):
    print(f"{'idx':>3}  {'name':<18} {'address':>10} {'size':>10}")
    for h in r.sections:
        if not h["size"]:
            continue
        data = r._raw(h)
        print(f"{h['i']:>3}  {r.name(h):<18} {h['addr']:#010x} {len(data):>10}")


def cmd_dis(r, addr, count):
    raw = r.read(addr, count * 4)
    if raw is None:
        sys.exit(f"{addr:#x} is in no loaded section")
    for i in range(count):
        w = int.from_bytes(raw[i * 4:i * 4 + 4], "big")
        a = addr + i * 4
        print(f"  {a:#010x}  {w:08x}  {disasm(w, a)}")


def cmd_str(r, addr):
    raw = r.read(addr, 200)
    if raw is None:
        sys.exit(f"{addr:#x} is in no loaded section")
    print(repr(raw.split(b"\x00")[0].decode("ascii", "replace")))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    r = Rpx()
    c = sys.argv[1]
    if c == "sections":
        cmd_sections(r)
    elif c == "dis":
        cmd_dis(r, int(sys.argv[2], 0), int(sys.argv[3]) if len(sys.argv) > 3 else 16)
    elif c == "str":
        cmd_str(r, int(sys.argv[2], 0))
    else:
        sys.exit(__doc__)
