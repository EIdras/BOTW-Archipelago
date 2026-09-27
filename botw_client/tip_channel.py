"""Client side of the AP tip channel (native side: tools/build_tip_channel.py).

AP text is laid out as the game lays out its own tips (3 lines of 34
characters, explicit line breaks, colour codes), one tip at a time: a page is
written into the native buffer while the channel is idle, then the native
submit runs on the game thread through the per-frame invoker, under the
publisher lock every native channel shares. The native side reports the
outcome of each generation (closed, dropped, refused).
"""
from __future__ import annotations

import struct
import textwrap
import time

from . import tip_protocol as tp

COLOR = "\u000e\u0000\u0003\u0002"      # game control code: colour N follows
RESET = COLOR + "￿"
CODE_BASE = 0x01800000                  # the injection group's code cave
SCAN = 0x00100000


def _visible(markup: str) -> list[tuple[str, int | None]]:
    """(character, colour) pairs of `{N}...{/}` markup; other braces are text."""
    out, colour, i = [], None, 0
    while i < len(markup):
        if markup[i] == "{":
            end = markup.find("}", i)
            body = markup[i + 1:end] if end != -1 else ""
            if body == "/":
                colour, i = None, end + 1
                continue
            if body.isdigit() and int(body) < 0xFFFF:
                colour, i = int(body), end + 1
                continue
        out.append((markup[i], colour))
        i += 1
    return out


def _encode(chars: list[tuple[str, int | None]]) -> str:
    out, current = [], None
    for char, colour in chars:
        if colour != current and char != "\n":
            out.append(RESET if colour is None else COLOR + chr(colour))
            current = colour
        out.append(char)
    if current is not None:
        out.append(RESET)
    return "".join(out)


def pages(markup: str, width: int = tp.LINE_WIDTH, lines: int = tp.LINES) -> list[str]:
    """Tips of at most `lines` lines of `width` visible characters, colour codes
    encoded, each within the native buffer; a long message gives several."""
    chars = [(c, k) for c, k in _visible(" ".join(markup.split()))]
    plain = "".join(c for c, _ in chars)
    wrapped = textwrap.wrap(plain, width, break_long_words=True, break_on_hyphens=False)
    # Map the wrapped lines back onto the coloured characters, in order.
    rows, cursor = [], 0
    for line in wrapped:
        start = plain.index(line, cursor)
        rows.append(chars[start:start + len(line)])
        cursor = start + len(line)
    out = []
    for first in range(0, len(rows), lines):
        page = []
        for row in rows[first:first + lines]:
            if page:
                page.append(("\n", None))
            page.extend(row)
        text = _encode(page)
        if len(text.encode("utf-16-be")) // 2 > tp.TEXT_UNITS:
            raise ValueError("page trop longue pour le tampon natif")
        out.append(text)
    return out


class TipChannel:
    """The native tip channel of a connected game (BotwGame)."""

    def __init__(self, game, *, clock=time.monotonic, lock_factory=None):
        self.game, self.clock = game, clock
        if lock_factory is None:
            from tools.cemu.owned_presentation import publisher_lock
            lock_factory = publisher_lock
        self.lock_factory = lock_factory
        self.process, self.cave = game.process, game.cave
        self.data = self.locate()
        self.flag_object = game.live.index["bool"].get(tp.TIP_KEY_HASH)
        if not self.flag_object:
            raise RuntimeError(f"drapeau {tp.TIP_KEY} introuvable dans les GameData vivantes")
        self.active = None                  # generation of our tip on screen, if any
        self._flags = None

    def in_world(self) -> bool:
        """Link playable in the world: HUD up, no loading screen, dialogue or
        menu (the guard of the item presentations and the dialogue bridge).
        A tip requested at the title screen or while loading is "shown" where
        nobody sees it (25/09: the connection notice was lost that way)."""
        from tools.cemu.presentation_ready import flag_reader, ready
        if self._flags is None:
            self._flags = flag_reader(self.process, self.cave)
        return ready(self.process, self.cave, self._flags, allow_hudless=True)

    # --- memory ---------------------------------------------------------------

    def _host(self, guest: int) -> int:
        return self.cave.base + guest

    def _word(self, guest: int) -> int:
        raw = self.process.read(self._host(guest), 4)
        if raw is None or len(raw) != 4:
            raise RuntimeError("lecture du canal des conseils impossible")
        return int.from_bytes(raw, "big")

    def _write(self, guest: int, data: bytes) -> None:
        if not self.process.write(self._host(guest), data):
            raise RuntimeError("écriture du canal des conseils impossible")

    def locate(self) -> int:
        """apTipData, found by its signature in the injection group's cave."""
        raw = self.process.read(self._host(CODE_BASE), SCAN)
        if not raw:
            raise RuntimeError("code cave illisible")
        head = struct.pack(">II", tp.MAGIC, tp.VERSION)
        found = []
        at = raw.find(head)
        while at != -1:
            words = struct.unpack_from(f">{tp.DATA_WORDS}I", raw, at)
            field = {name: words[offset // 4] for name, offset in tp.OFFSETS.items()}
            data = CODE_BASE + at
            if (field["index"] == tp.TIP_INDEX and field["flag_hash"] == tp.TIP_KEY_HASH
                    and field["text"] == data + 4 * tp.DATA_WORDS
                    and CODE_BASE <= field["submit"] < CODE_BASE + SCAN):
                found.append(data)
            at = raw.find(head, at + 4)
        if len(found) != 1:
            raise RuntimeError("canal des conseils absent du pack chargé (ou ambigu)")
        return found[0]

    def field(self, name: str) -> int:
        return self._word(self.data + tp.OFFSETS[name])

    # --- protocol -------------------------------------------------------------

    def idle(self) -> bool:
        return (self.field("phase") == tp.IDLE and not self.field("fault")
                and self.field("completed") == self.field("generation"))

    def submit(self, page: str, timeout: float = 3.0) -> str:
        """'accepted', 'busy', 'refused' (by the game) or 'invalid'."""
        encoded = page.encode("utf-16-be")
        units = len(encoded) // 2
        if not 0 < units <= tp.TEXT_UNITS:
            raise ValueError("page vide ou trop longue")
        c = self.cave
        with self.lock_factory(self.process.pid):
            if not self.idle() or not c.pf_ready():
                return "busy"
            if self._word_host(c.pf_req) or self._word_host(c.opn_req):
                return "busy"
            generation = self.field("generation")
            # Inputs are written only while idle: the native side reads them
            # only after the submit below.
            self._write(self.field("text"), encoded + b"\0\0")
            self._write(self.data + tp.OFFSETS["units"], struct.pack(">I", units))
            self._write(self.data + tp.OFFSETS["flag_object"],
                        struct.pack(">I", self.flag_object))
            before = self._word_host(c.call_n)
            c.call_pf(self.field("submit"))
            deadline = self.clock() + timeout
            while self.clock() < deadline:
                if self._word_host(c.call_n) != before:
                    result = self._word_host(c.call_ret)
                    if result == tp.ACCEPTED:
                        if self.field("generation") != generation + 1:
                            raise RuntimeError("génération du conseil incohérente")
                        self.active = generation + 1
                        return "accepted"
                    return {tp.BUSY: "busy", tp.REFUSED_BY_GAME: "refused"}.get(
                        result, "invalid")
                time.sleep(0.02)
        raise RuntimeError("soumission du conseil sans réponse")

    def _word_host(self, host: int) -> int:
        raw = self.process.read(host, 4)
        if raw is None or len(raw) != 4:
            raise RuntimeError("lecture de l'invocateur impossible")
        return int.from_bytes(raw, "big")

    def poll(self) -> str | None:
        """None while our tip is active; else how it ended."""
        if self.active is None:
            return "idle"
        if self.field("completed") != self.active:
            return None
        self.active = None
        return {tp.CLOSED: "closed", tp.DROPPED: "dropped",
                tp.REFUSED: "refused"}.get(self.field("outcome"), "unknown")
