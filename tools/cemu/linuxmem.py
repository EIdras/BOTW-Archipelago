"""Read another process's memory (Linux, 64-bit).

The Windows side is tools/cemu/winmem.py (kernel32). This is the same small
interface over /proc, so every caller sees one Process and no OS:

    Process.for_pid(pid, writable=...)   # the factory in tools/cemu/__init__
    p.regions(min_size) -> (base, size)  # committed, readable, non-guarded
    p.read(address, size) -> bytes|None
    p.write(address, data) -> bool
    p.close();  p.h, p.pid, p.writable

/proc/<pid>/mem is writable by any process of the same user without CAP_SYS_PTRACE,
which matches the "run as the same user as Cemu" expectation. A region that cannot
be read returns None from read(), and open() raises when the process is not visible.

Testable without Cemu: arm /proc/self and exercise read/regions/write here.
"""
from __future__ import annotations

import os
from pathlib import Path

PAGE = 4096


class Process:
    def __init__(self, pid: int, writable: bool = False):
        self.pid = pid
        self.writable = writable
        # .h is the open /proc/<pid>/mem descriptor, the analogue of the kernel32 handle.
        flags = os.O_RDWR if writable else os.O_RDONLY
        self.h = os.open(f"/proc/{pid}/mem", flags)
        if self.h < 0:
            raise OSError(f"cannot open /proc/{pid}/mem - run this as the same user as Cemu")

    def close(self):
        if self.h is not None:
            os.close(self.h)
            self.h = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def regions(self, min_size=0):
        """Yield (base, size) of committed, readable, non-guarded regions.

        The direct analogue of VirtualQueryEx: /proc/<pid>/maps already lists only
        committed regions, so we filter on the perms column instead of a State field.
        'g' marks a guard region and is skipped alongside anything unreadable.
        """
        text = Path(f"/proc/{self.pid}/maps").read_text(encoding="utf-8", errors="replace")
        for line in text.splitlines():
            fields = line.split(None, 5)
            if len(fields) < 5:
                continue
            perms = fields[1]
            base, end = (int(x, 16) for x in fields[0].split("-"))
            size = end - base
            if size >= min_size and perms[0] == "r" and "g" not in perms:
                yield base, size

    def read(self, address: int, size: int) -> bytes | None:
        """Read `size` bytes at `address`, or None if any page is unmappable.

        Read a page at a time: a single fault mid-range must return None, not a
        partial buffer that hides it. This matches winmem, which returns None when
        ReadProcessMemory fails for the request.
        """
        out = bytearray()
        cur, remaining = address, size
        while remaining > 0:
            want = min(remaining, PAGE)
            try:
                chunk = os.pread(self.h, want, cur)
            except OSError:
                # An unmapped or protected page faults here (EIO); that is the
                # Linux analogue of ReadProcessMemory failing: report None.
                return None
            if not chunk:
                return None
            out += chunk
            cur += want
            remaining -= want
        return bytes(out)

    def write(self, address: int, data: bytes) -> bool:
        """Write bytes into the target process. Requires writable=True."""
        if not self.writable:
            raise PermissionError("Process was opened read-only; pass writable=True")
        put = 0
        while put < len(data):
            put += os.pwrite(self.h, data[put:], address + put)
        return put == len(data)
