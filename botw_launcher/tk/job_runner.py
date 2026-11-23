"""The job that runs, in a child process started by multiprocessing
(tk/child.py), one at a time."""
from __future__ import annotations

import json
import logging
import multiprocessing
import threading
from typing import Callable

from ..jobs import MARK
from .events import Signal, later

logger = logging.getLogger(__name__)
Done = Callable[[bool, object], None]


class JobRunner:
    def __init__(self, entry: Callable):
        """`entry(name, arguments, lines, typed)`: the child's function, which
        a fresh process can import (tk/child.py run, or the apworld's own,
        which first puts the project on the path)."""
        self.entry = entry
        self.started = Signal()     # name, title
        self.line = Signal()        # a line of the job's output
        self.event = Signal()       # an event of the job (jobs.py), done and failed apart
        self.finished = Signal()    # name, succeeded, result or error
        self.name = ""
        self._process: multiprocessing.Process | None = None
        self._typed = None
        self._outcome: tuple[bool, object] | None = None
        self._on_done: Done | None = None
        self._cancelled = False

    @property
    def busy(self) -> bool:
        return self._process is not None

    def start(self, name: str, arguments: dict, title: str, on_done: Done | None = None) -> None:
        if self.busy:
            raise RuntimeError(f"a job is running: {self.name}")
        self.name, self._on_done, self._outcome, self._cancelled = name, on_done, None, False
        lines, self._typed = multiprocessing.Queue(), multiprocessing.Queue()
        logger.info("job %s started", name)
        self._process = multiprocessing.Process(target=self.entry, args=(name, arguments, lines, self._typed),
                                                name=f"BOTW {name}", daemon=False)
        self._process.start()
        self.started.emit(name, title)
        threading.Thread(target=self._read, args=(self._process, lines), daemon=True).start()

    def send(self, text: str) -> None:
        """A line for the job's input: what the player types to a play session."""
        if self._typed is not None:
            self._typed.put(text)

    def cancel(self) -> None:
        if self._process is not None:
            self._cancelled = True
            self._process.kill()

    def _read(self, process: multiprocessing.Process, lines) -> None:
        while True:
            try:
                text = lines.get(timeout=0.5)
            except Exception:  # noqa: BLE001 - queue.Empty, or the queue gone with a killed child
                if not process.is_alive():
                    break
                continue
            if text is None:
                break
            later(lambda text=text: self._take(text))
        process.join()
        later(lambda: self._ended(process.exitcode))

    def _take(self, text: str) -> None:
        if not text.startswith(MARK):
            logger.debug("%s: %s", self.name, text)
            self.line.emit(text)
            return
        try:
            event = json.loads(text[len(MARK):])
        except ValueError:
            logger.warning("%s: unreadable event %r", self.name, text)
            return
        if event.get("event") == "done":
            self._outcome = (True, event.get("result") or {})
        elif event.get("event") == "failed":
            self._outcome = (False, str(event.get("error", "")))
        else:
            self.event.emit(event)

    def _ended(self, code: int | None) -> None:
        if self._process is None:
            return
        self._process = self._typed = None
        if self._cancelled:
            succeeded, payload = False, "Cancelled."
        elif self._outcome is not None:
            succeeded, payload = self._outcome
        else:
            succeeded, payload = False, f"The task stopped unexpectedly (exit code {code}). See the Logs page."
        logger.log(logging.INFO if succeeded or self._cancelled else logging.ERROR,
                   "job %s %s", self.name, "finished" if succeeded else f"failed: {payload}")
        name, on_done, self._on_done = self.name, self._on_done, None
        if on_done is not None:
            on_done(succeeded, payload)
        self.finished.emit(name, succeeded, payload)
