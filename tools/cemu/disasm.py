"""Minimal PowerPC disassembler - enough of the integer/branch subset to read
BOTW's code from Python instead of loading the RPX into Ghidra.

    python tools/cemu/disasm.py 0x02eb583c 40

Not exhaustive: unknown encodings are printed as .long so nothing is silently
misread. If an instruction matters and shows up as .long, decode it by hand
rather than trusting a guess.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winmem import Process
from mailbox import cemu_pid, find_cave, guest_base


def _simm(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


D_FORM = {
    32: "lwz", 33: "lwzu", 34: "lbz", 35: "lbzu", 36: "stw", 37: "stwu",
    38: "stb", 39: "stbu", 40: "lhz", 41: "lhzu", 44: "sth", 45: "sthu",
    48: "lfs", 49: "lfsu", 50: "lfd", 52: "stfs", 53: "stfsu", 54: "stfd",
}

X_31 = {
    23: "lwzx", 87: "lbzx", 151: "stwx", 215: "stbx", 279: "lhzx",
    444: "or", 316: "xor", 28: "and", 60: "andc", 476: "nand",
    266: "add", 40: "subf", 235: "mullw", 491: "divw", 339: "mfspr",
    467: "mtspr", 20: "lwarx", 150: "stwcx.", 0: "cmpw", 32: "cmplw",
    24: "slw", 536: "srw", 792: "sraw", 824: "srawi", 954: "extsb",
    922: "extsh", 26: "cntlzw", 8: "subfc", 138: "adde", 202: "addze",
}

# A conditional branch tests ONE bit of CR, named by BI & 3:
#   0 = lt   1 = gt   2 = eq   3 = so
# and BO says whether to branch when that bit is true (12) or false (4).
# Looking at BO alone reads "bne" where the code says "ble" -- a
# confusion that once produced three wrong analyses in a row of the center
# message's state machine.
CR_BIT = {0: ("lt", "ge"), 1: ("gt", "le"), 2: ("eq", "ne"), 3: ("so", "ns")}


def disasm(w, pc):
    op = w >> 26
    d = (w >> 21) & 31
    a = (w >> 16) & 31
    b = (w >> 11) & 31
    simm = _simm(w)
    uimm = w & 0xFFFF

    if w == 0x60000000:
        return "nop"
    if op == 14:
        return f"li r{d}, {simm:#x}" if a == 0 else f"addi r{d}, r{a}, {simm:#x}"
    if op == 15:
        return f"lis r{d}, {uimm:#06x}" if a == 0 else f"addis r{d}, r{a}, {uimm:#06x}"
    if op in D_FORM:
        return f"{D_FORM[op]} r{d}, {simm:#x}(r{a})"
    if op == 11:
        return f"cmpwi r{a}, {simm:#x}"
    if op == 10:
        return f"cmplwi r{a}, {uimm:#x}"
    if op == 24:
        return f"ori r{a}, r{d}, {uimm:#x}" if w != 0x60000000 else "nop"
    if op == 28:
        return f"andi. r{a}, r{d}, {uimm:#x}"
    if op == 26:
        return f"xori r{a}, r{d}, {uimm:#x}"
    if op == 21:
        mb, me = (w >> 6) & 31, (w >> 1) & 31
        return f"rlwinm{'.' if w & 1 else ''} r{a}, r{d}, {b}, {mb}, {me}"
    if op == 18:                                   # b / bl / ba / bla
        li = w & 0x03FFFFFC
        if li & 0x02000000:
            li -= 0x04000000
        aa, lk = (w >> 1) & 1, w & 1
        tgt = li if aa else pc + li
        return f"{'bla' if aa and lk else 'ba' if aa else 'bl' if lk else 'b'} {tgt:#010x}"
    if op == 16:                                   # conditional branch
        bo, bi = d, a
        bd = w & 0xFFFC
        if bd & 0x8000:
            bd -= 0x10000
        aa, lk = (w >> 1) & 1, w & 1
        tgt = bd if aa else pc + bd
        crf, bit = bi >> 2, bi & 3
        if bo in (12, 13, 14, 15):
            cond = CR_BIT[bit][0]
        elif bo in (4, 5, 6, 7):
            cond = CR_BIT[bit][1]
        elif bo == 20:
            cond = ""
        elif bo == 16:
            cond = "dnz"
        elif bo == 18:
            cond = "dz"
        else:
            cond = f"bo={bo}"
        return f"b{cond} cr{crf}, {tgt:#010x}{'l' if lk else ''}"
    if op == 19:
        xo = (w >> 1) & 0x3FF
        lk = w & 1
        if xo == 16:
            base = "blr" if d == 20 else "bclr"
            return base + ("l" if lk else "")
        if xo == 528:
            # the LK bit tells a jump from a CALL: bctr jumps and does not come
            # back, bctrl calls and what follows runs. Mixing them up makes the
            # end of a function unreadable.
            base = "bctr" if d == 20 else "bcctr"
            return base + ("l" if lk else "")
        return f".long {w:#010x}  ; op19 xo={xo}"
    if op == 31:
        xo = (w >> 1) & 0x3FF
        if xo == 339:
            spr = ((w >> 16) & 0x1F) | (((w >> 11) & 0x1F) << 5)
            return f"mflr r{d}" if spr == 8 else f"mfspr r{d}, {spr}"
        if xo == 467:
            spr = ((w >> 16) & 0x1F) | (((w >> 11) & 0x1F) << 5)
            return f"mtlr r{d}" if spr == 8 else (f"mtctr r{d}" if spr == 9
                                                 else f"mtspr {spr}, r{d}")
        if xo == 444:
            return f"mr r{a}, r{d}" if d == b else f"or r{a}, r{d}, r{b}"
        if xo == 26:
            return f"cntlzw{'.' if w & 1 else ''} r{a}, r{d}"
        if xo in X_31:
            name = X_31[xo]
            if name in ("cmpw", "cmplw"):
                return f"{name} r{a}, r{b}"
            return f"{name} r{d}, r{a}, r{b}"
        return f".long {w:#010x}  ; op31 xo={xo}"
    return f".long {w:#010x}  ; op={op}"


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    start = int(sys.argv[1], 0)
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 32
    back = int(sys.argv[3]) if len(sys.argv) > 3 else 0

    pid = cemu_pid()
    if not pid:
        sys.exit("Cemu is not running")
    with Process(pid) as p:
        base, _, _ = guest_base(p, find_cave(p) - 12)
        if base is None:
            sys.exit("base not found - run mailbox.py first")
        pc = start - back * 4
        raw = p.read(base + pc, count * 4)
        for i in range(count):
            w = int.from_bytes(raw[i * 4:i * 4 + 4], "big")
            addr = pc + i * 4
            mark = "  <<<" if addr == start else ""
            print(f"  {addr:#010x}  {w:08x}  {disasm(w, addr)}{mark}")


if __name__ == "__main__":
    main()
