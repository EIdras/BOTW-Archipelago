"""Small instruction interpreter for owner_source, not an emulator of BOTW.

Exercises the emitted assembly's branches, register preservation, stores and
publication order. Atomic reservations are serial here; forced failure tests
cover the fail-closed path, not real multicore scheduling.
"""
import re
from tools.build_owned_presentation import owner_source


class PpcOwnerModel:
    def __init__(self, source=None):
        self.labels = dict(apTick=0x01800010, apSubReq=0x01800100,
                           apSubDescReq=0x01800104, apSubAuto=0x01800108)
        self.code, self.memory, self.writes = {}, {}, []
        self.reg = {i: 0x12340000+i for i in range(32)}
        self.reg[1] = 0x0E200000
        self.lr, self.cr = 0x11223344, 0xA5A5A5A5
        self.fail_reservation = False
        self.native = lambda: 1
        self.resource_ready = 1
        self.resource_method = 0x43000000
        manager, resource, vtable = 0x50000000, 0x51000000, 0x52000000
        self.put(0x1046D3AC, manager)
        self.put(manager + 0x174A4, resource)
        self.put(resource, vtable)
        self.put(vtable + 0xB4, self.resource_method)
        address = 0x01805000
        defined = set()
        for line in (owner_source() if source is None else source).splitlines():
            line = line.split(";", 1)[0].strip()
            if not line or "=" in line or line.startswith('['):
                continue
            if line.endswith(":"):
                # Cemu refuses a label defined twice ("Label ... is already
                # defined"); the model must too (the message pack hit it).
                if line[:-1] in defined:
                    raise ValueError(f"label defined twice: {line[:-1]}")
                defined.add(line[:-1])
                self.labels[line[:-1]] = address
            else:
                self.code[address] = line
                address += 4
        for address, line in self.code.items():
            if line.startswith(".int "):
                self.put(address, self.value(line[5:]))
        self.writes.clear()

    def value(self, value):
        if value.endswith("@ha"):
            return (self.labels[value[:-3]]+0x8000) >> 16
        if value.endswith("@l"):
            raw = self.labels[value[:-2]] & 0xFFFF
            return raw - 0x10000 if raw & 0x8000 else raw
        return self.labels[value] if value in self.labels else int(value, 0)

    def get(self, address, size=4):
        return int.from_bytes(bytes(self.memory.get(address+i, 0) for i in range(size)), "big")

    def put(self, address, value, size=4):
        value &= (1 << (size*8))-1
        self.writes.append((address, value, size))
        for i, byte in enumerate(value.to_bytes(size, "big")):
            self.memory[address+i] = byte

    def field(self, offset, value=None):
        address = self.labels["apOwnedData"] + offset
        if value is not None:
            self.put(address, value)
        return self.get(address)

    def quotas(self):
        return tuple(self.get(self.labels[n]) for n in ("apSubReq", "apSubDescReq", "apSubAuto"))

    def compare(self, a, b):
        nibble = 8 if a < b else 4 if a > b else 2
        self.cr = (self.cr & 0x0FFFFFFF) | (nibble << 28)

    def run(self, label):
        pc = self.labels[label]
        returns = []
        for _ in range(1500):
            if pc not in self.code:
                return self.reg[3]
            line = self.code[pc]
            pc += 4
            if line.startswith(".int "):
                word = self.value(line[5:])
                if word == 0x7C000026:
                    self.reg[0] = self.cr
                elif word == 0x7C0FF120:
                    self.cr = self.reg[0]
                elif word == 0x7D206028:
                    self.reg[9] = self.get(self.reg[12])
                elif word == 0x7D20612D:
                    self.compare(0, 1 if self.fail_reservation else 0)
                    if not self.fail_reservation:
                        self.put(self.reg[12], self.reg[9])
                elif word == 0x7C0004AC:
                    pass
                elif word == 0x389E001C:
                    self.reg[4] = (self.reg[30]+0x1C) & 0xFFFFFFFF
                elif word == 0x61080004:
                    self.reg[8] |= 4
                elif word == 0x3FE01048:
                    self.reg[31] = 0x10480000
                elif word == 0x99830025:
                    self.put(self.reg[3]+0x25, self.reg[12], 1)
                elif word == 0x9421FFE0:
                    address = self.reg[1]-32
                    self.put(address,self.reg[1])
                    self.reg[1]=address
                elif word in (0x907D0000,0x93EB0000):
                    self.put(self.reg[(word>>16)&31],self.reg[(word>>21)&31])
                elif word == 0x815B00FC:
                    self.reg[10]=self.get(self.reg[27]+0xfc)
                elif word == 0x7F43D378:
                    self.reg[3]=self.reg[26]
                elif word == 0x3BBD0001:
                    self.reg[29]=(self.reg[29]+1)&0xffffffff
                else:
                    raise AssertionError(f"unsupported opcode {word:#x}")
                continue
            op, *args = re.split(r"[ ,]+", line)
            reg = lambda value: int(value[1:])
            if op in ("li", "lis"):
                self.reg[reg(args[0])] = (self.value(args[1]) << (16 if op == "lis" else 0)) & 0xFFFFFFFF
            elif op in ("addi", "addis"):
                dst, src = reg(args[0]), reg(args[1])
                immediate = self.value(args[2]) << (16 if op == "addis" else 0)
                self.reg[dst] = ((self.reg[src] if src else 0) + immediate) & 0xFFFFFFFF
            elif op in ("lwz", "stw", "stwu", "lbz", "stb"):
                dst = reg(args[0])
                offset, src = re.fullmatch(r"(.+)\(r(\d+)\)", args[1]).groups()
                src = int(src)
                address = ((self.reg[src] if src else 0) + self.value(offset)) & 0xFFFFFFFF
                if op.startswith("st"):
                    self.put(address, self.reg[dst], 1 if op=='stb' else 4)
                    if op == "stwu":
                        self.reg[src] = address
                else:
                    self.reg[dst] = self.get(address, 1 if op == "lbz" else 4)
            elif op in ('ori','slwi','add'):
                dst,src=reg(args[0]),reg(args[1])
                value=self.reg[src]
                self.reg[dst]=((value|self.value(args[2])) if op=='ori' else
                    (value<<self.value(args[2])) if op=='slwi' else value+self.reg[reg(args[2])])&0xffffffff
            elif op in ("cmpwi", "cmpw", "cmplw", "cmplwi"):
                a = self.reg[reg(args[0])]
                b = self.value(args[1]) if op in ("cmpwi","cmplwi") else self.reg[reg(args[1])]
                if op not in ("cmplw","cmplwi"):
                    signed = lambda n: (n & 0xFFFFFFFF) - (0x100000000 if n & 0x80000000 else 0)
                    a, b = signed(a), signed(b)
                self.compare(a, b)
            elif op in ("beq", "bne", "blt", "bge", "b"):
                eq, lt = bool(self.cr & 0x20000000), bool(self.cr & 0x80000000)
                if {"beq": eq, "bne": not eq, "blt": lt, "bge": not lt, "b": True}[op]:
                    pc = self.value(args[0])
            elif op == "mflr":
                self.reg[reg(args[0])] = self.lr
            elif op == 'mr':
                self.reg[reg(args[0])] = self.reg[reg(args[1])]
            elif op == "mtlr":
                self.lr = self.reg[reg(args[0])]
            elif op == "mtctr":
                self.ctr = self.reg[reg(args[0])]
            elif op == "bctrl":
                assert self.ctr == self.resource_method
                self.lr = pc
                self.reg[3] = self.resource_ready & 0xFFFFFFFF
            elif op == "bl":
                self.lr = pc
                if args[0] in self.labels:
                    returns.append(pc)
                    pc = self.labels[args[0]]
                else:
                    assert args[0] == "0x02ddf744"
                    self.reg[3] = self.native() & 0xFFFFFFFF
            elif op == "blr":
                if returns:
                    pc = returns.pop()
                else:
                    return self.reg[3]
            else:
                raise AssertionError(f"unsupported instruction {line}")
        raise AssertionError("owner program did not terminate")
