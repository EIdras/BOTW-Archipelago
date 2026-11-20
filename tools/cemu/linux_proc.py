"""Linux discovery of the running Cemu emulator, reading /proc directly.

A Cemu AppImage runs as two processes: the emulator (its command line is the
AppImage path, e.g. /home/ac/Cemu/Cemu-2.6-x86_64.AppImage) and the FUSE mount
shim under /tmp/.mount_*. Only the emulator holds the game's memory, so
discovery keeps the Cemu match, skips the shim, and prefers the match whose
command line contains .AppImage. Reading /proc/*/cmdline directly (not a pgrep
string) keeps this testable.
"""
import os

CEMU = "Cemu"
MOUNT_SHIM = "/tmp/.mount_"


def find_cemu_pid(environ=os.environ, proc_dir="/proc"):
    """PID of the running Cemu emulator, or None. Honours an explicit
    BOTW_CEMU_PID, then scans /proc for the AppImage Cemu match."""
    explicit = environ.get("BOTW_CEMU_PID")
    if explicit is not None:
        if not explicit.isdigit() or int(explicit) <= 0:
            raise ValueError("BOTW_CEMU_PID must be a positive process ID")
        return int(explicit)
    emulator = None
    with os.scandir(proc_dir) as entries:
        for entry in entries:
            if not entry.name.isdigit():
                continue
            try:
                with open(entry.path + "/cmdline", "rb") as stream:
                    cmdline = stream.read().replace(b"\x00", b" ").strip().decode("utf-8", "replace")
            except OSError:
                continue
            if MOUNT_SHIM in cmdline or CEMU not in cmdline:
                continue
            if ".AppImage" in cmdline:
                return int(entry.name)
            emulator = int(entry.name)
    return emulator
