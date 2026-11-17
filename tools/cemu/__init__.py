"""Process-memory access for Cemu, behind one factory so callers see no OS.

    from tools.cemu import Process
    p = Process(pid, writable=True)   # winmem.Process on Windows, linuxmem.Process on Linux

The guest side (guest.py, mailbox.py, the client) never imports a backend directly;
it talks to whichever Process the factory returns. See tools/cemu/linuxmem.py and
tools/cemu/winmem.py for the two backends, which share this interface by construction.
"""
from __future__ import annotations

import sys

if sys.platform == "win32":
    from .winmem import Process
else:
    from .linuxmem import Process


def for_pid(pid: int, writable: bool = False) -> Process:
    """Open `pid` with the platform backend. Alias of the Process constructor."""
    return Process(pid, writable=writable)
