"""One user of the cave's invoker at a time, inside this client.

The cave has one request slot, and tools/cemu/owned_presentation.publisher_lock
(an OS mutex, taken without waiting) keeps two publishers of different Python
processes apart: a busy mutex is an error there. Inside the client, the loop
(deliveries, journal, DeathLink) and the Cucco Swarm, which plays for 10 s on
a thread of its own, share that slot: they take their turn here first, waiting
for each other, so that the mutex is never found busy by the client itself.
The turn is reentrant (an attacker of the swarm holds it across its calls) and,
held by this process, the OS mutex is too.
"""
from __future__ import annotations

from contextlib import contextmanager
import threading

_TURN = threading.RLock()
WAIT = 10.0         # longer than one attacker of the swarm, even with a paused game


@contextmanager
def client_turn(*, wait: float = WAIT):
    """The client's turn alone, for a publisher that takes the mutex itself."""
    if not _TURN.acquire(timeout=wait):
        raise RuntimeError("The cave's invoker stayed busy inside the client")
    try:
        yield
    finally:
        _TURN.release()


@contextmanager
def publisher_turn(pid, *, os_lock=None, wait: float = WAIT):
    """The client's turn, then the emulator's publisher mutex."""
    if os_lock is None:
        from tools.cemu.owned_presentation import publisher_lock as os_lock
    with client_turn(wait=wait), os_lock(pid):
        yield
