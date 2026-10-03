"""The AP tip channel's native code, run on a model of the game's tip widget.

The model reproduces what the disassembly shows (docs/reference/
ap_messages.md): 0x02fd4730 refuses a queued or shown index or a true flag,
else queues it at widget+0x1ba8; the update copies it to widget+0x1bb0 and
calls 0x02fd4848, whose text site hands {pointer, length} to the pane;
closing sets widget+0x1bb0 back to -1.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

from botw_client import tip_protocol as tp

ROOT = Path(__file__).resolve().parents[1]
WIDGET = 0x436D0000
FLAG = 0x30000000                    # live Flag<bool>
TABLE = 0x20000000                   # 23 entries of 16 bytes
TEXT_OBJECT = 0x46000000             # the game's {pointer, length}
GAME_TEXT = 0x47000000


class Machine:
    """Just enough PowerPC for the channel's code; game calls are Python."""

    def __init__(self, source: str):
        self.mem: dict[int, int] = {}
        self.reg = [0] * 32
        self.cr = 0
        self.lr = 0
        self.labels, self.code = {}, {}
        address = 0x01800000
        for line in source.splitlines():
            line = line.split(";", 1)[0].strip()
            if not line or line.startswith("[") or "=" in line:
                continue
            if line.endswith(":"):
                self.labels[line[:-1]] = address
            else:
                self.code[address] = line
                address += 4
        for address, line in self.code.items():
            if line.startswith(".int "):
                self.put(address, self.value(line[5:]))
        self.calls = []
        self.game = {}

    def value(self, text: str) -> int:
        text = text.strip()
        for suffix, fn in (("@ha", lambda v: ((v + 0x8000) >> 16) & 0xFFFF),
                           ("@l", lambda v: v & 0xFFFF)):
            if text.endswith(suffix):
                v = fn(self.labels[text[:-len(suffix)]])
                return v - 0x10000 if suffix == "@l" and v & 0x8000 else v
        if text in self.labels:
            return self.labels[text]
        return int(text, 0)

    def get(self, address, size=4):
        return int.from_bytes(bytes(self.mem.get(address + i, 0) for i in range(size)), "big")

    def put(self, address, value, size=4):
        for i, byte in enumerate((value & ((1 << (8 * size)) - 1)).to_bytes(size, "big")):
            self.mem[address + i] = byte

    def compare(self, a, b, signed=True):
        if signed:
            a, b = [(n & 0xFFFFFFFF) - (1 << 32 if n & 0x80000000 else 0) for n in (a, b)]
        self.cr = (8 if a < b else 4 if a > b else 2) << 28

    def run(self, label, lr=0xDEAD0000):
        pc, self.lr = self.labels[label], lr
        for _ in range(5000):
            if pc == lr:
                return self.reg[3]
            line = self.code[pc]
            pc += 4
            op, *args = re.split(r"[ ,]+", line)
            r = lambda a: int(a[1:])
            if op == ".int":
                word = self.value(args[0])
                if word == 0x7D800026:
                    self.reg[12] = self.cr
                elif word == 0x7D8FF120:
                    self.cr = self.reg[12]
                elif word != 0x7C0004AC:
                    raise AssertionError(f"code .int inattendu {word:#x}")
            elif op in ("li", "lis"):
                self.reg[r(args[0])] = (self.value(args[1]) << (16 if op == "lis" else 0)) & 0xFFFFFFFF
            elif op == "addi":
                self.reg[r(args[0])] = (self.reg[r(args[1])] + self.value(args[2])) & 0xFFFFFFFF
            elif op in ("lwz", "stw", "lbz", "stb", "stwu"):
                offset, base = re.fullmatch(r"(.+)\(r(\d+)\)", args[1]).groups()
                address = (self.reg[int(base)] + self.value(offset)) & 0xFFFFFFFF
                size = 1 if op in ("lbz", "stb") else 4
                if op.startswith("st"):
                    self.put(address, self.reg[r(args[0])], size)
                    if op == "stwu":
                        self.reg[int(base)] = address
                else:
                    self.reg[r(args[0])] = self.get(address, size)
            elif op in ("cmpwi", "cmpw", "cmplwi", "cmplw"):
                b = self.value(args[1]) if op.endswith("i") else self.reg[r(args[1])]
                self.compare(self.reg[r(args[0])], b, signed=op in ("cmpwi", "cmpw"))
            elif op in ("b", "beq", "bne", "blt", "bge", "bgt"):
                lt, gt, eq = (bool(self.cr >> 31 & 1), bool(self.cr >> 30 & 1),
                              bool(self.cr >> 29 & 1))
                if {"b": True, "beq": eq, "bne": not eq, "blt": lt, "bge": not lt,
                        "bgt": gt}[op]:
                    pc = self.value(args[0])
            elif op == "slwi":
                self.reg[r(args[0])] = (self.reg[r(args[1])] << self.value(args[2])) & 0xFFFFFFFF
            elif op == "ori":
                self.reg[r(args[0])] = self.reg[r(args[1])] | self.value(args[2])
            elif op in ("add", "or"):
                a, b = self.reg[r(args[1])], self.reg[r(args[2])]
                self.reg[r(args[0])] = ((a + b) if op == "add" else (a | b)) & 0xFFFFFFFF
            elif op == "rlwinm":
                value, sh, mb, me = (self.reg[r(args[1])], *(self.value(a) for a in args[2:5]))
                rot = ((value << sh) | (value >> (32 - sh))) & 0xFFFFFFFF if sh else value
                mask = sum(1 << (31 - i) for i in range(mb, me + 1))
                self.reg[r(args[0])] = rot & mask
            elif op == "mr":
                self.reg[r(args[0])] = self.reg[r(args[1])]
            elif op == "mflr":
                self.reg[r(args[0])] = self.lr
            elif op == "mtlr":
                self.lr = self.reg[r(args[0])]
            elif op == "bl":
                target = self.value(args[0])
                self.calls.append(target)
                self.reg[3] = self.game[target](self) & 0xFFFFFFFF
            elif op == "blr":
                pc = self.lr
            else:
                raise AssertionError(f"instruction not modeled: {line}")
        raise AssertionError("the program does not end")


class Game:
    """The tip widget and the two game functions, after the disassembly."""

    def __init__(self, m: Machine, flag=False):
        self.m = m
        m.reg[1] = 0x0F000000
        m.put(WIDGET + tp.QUEUED, 0xFFFFFFFF)
        m.put(WIDGET + tp.SHOWN, 0xFFFFFFFF)
        m.put(tp.TABLE_POINTER, TABLE)
        m.put(FLAG + tp.BOOL_HASH, tp.TIP_KEY_HASH)
        m.put(FLAG + tp.BOOL_VALUE, 0x80 | int(flag), 1)
        m.game[tp.FLAG_GETTER] = self.getter
        m.game[tp.REQUEST] = self.request
        self.data = m.labels["apTipData"]

    def field(self, name, value=None):
        if value is not None:
            self.m.put(self.data + tp.OFFSETS[name], value)
        return self.m.get(self.data + tp.OFFSETS[name])

    def flag(self):
        return self.m.get(FLAG + tp.BOOL_VALUE, 1) & 1

    def getter(self, m):
        assert m.reg[3] == TABLE + tp.TIP_INDEX * 16 + 8 and m.reg[4] == 0
        return self.flag()

    def request(self, m):
        widget, index, force = m.reg[3], m.reg[4], m.reg[5]
        assert widget == WIDGET and force == 1
        if (index >= 23 or m.get(WIDGET + tp.SHOWN) == index or self.flag()):
            return 0
        m.put(WIDGET + tp.QUEUED, index)
        return 0

    def frame(self):
        """0x02fd4a1c: the hook at its site, then the queued tip moves on screen."""
        self.m.reg[31] = WIDGET
        self.m.run("apTipsProbe1")
        queued = self.m.get(WIDGET + tp.QUEUED)
        if queued != 0xFFFFFFFF and queued != self.m.get(WIDGET + tp.SHOWN):
            self.m.put(WIDGET + tp.SHOWN, queued)
            self.m.put(WIDGET + tp.QUEUED, 0xFFFFFFFF)
            self.show(queued)

    def show(self, index):
        """0x02fd4848 up to the text site: the game's text object, then the hook."""
        self.m.put(TEXT_OBJECT, GAME_TEXT)
        self.m.put(TEXT_OBJECT + 4, 40)
        self.m.reg[30], self.m.reg[31], self.m.reg[5] = WIDGET, index, TEXT_OBJECT
        self.m.run("apTipsSpy")

    def close(self):
        self.m.put(WIDGET + tp.SHOWN, 0xFFFFFFFF)

    def submit(self, units=5):
        self.field("flag_object", FLAG)
        self.field("units", units)
        return self.m.run("apTipSubmit")


def machine() -> Machine:
    from tools.build_native_from_source import generate
    # The native build carries the channel (the AP journal).
    native = generate(resource_gate=True, event_gate=True)["runtime/patch_apInject.asm"]
    return Machine(native.decode("utf-8"))


class TipChannelTests(unittest.TestCase):
    def test_our_text_replaces_the_borrowed_tip_and_the_flag_comes_back(self):
        for seen in (False, True):
            with self.subTest(flag_before=seen):
                m = machine()
                g = Game(m, flag=seen)
                g.frame()                                   # widget captured
                self.assertEqual(g.submit(), tp.ACCEPTED)
                self.assertEqual(g.flag(), 0)               # cleared for the request
                self.assertEqual(g.field("phase"), tp.REQUESTED)
                g.frame()                                   # shown, our text set
                self.assertEqual(m.get(TEXT_OBJECT), m.labels["apTipText"])
                self.assertEqual(m.get(TEXT_OBJECT + 4), 5)
                self.assertEqual(g.field("phase"), tp.SHOWN_PHASE)
                g.frame()
                self.assertEqual(g.field("phase"), tp.SHOWN_PHASE)
                g.close()
                g.frame()                                   # closed: completed
                self.assertEqual(g.field("phase"), tp.IDLE)
                self.assertEqual(g.field("completed"), g.field("generation"))
                self.assertEqual(g.field("outcome"), tp.CLOSED)
                self.assertEqual(g.flag(), int(seen))       # as it was
                self.assertEqual(m.get(FLAG + tp.BOOL_VALUE, 1) & 0x80, 0x80)

    def test_the_vanilla_tip_keeps_its_own_text(self):
        m = machine()
        g = Game(m)
        g.frame()
        g.show(tp.TIP_INDEX)                                # the game's own request
        self.assertEqual(m.get(TEXT_OBJECT), GAME_TEXT)
        g.show(4)
        self.assertEqual(m.get(TEXT_OBJECT), GAME_TEXT)

    def test_busy_while_active_or_while_the_tip_is_on_screen(self):
        m = machine()
        g = Game(m)
        self.assertEqual(g.submit(), tp.BUSY)               # widget never seen
        g.frame()
        m.put(WIDGET + tp.SHOWN, tp.TIP_INDEX)              # vanilla tip on screen
        self.assertEqual(g.submit(), tp.BUSY)
        self.assertEqual(m.calls, [])
        m.put(WIDGET + tp.SHOWN, 0xFFFFFFFF)
        self.assertEqual(g.submit(), tp.ACCEPTED)
        self.assertEqual(g.submit(), tp.BUSY)               # ours active

    def test_busy_while_a_game_tip_is_queued_or_on_screen(self):
        # Measured on 03/10: forced over the heat warning (6), which the game asks
        # for again at once, ours was evicted and the warning came back in a loop.
        for slot in (tp.QUEUED, tp.SHOWN):
            with self.subTest(slot=hex(slot)):
                m = machine()
                g = Game(m)
                g.frame()
                m.put(WIDGET + slot, 6)
                self.assertEqual(g.submit(), tp.BUSY)
                self.assertEqual((m.calls, g.field("phase"), g.flag()), ([], tp.IDLE, 0))
                m.put(WIDGET + slot, 0xFFFFFFFF)
                self.assertEqual(g.submit(), tp.ACCEPTED)

    def test_a_refused_request_gives_the_flag_back_at_once(self):
        m = machine()
        g = Game(m, flag=True)
        g.frame()
        m.game[tp.REQUEST] = lambda _m: 0                   # the game refuses
        self.assertEqual(g.submit(), tp.REFUSED_BY_GAME)
        self.assertEqual(g.flag(), 1)
        self.assertEqual((g.field("phase"), g.field("outcome")), (tp.IDLE, tp.REFUSED))
        self.assertEqual(g.field("completed"), g.field("generation"))

    def test_a_request_that_never_shows_is_dropped(self):
        m = machine()
        g = Game(m)
        g.frame()
        self.assertEqual(g.submit(), tp.ACCEPTED)
        m.put(WIDGET + tp.QUEUED, 0xFFFFFFFF)               # cancelled by the game
        for _ in range(tp.DROP_FRAMES):
            g.frame()
        self.assertEqual((g.field("phase"), g.field("outcome")), (tp.IDLE, tp.DROPPED))
        self.assertEqual(g.flag(), 0)

    def test_invalid_inputs_touch_nothing(self):
        for name, value in (("units", 0), ("units", tp.TEXT_UNITS + 1),
                            ("flag_object", 0x0100), ("flag_hash", 1)):
            with self.subTest(field=name):
                m = machine()
                g = Game(m, flag=True)
                g.frame()
                g.field("flag_object", FLAG)
                g.field("units", 5)
                g.field(name, value)
                self.assertEqual(m.run("apTipSubmit"), tp.INVALID)
                self.assertEqual((g.flag(), m.calls), (1, []))

    def test_registers_and_condition_register_survive_the_frame_hook(self):
        m = machine()
        g = Game(m)
        m.cr = 0x12345678
        before = list(m.reg)
        g.frame()
        self.assertEqual(m.cr, 0x12345678)
        preserved = [i for i in range(32) if i not in (0, 10, 11, 12)]
        self.assertEqual([m.reg[i] for i in preserved], [before[i] if i != 31 else WIDGET
                                                         for i in preserved])


if __name__ == "__main__":
    unittest.main()
