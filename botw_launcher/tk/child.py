"""A job's child process (botw_launcher/jobs.py), started by multiprocessing.

Inside a frozen Archipelago, there is no Python to start with a command line,
and a windowed program has no standard streams: the child's streams are queues
to the window instead. What the job prints and the events it emits go out on
`lines`, what the player types comes in on `typed`, as jobs.py expects them on
its standard output and input.
"""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import sys


class _Out(io.TextIOBase):
    """Text to the window, line by line. Its descriptor is a file of the logs'
    folder: faulthandler writes a hard crash there (tools/play_session.py)."""

    def __init__(self, lines, crash: Path):
        self.lines, self.pending, self.crash = lines, "", crash
        self._descriptor: int | None = None

    def write(self, text: str) -> int:
        self.pending += text
        *done, self.pending = self.pending.split("\n")
        for line in done:
            self.lines.put(line)
        return len(text)

    def flush(self) -> None:
        pass

    def fileno(self) -> int:
        if self._descriptor is None:
            self.crash.parent.mkdir(parents=True, exist_ok=True)
            self._descriptor = os.open(self.crash, os.O_WRONLY | os.O_CREAT | os.O_APPEND)
        return self._descriptor

    def isatty(self) -> bool:
        return False


class _In(io.TextIOBase):
    def __init__(self, typed):
        self.typed = typed

    def readline(self, *_size) -> str:
        line = self.typed.get()
        return "" if line is None else line + "\n"

    def isatty(self) -> bool:
        return False


def run(name: str, arguments: dict, lines, typed) -> None:
    """Run the job `name`; its last line is the outcome (jobs.py), then None."""
    from botw_client.paths import DATA
    out = _Out(lines, DATA / "logs" / "crash.log")
    sys.stdout = sys.stderr = sys.__stdout__ = sys.__stderr__ = out
    sys.stdin = sys.__stdin__ = _In(typed)
    typed.put(json.dumps(arguments))       # jobs.main reads its arguments first
    try:
        from botw_launcher import jobs
        jobs.main([name])
    finally:
        out.write("\n")
        lines.put(None)
