"""Show OUR text in the game's center message.

    python tools/cemu/saycenter.py "Alice sends you a Sword"
    python tools/cemu/saycenter.py "..." --index 5
    python tools/cemu/saycenter.py --locate      # locate without showing

THE MECHANISM, ESTABLISHED BY MEASUREMENT

    0x02ed1f7c(this, index, SafeString*)   pushes the request -> this+0x154 = 1
    0x02ed1e1c(this, flag)                 pops and shows     -> this+0x154 = 0

Both are requested in the SAME frame: `apCheckPlay` then `apCheckMsg` are two
consecutive blocks of the per-frame hook. Each alone does nothing -- the push
leaves the counter at 1, and the pop leaves through `ble` on an empty list. Both
were needed.

The text follows the same path as the item notification: the game resolves the
message from a static table at display time, so ours is written there, the
message is triggered, and the table is restored at once.

PREREQUISITE: NONE ANY MORE, except that the game's UI exists

A real center message used to be needed since the start, for the probe to see
the `this` go by. It is now RESOLVED every frame: it is `*(screen 0x25 +
0x1b84)`, read at 0x02fbcaf8 -- a method of screen 0x25 that does `lwz r3,
0x1b84(r3)` before jumping into the push 0x02ed1f7c. The object obtained does
hold the list at +0x14c and its count at +0x154, the two fields the display
function tests.
"""
import json
import pathlib
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winmem import Process
from mailbox import Cave, be, cemu_pid, diagnose, find_cave, guest_base
from findtext import read_utf16, scan
from say import colorize, has_markup

CACHE = pathlib.Path(tempfile.gettempdir()) / "botw_ap_center.json"
# Text of the message of index 5, in the French game. It anchors the search for
# the entry in the static table; --msg aims at another one.
DEFAULT_INDEX = 5
# The FULL STOP is part of the message. Without it `locate()` found nothing: it
# compares the WHOLE string, not a prefix, and so refused all its own finds --
# a failure that read "entry not found".
DEFAULT_MSG = "Le compartiment des vêtements est plein."
WINDOW = 256


def trigger(p, c, idx, timeout=5.0):
    """Push then pop, in the same frame."""
    before = be(p.read(c.play_done, 4))
    p.write(c.play_a, (idx & 0xFFFFFFFF).to_bytes(4, "big"))
    p.write(c.play_raw, bytes(4))
    p.write(c.play_req, (1).to_bytes(4, "big"))
    p.write(c.ms_index, (idx & 0xFFFFFFFF).to_bytes(4, "big"))
    p.write(c.ms_flag, (1).to_bytes(4, "big"))
    p.write(c.ms_queue, bytes(4))
    p.write(c.ms_state, bytes(4))
    p.write(c.ms_req, (1).to_bytes(4, "big"))
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(0.05)
        raw = p.read(c.play_done, 4)
        if not raw:
            raise RuntimeError("Cemu no longer answers (the game crashed).")
        if be(raw) != before:
            return be(p.read(c.ms_ret, 4))
    return None


def locate(p, base, c, msg, idx, cave, verbose=True):
    """Address of the message's entry in the static table.

    Several copies exist: the table read at display time, and the arena where
    the resolved text is copied. A distinct marker per candidate, then a real
    display, tells them apart -- the table keeps its own, the arena receives
    the table's. The same method as for the item notification.
    """
    key = f"{p.pid}:{msg}"
    data = {}
    if CACHE.exists():
        try:
            data = json.loads(CACHE.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
    if key in data:
        first, _ = read_utf16(p, base, data[key])
        if first == msg:
            return data[key]

    if verbose:
        print(f"locating {msg[:34]!r} ... (~6 s)")
    cands = []
    for g, _ in scan(p, base, [(msg.encode("utf-16-be"), "be")]):
        if cave and cave[0] <= g < cave[1]:
            continue
        first, _ = read_utf16(p, base, g)
        if first == msg:
            cands.append(g)
    if not cands:
        return None
    if len(cands) == 1:
        static = cands[0]
    else:
        marks = [("ARCHIPELAGO" * (len(msg) // 11 + 2))[:len(msg) - 1] + str(i)
                 for i in range(len(cands))]
        for g, m in zip(cands, marks):
            p.write(base + g, m.encode("utf-16-be"))
        trigger(p, c, idx)
        time.sleep(0.4)
        keep = [g for g, m in zip(cands, marks)
                if read_utf16(p, base, g)[0] == m]
        for g in cands:
            p.write(base + g, msg.encode("utf-16-be"))
        if not keep:
            return None
        static = keep[0]

    data[key] = static
    CACHE.write_text(json.dumps(data), encoding="utf-8")
    if verbose:
        print(f"  entry = {static:#010x}  ({len(msg)} characters of room)")
    return static


def main():
    argv = sys.argv[1:]

    def opt(n, d=None):
        if n not in argv:
            return d
        i = argv.index(n) + 1
        return argv[i] if i < len(argv) and not argv[i].startswith("--") else d

    msg = opt("--msg", DEFAULT_MSG)
    idx = int(opt("--index", str(DEFAULT_INDEX)))
    positional = [a for i, a in enumerate(argv)
                  if not a.startswith("--")
                  and (i == 0 or not argv[i - 1].startswith("--"))]

    pid = cemu_pid()
    if not pid:
        sys.exit("Cemu is not running")

    with Process(pid, writable=True) as p:
        a = find_cave(p)
        if a is None:
            print("cave not found.")
            print("")
            diagnose()
            return
        base, cave_g, _ = guest_base(p, a - 12)
        c = Cave(p, a, base)
        cave = (cave_g, cave_g + 2048)

        ok, rn, tick = c.resolve_ready()
        if not ok:
            sys.exit(f"the loaded patch's resolver does not run "
                     f"(apResolveN={rn}, tick={tick}).\n"
                     "CLOSE AND REOPEN CEMU: reloading a save is not "
                     "enough.")
        if not be(p.read(c.push_this, 4)):
            sys.exit("the message object is not resolved "
                     "(*(screen 0x25 + 0x1b84) is 0).\n"
                     "Load a save, then run again.")

        static = locate(p, base, c, msg, idx, cave)
        if static is None:
            print(f"entry {msg[:34]!r} not found.")
            print("  The text must be EXACTLY the one shown on screen.")
            print("  Show the message once, note it, and pass it to --msg.")
            return

        if "--locate" in argv or not positional:
            print("")
            print(f"Room available: {len(msg)} characters.")
            print('Give a text as an argument to show it.')
            return

        # The {N} ... {/} markup becomes the game's control codes.
        # The string AFTER markup counts for the room.
        text = colorize(positional[0])
        if len(text) > len(msg):
            sys.exit(f"{len(text)} characters for a slot of "
                     f"{len(msg)}. Beyond it, the text overflows onto neighbouring "
                     f"messages -- which crashed the game with the item "
                     f"notification.")

        print(f"showing: {positional[0]!r} "
              f"({len(text)} code units" +
              (", color markup included)" if has_markup(positional[0])
               else ")"))
        saved = p.read(base + static, max(WINDOW, len(text) * 2 + 32))
        p.write(base + static, text.encode("utf-16-be") + b"\x00\x00")
        try:
            ret = trigger(p, c, idx)
        finally:
            if saved:
                p.write(base + static, saved)
        if ret:
            print("triggered -- look at the screen.")
        else:
            print(f"the game refused (return {ret}).")


if __name__ == "__main__":
    main()
