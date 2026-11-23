"""The launcher's long tasks, each run in a child process.

    python botw_launcher/__main__.py --job <name>

The window starts a job, writes its arguments as one JSON line on its input,
and reads its output (the window runs a job in a multiprocessing child,
botw_launcher/tk/child.py, with the same events). On that output:

  * a line starting with MARK is an event, a JSON object with an "event" key:
        progress  step, steps, label    a step of a build, a copy, a download
        stage     stage                 a step of a play session (core/output.py)
        count     what                  a check found or an item received
        waiting   count                 items waiting for a moment the game can take them
        message   kind, parts           a server message in parts (botw_client/protocol.py)
        hints     hints                 the slot's hints, each time they change
        done      result                the job's last line when it succeeded
        failed    error                 its last line otherwise
  * any other line is text for the log, as the tools print it.

A job is a plain function registered with @job; its keyword arguments are the
JSON object's keys, its result a JSON-able dict. It reports with print(), and
fails by raising: the message is shown to the player.

Why a process and not a thread: a play session owns its input, its error
stream and a server (tools/play_session.py); a build can be cancelled by ending
its process; and a crash there leaves the window standing, with the log.
"""
from __future__ import annotations

from dataclasses import asdict
import io
import json
from pathlib import Path
import sys
import threading
import traceback
from typing import Callable

from .core import output

MARK = "\x02"       # no tool prints it, and no reader takes it for the end of a line
JOBS: dict[str, Callable[..., dict | None]] = {}
_write_lock = threading.Lock()


def job(name: str):
    def register(function):
        JOBS[name] = function
        return function
    return register


def emit(event: str, **fields) -> None:
    with _write_lock:
        sys.__stdout__.write(MARK + json.dumps({"event": event, **fields}) + "\n")
        sys.__stdout__.flush()


def progress(step: int, steps: int, label: str) -> None:
    emit("progress", step=step, steps=steps, label=label)


class _Lines(io.TextIOBase):
    """The job's output, passed on line by line; the lines core/output.py
    knows also go out as events."""

    def __init__(self, stream):
        self.stream = stream
        self.pending = ""

    def write(self, text: str) -> int:
        self.pending += text
        *lines, self.pending = self.pending.split("\n")
        for line in lines:
            event = output.interpret(line)
            with _write_lock:
                self.stream.write(line + "\n")
                self.stream.flush()
            if event is not None:
                emit(**event)
        return len(text)

    def flush(self) -> None:
        self.stream.flush()

    def fileno(self) -> int:        # faulthandler writes a crash straight to the descriptor
        return self.stream.fileno()


# ---- the jobs ---------------------------------------------------------------

@job("create-profile")
def create_profile(executable: str) -> None:
    from .core import profile
    print("Copying Cemu, the update, the DLC and your saves...")
    profile.create(Path(executable))


@job("prepare-seed")
def prepare_seed(path: str, slot: str) -> dict:
    from .core import seeds
    return {"seed": seeds.prepare(seeds.inspect(Path(path)), slot)}


@job("rebuild-seed")
def rebuild_seed(seed: str) -> dict:
    from .core import seeds
    seeds.rebuild(seed)
    return {"seed": seed}


@job("play")
def play(seed: str, room: str | None = None, password: str | None = None,
         open_to_network: bool = False, session_arguments: list[str] = ()) -> dict:
    """A play session of a prepared seed, until Cemu closes: in the room at
    `room`, or hosted on this computer. `session_arguments` go to
    tools/play_session.py as they are (the test aids of a source checkout)."""
    from tools import build_poptracker, play_session
    from .core import seeds
    emit("stage", stage=output.PACK)
    seeds.refresh(seed)
    made = seeds.newer_world(seed)
    if made:
        print(f"This seed was generated with the Breath of the Wild world {made}, newer than this "
              "version: if something is missing, update BOTW Archipelago.")
    # A tracker pack the player built is kept up to date; none is built unasked.
    if (build_poptracker.PACK_FOLDER / f"{build_poptracker.PACK_NAME}.zip").is_file():
        build_poptracker.ensure_pack()
    arguments = ["--seed", seed, *session_arguments]
    if room:
        arguments += ["--connect", room] + (["--password", password] if password else [])
    elif open_to_network:
        arguments.append("--host")
    play_session.OBSERVER = lambda event: emit(**event)
    try:
        play_session.main(arguments)
    finally:
        play_session.OBSERVER = None
    from . import logs
    session = logs.last_session(seeds.folder_of(seed))
    return {"seed": seed, "session": str(session) if session else ""}


@job("poptracker")
def poptracker() -> dict:
    from tools import build_poptracker
    build_poptracker.ensure_pack()
    return {"folder": str(build_poptracker.PACK_FOLDER)}


@job("move-data")
def move_data(target: str) -> dict:
    from .core import storage
    return {"data": str(storage.relocate(Path(target), progress=progress))}


@job("install-update")
def install_update(release: dict) -> dict:
    from .core import updates
    archive = updates.download(updates.Release(**release), progress)
    installed = updates.install(archive, progress)
    print(f"Version {installed.version} is installed.")
    return {**asdict(installed), "folder": str(installed.folder)}


@job("install-apworld")
def install_apworld(release: dict) -> dict:
    from .core import updates
    target = updates.installed_apworld()
    if target is None:
        raise RuntimeError("This window was not opened from a botw.apworld: nothing to replace.")
    updates.install_apworld(updates.Release(**release), target, progress)
    print(f"Version {release['version']} is installed in {target}.")
    return {"version": release["version"], "apworld": str(target)}


# ---- the child process ------------------------------------------------------

def main(arguments: list[str]) -> int:
    name = arguments[0] if arguments else ""
    if name not in JOBS:
        print(f"unknown job: {name!r}; one of {', '.join(sorted(JOBS))}", file=sys.stderr)
        return 2
    sys.stdout, sys.stderr = _Lines(sys.__stdout__), _Lines(sys.__stderr__)
    try:
        result = JOBS[name](**json.loads(sys.stdin.readline() or "{}"))
    except SystemExit as exc:
        # The tools' command lines end this way: with a sentence, or a code.
        if exc.code in (None, 0):
            emit("done", result={})
            return 0
        emit("failed", error=exc.code if isinstance(exc.code, str) else f"{name} stopped (code {exc.code})")
        return 1
    except Exception as exc:  # noqa: BLE001 - whatever it is goes to the player and the log
        traceback.print_exc()
        emit("failed", error=str(exc) or type(exc).__name__)
        return 1
    emit("done", result=result or {})
    return 0
