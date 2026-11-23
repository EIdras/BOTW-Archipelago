"""Signals and the window's thread. Tk widgets are only touched from the thread
of the main loop: anything that comes from another thread (a background read,
a log record, a job's output) is queued here and delivered by the loop."""
from __future__ import annotations

import logging
import queue
import threading
from typing import Callable

logger = logging.getLogger(__name__)
_calls: "queue.SimpleQueue[Callable[[], None]]" = queue.SimpleQueue()
PUMP_MS = 50


class Signal:
    """A list of callbacks, called in order with the values emitted."""

    def __init__(self) -> None:
        self._slots: list[Callable] = []

    def connect(self, slot: Callable) -> None:
        self._slots.append(slot)

    def emit(self, *values) -> None:
        for slot in list(self._slots):
            slot(*values)


def later(call: Callable[[], None]) -> None:
    """Run `call` in the window's thread, from any thread."""
    _calls.put(call)


def pump(root) -> None:
    """Deliver the queued calls; then again PUMP_MS later."""
    while True:
        try:
            call = _calls.get_nowait()
        except queue.Empty:
            break
        try:
            call()
        except Exception:  # noqa: BLE001 - one failing callback must not stop the window
            logger.exception("callback failed")
    root.after(PUMP_MS, pump, root)


def background(work: Callable, done: Callable | None = None, failed: Callable | None = None) -> None:
    """Run `work()` in a thread; then `done(result)` or `failed(error)` in the
    window's thread. For the short reads a page should not wait for."""
    def run() -> None:
        try:
            result = work()
        except Exception as exc:  # noqa: BLE001
            logger.warning("background task failed: %s", exc)
            if failed is not None:
                later(lambda error=exc: failed(error))     # `exc` is unbound once the except ends
            return
        if done is not None:
            later(lambda: done(result))
    threading.Thread(target=run, daemon=True).start()
