"""Locate in RAM the DISPLAYED TEXT of a notification, to replace it.

The problem: 0x02FFA888(row, name) receives an ACTOR NAME ("Item_Fruit_A").
The game resolves it into the displayed text (the item's name in the game's
language). Only the name is ours, not the text.

USE
  1. Have the game show the item's notification and READ the text on screen.
  2. Search for it. EXACT matches are listed first:
         python tools/cemu/findtext.py "Apple"
  3. Test a candidate -- writes a marker, has it displayed, then restores:
         python tools/cemu/findtext.py --probe 0x21c4f244
  4. If the marker shows, look for what POINTS to it, to redirect to our
     buffer instead of overwriting (no length limit any more):
         python tools/cemu/findtext.py --refs 0x21c4f244
         python tools/cemu/findtext.py --repoint 0xSLOT --text "My text"

  --poke ADDR --text "..."   overwrites in place, without a net (destructive)

TWO TRAPS
  * A match is not necessarily the right word: a short name is also a PREFIX
    of longer ones (plurals, cooked variants). Only a string immediately
    followed by a terminator is the item's name. Hence the sort.
  * Searching in UTF-16LE finds the same bytes shifted by one. These ghosts
    are filtered out.
"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winmem import Process
from mailbox import Cave, cemu_pid, find_cave, guest_base

GUEST_SPAN = 1 << 32
CHUNK = 32 << 20


def scan(p, base, needles, align=1):
    """Guest addresses where one of the patterns appears."""
    hits = []
    longest = max(len(n) for n, _ in needles)
    for rbase, rsize in p.regions(min_size=1 << 12):
        if not (base <= rbase < base + GUEST_SPAN):
            continue
        off = 0
        while off < rsize:
            n = min(CHUNK, rsize - off)
            buf = p.read(rbase + off, n)
            if buf:
                for pat, tag in needles:
                    i = buf.find(pat)
                    while i != -1:
                        g = rbase + off + i - base
                        if g % align == 0:
                            hits.append((g, tag))
                        i = buf.find(pat, i + 1)
            if n < CHUNK:
                break
            off += n - longest
    return hits


def read_utf16(p, base, guest, maxunits=64):
    """The UTF-16BE string at this address, and the one after its terminator."""
    raw = p.read(base + guest, maxunits * 2)
    if not raw:
        return "", ""
    def decode(start):
        out = []
        i = start
        while i + 1 < len(raw):
            u = int.from_bytes(raw[i:i + 2], "big")
            if u == 0:
                break
            out.append(chr(u) if 32 <= u < 0xD800 else "�")
            i += 2
        return "".join(out), i + 2
    first, nxt = decode(0)
    second, _ = decode(nxt)
    return first, second


def marker_for(n):
    """A marker as long as the original: no overflow possible."""
    return ("ARCHIPELAGO" * (n // 11 + 1))[:n]


def do_search(p, base, target):
    hits = scan(p, base, [(target.encode("utf-16-be"), "be")])
    exact, prefix = [], []
    for guest, _ in hits:
        first, second = read_utf16(p, base, guest)
        (exact if first == target else prefix).append((guest, first, second))

    print(f"{len(exact)} EXACT match(es), "
          f"{len(prefix)} prefix(es) set aside\n")
    for guest, first, second in exact:
        print(f"  EXACT  {guest:#010x}  {first!r}")
        if second:
            print(f"                     followed by {second[:48]!r}")
    if not exact:
        print("  None. Is the text read on screen exact (accents, case)?")
        for guest, first, _ in prefix[:10]:
            print(f"  prefix {guest:#010x}  {first!r}")
        return exact
    print("")
    print("Test them one by one; the first that changes the screen is the one:")
    for guest, _, _ in exact:
        print(f"  python tools/cemu/findtext.py --probe {guest:#010x}")
    return exact


def do_probe(p, base, c, guest, actor, keep, hold):
    """Write a marker, have it displayed, say whether the game rewrote it.

    This test replaces an earlier, wrong classification: it compared before
    and after while showing ANOTHER item, but with --persist no row is
    recycled, so nothing could change. Here the difference is forced instead
    of waited for.
    """
    original, _ = read_utf16(p, base, guest)
    if not original:
        sys.exit(f"no readable string at {guest:#010x}")
    raw_orig = original.encode("utf-16-be")
    mark = marker_for(len(original))

    print(f"original = {original!r}")
    print(f"marker   = {mark!r}   (same length: nothing overflows)")
    if not p.write(base + guest, mark.encode("utf-16-be")):
        sys.exit("write refused")

    print("")
    print(f"showing {actor} -- LOOK AT THE SCREEN NOW")
    ok = c.notify(actor, duration=hold)
    if not ok:
        # Without a trigger, there was no test: say it, and stop there.
        # Asking "did the marker show?" after a failed trigger asks for a
        # conclusion on a measurement that did not happen -- and a "no" would
        # read as "wrong address".
        print("")
        print("THE TRIGGER FAILED: no notification was shown, so this test")
        print("measured nothing. Conclude nothing from the screen.")
        print("")
        print("Most frequent cause: the session prerequisite. The cave")
        print("captures PauseMenuDataMgr and the notification screen on the")
        print("fly, so an item must have been picked up once since the start.")
        print("")
        print("For the get window, this test does not fit anyway: it forces")
        print("a BANNER, not the large window. Use --refs on the heap copies")
        print("instead.")
        p.write(base + guest, raw_orig)
        print("")
        print("original restored.")
        return
    time.sleep(1.0)

    now, _ = read_utf16(p, base, guest)
    print("")
    if now == mark:
        print("The game did NOT rewrite this area: it is a static table.")
        print("If the marker showed, this address drives the text.")
    else:
        print(f"The game rewrote the area ({now!r}): a live copy, redone at")
        print("every display. It would have to be written AFTER the three calls.")

    if keep:
        print("")
        print("--keep: the marker is left in place.")
    else:
        time.sleep(hold if hold and hold < 10 else 4.0)
        p.write(base + guest, raw_orig)
        print("")
        print("original restored.")
    print("")
    print("Did the marker show on screen?")


def do_refs(p, base, target):
    """What points to this address?

    Redirecting a pointer is better than overwriting the table: no length
    limit, and the original text stays intact. Only 4-aligned slots are kept --
    a PowerPC pointer always is.
    """
    hits = scan(p, base, [(target.to_bytes(4, "big"), "ptr")], align=4)
    print(f"{len(hits)} aligned slot(s) holding {target:#010x}\n")
    for guest, _ in hits[:40]:
        print(f"  {guest:#010x}")
    if len(hits) > 40:
        print(f"  ... and {len(hits) - 40} more")
    if hits:
        print("")
        print("Redirect one of them to our buffer:")
        print(f"  python tools/cemu/findtext.py --repoint {hits[0][0]:#010x} "
              f"--text \"My text\"")
    else:
        print("No absolute pointer. The table is probably addressed by an")
        print("index or an offset: it must be overwritten in place, and so")
        print("stay within the original length.")
    return hits


def do_repoint(p, base, c, slot, text):
    addr = c.write_text(text)
    ok = p.write(base + slot, addr.to_bytes(4, "big"))
    print(f"text stored in apText = {addr:#010x} ({len(text)} characters)")
    print(f"pointer {slot:#010x} redirected: {'OK' if ok else 'REFUSED'}")
    if ok:
        print("")
        print("Show a notification again to see the result.")
    return ok


def do_poke(p, base, guest, text):
    original, _ = read_utf16(p, base, guest)
    data = text.encode("utf-16-be") + b"\x00\x00"
    if len(text) > len(original):
        print(f"WARNING: {len(text)} characters for {len(original)} "
              f"originally -- the next string will be overwritten.")
    ok = p.write(base + guest, data)
    print(f"writing {len(data)} bytes at {guest:#010x}: "
          f"{'OK' if ok else 'REFUSED'}")
    return ok


def do_writehex(p, base, guest, hexstr):
    """Rewrite raw bytes: enough to undo a failed --poke.

    No terminator is added, unlike --poke: exactly what was there is put back,
    inner terminators included.
    """
    data = bytes.fromhex(hexstr.replace(" ", ""))
    ok = p.write(base + guest, data)
    print(f"{len(data)} raw bytes at {guest:#010x}: "
          f"{'OK' if ok else 'REFUSED'}")
    if ok:
        first, second = read_utf16(p, base, guest)
        print(f"read back: {first!r} then {second[:32]!r}")
    return ok


def main():
    argv = sys.argv[1:]
    if not argv:
        sys.exit(__doc__)

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    text = opt("--text")
    actor = opt("--actor", "Item_Fruit_A")
    hold = float(opt("--hold", "8"))
    keep = "--keep" in argv
    positional = [a for i, a in enumerate(argv)
                  if not a.startswith("--")
                  and (i == 0 or not argv[i - 1].startswith("--"))]

    pid = cemu_pid()
    if not pid:
        sys.exit("Cemu is not running")

    with Process(pid, writable=True) as p:
        a = find_cave(p)
        if a is None:
            sys.exit("cave not found - is the graphic pack enabled?")
        base, _, _ = guest_base(p, a - 12)
        if base is None:
            sys.exit("guest/host base not found")
        c = Cave(p, a, base)

        if opt("--probe"):
            do_probe(p, base, c, int(opt("--probe"), 0), actor, keep, hold)
        elif opt("--refs"):
            do_refs(p, base, int(opt("--refs"), 0))
        elif opt("--repoint"):
            if not text:
                sys.exit("--repoint needs --text \"...\"")
            do_repoint(p, base, c, int(opt("--repoint"), 0), text)
        elif opt("--writehex"):
            if not opt("--hex"):
                sys.exit("--writehex needs --hex \"0050006f...\"")
            do_writehex(p, base, int(opt("--writehex"), 0), opt("--hex"))
        elif opt("--poke"):
            if not text:
                sys.exit("--poke needs --text \"...\"")
            do_poke(p, base, int(opt("--poke"), 0), text)
        elif positional:
            do_search(p, base, positional[0])
        else:
            sys.exit(__doc__)


if __name__ == "__main__":
    main()
