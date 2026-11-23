"""Access to another process's memory (Linux, 64-bit), the counterpart of winmem.py.

The same small interface as winmem.Process, over /proc/<pid>/maps and
/proc/<pid>/mem: regions(min_size), read(address, size), write(address, data),
close(), and the pid, writable and h attributes (h is the open
/proc/<pid>/mem file, None once closed). procmem.py picks the backend.

Opening /proc/<pid>/mem is a ptrace access check. Under Yama's ptrace_scope 1
(Ubuntu, Fedora, SteamOS) only an ancestor of the target passes it: the
session starts Cemu itself, so the client may read it, while a tool started
from another shell is refused.
"""
import os

USER_SPACE_END = 1 << 47        # winmem walks the same range; [vsyscall] lies above


def parse_maps(text: bytes, min_size: int = 0):
    """Yield (base, size) of the readable mappings listed in /proc/<pid>/maps.

    A mapping without the r permission (a reservation, a guard) is left out,
    the analogue of winmem's committed-and-readable filter.
    """
    for line in text.splitlines():
        fields = line.split(None, 2)
        if len(fields) < 2:
            continue
        start, _, end = fields[0].partition(b"-")
        try:
            base, stop = int(start, 16), int(end, 16)
        except ValueError:
            continue
        size = stop - base
        if (fields[1].startswith(b"r") and size > 0 and size >= min_size
                and stop <= USER_SPACE_END):
            yield base, size


class Process:
    def __init__(self, pid: int, writable: bool = False):
        self.pid = pid
        self.writable = writable
        path = f"/proc/{int(pid)}/mem"
        try:
            self.h = open(path, "r+b" if writable else "rb", buffering=0)
        except PermissionError as error:
            raise PermissionError(
                error.errno,
                f"cannot open {path}: run as the same user as Cemu, and start Cemu from "
                "this tool (kernel.yama.ptrace_scope lets only its parent read it)") from error

    def close(self):
        if self.h:
            self.h.close(); self.h = None

    def __enter__(self): return self
    def __exit__(self, *a): self.close()

    def regions(self, min_size=0):
        """Yield (base, size) of readable regions."""
        try:
            with open(f"/proc/{int(self.pid)}/maps", "rb") as maps:
                text = maps.read()
        except OSError:
            return
        yield from parse_maps(text, min_size)

    def read(self, address: int, size: int) -> bytes | None:
        """The bytes at address, or None if any of them cannot be read.

        One read for the whole range: the kernel stops at the first page it
        cannot reach, and a short read is a failure, as for ReadProcessMemory.
        """
        if not self.h:
            return None
        try:
            data = os.pread(self.h.fileno(), size, address)
        except (OSError, OverflowError, ValueError):
            return None
        if not data or len(data) != size:
            return None
        return data

    def write(self, address: int, data: bytes) -> bool:
        """Write bytes into the target process. Requires writable=True."""
        if not self.writable:
            raise PermissionError("Process was opened read-only; pass writable=True")
        if not self.h:
            return False
        data = bytes(data)
        try:
            put = os.pwrite(self.h.fileno(), data, address)
        except (OSError, OverflowError, ValueError):
            return False
        return put == len(data)
