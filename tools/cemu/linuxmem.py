"""Access to another process's memory (Linux, 64-bit), the counterpart of winmem.py.

The same small interface as winmem.Process, over /proc/<pid>/maps and
/proc/<pid>/mem: regions(min_size), read(address, size), write(address, data),
close(), and the pid, writable and h attributes (h is the open
/proc/<pid>/mem file, None once closed). procmem.py picks the backend.

Opening /proc/<pid>/mem is a ptrace access check. Under Yama's ptrace_scope 1
(Ubuntu, Fedora, SteamOS) only an ancestor of the target passes it: the
session starts Cemu itself, so the client may read it, while a tool started
from another shell is refused.

Also what Windows asks of kernel32 or PowerShell about Cemu's process: which
processes are Cemu (cemu_pids) and which run of a PID the client attached to
(incarnation).
"""
import os

USER_SPACE_END = 1 << 47        # winmem walks the same range; [vsyscall] lies above
CEMU_NAMES = (b"Cemu", b"cemu")  # the official builds, and the lower-case packages
EXITED = ("Z", "X", "x")         # zombie (exited, not yet reaped) or dead


def parse_stat(text: bytes) -> tuple[str, int]:
    """(state, start time in clock ticks after boot) of a /proc/<pid>/stat line.

    The process name between parentheses may itself hold spaces and
    parentheses: the fields are counted from the last closing one.
    """
    fields = text[text.rindex(b")") + 1:].split()
    return fields[0].decode("ascii"), int(fields[19])


def incarnation(pid: int) -> str:
    """'pid:start time' of a running process; raises RuntimeError once it exited.

    The start time tells a PID the system reused from the one attached to,
    as the creation time does on Windows.
    """
    try:
        with open(f"/proc/{int(pid)}/stat", "rb") as stat:
            state, start = parse_stat(stat.read())
    except (OSError, ValueError, IndexError) as error:
        raise RuntimeError("Cemu process exited") from error
    if state in EXITED:
        raise RuntimeError("Cemu process exited")
    return f"{int(pid)}:{start:016x}"


def is_cemu(process: str) -> bool:
    """Whether a /proc/<pid> folder is a Cemu: its process name, or the file it runs.

    Never a part of the command line: a launcher started with a Cemu path in
    its arguments is not Cemu. An AppImage runs its Cemu binary from its
    mount, so the executable's name tells it when the process name does not.
    """
    try:
        with open(os.path.join(process, "comm"), "rb") as comm:
            if comm.read().strip() in CEMU_NAMES:
                return True
        executable = os.readlink(os.path.join(process, "exe"))
    except OSError:
        return False
    return os.path.basename(executable).encode() in CEMU_NAMES


def cemu_pids(proc: str = "/proc") -> list[int]:
    """PIDs of the running Cemu processes, lowest first."""
    try:
        entries = [entry.name for entry in os.scandir(proc) if entry.name.isdigit()]
    except OSError:
        return []
    return sorted(int(name) for name in entries if is_cemu(os.path.join(proc, name)))


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
