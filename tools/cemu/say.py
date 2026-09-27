"""Show ANY TEXT in the game's item notification.

    python tools/cemu/say.py "Alice found the Paraglider" --duration 8
    python tools/cemu/say.py "a long text ..." --duration 8   # stacked
    python tools/cemu/say.py "..." --nowrap       # one line, not split
    python tools/cemu/say.py --inspect            # state of the session
    python tools/cemu/say.py --cleanup            # repair pointer and pool

WHAT REALLY HAPPENS

The patch can only pass an ACTOR NAME; the game resolves it into text through
its tables. Probes in the game gave the whole chain:

    static table 0x21c4f244  --WRITTEN on display-->  pool 0x436690c0
                                                            ^
                                                      the widget, which reads
                                                      the pool again every frame

Route kept: write into the static table, display, restore the table. It is
the only one that ever showed our text.

Route SET ASIDE (--pointer, kept for reference): redirecting the pool pointer
to apText. Checked in the game, it only shows the original name -- the game
WRITES the resolved message through that pointer, so our text is overwritten
before it is drawn.

LENGTH: 40 CHARACTERS, AND THAT IS THE GAME'S LIMIT

40 characters pass, 44 crash. It is NOT an artefact of the method: the longest
item names of the game are ~45 characters, and the UI crashes beyond them --
in the inventory too, outside any notification.

Two workarounds were tried and set aside, both checked in the game:

  * growing the message's slot at run time (--reserve): measurement not
    reproducible, crashes;
  * lengthening the name in the FILE (a message mod, 120 characters): a
    correct build -- MSBT and SARC pass the byte-for-byte identity test --
    but the game crashes wherever the name is drawn.

Answer kept: SPLIT into several stacked notifications. Stacking works, each
line fits in the limit, and nothing overflows. It is automatic; --nowrap
turns it off.

COLORS

The game colors its text with a control code found in its message archive
(14,824 occurrences, group 0 / type 3 / 2 bytes):

    000E 0000 0003 0002 000N   switch to color N
    000E 0000 0003 0002 FFFF   back to the default

The markup {N} ... {/} is translated into those codes.

    say.py "Alice sends you a {2}Sword{/}" --duration 8
    say.py "item received" --color 2
    say.py --palette              # one hue per line, to identify them

Each colored segment costs 10 code units of the line's budget, tags included.
The ceiling applies to the string AFTER markup.

A line with markup is not split: an opening separated from its closing would
tint everything after it.

The entry's address is in the HEAP: it changes at every Cemu start. It is
located on the fly, then cached (key = PID + name). `--relocate` forces a new
search.

CARRIER

By default Item_Roast_16, whose name is the longest PLAIN TEXT name of the
game (27 characters in the French game). Its slot is 56 bytes instead of the
12 of a short name, which divides the overflow onto neighbouring messages by
nearly three. It is also a rare dish, seldom seen in the inventory.

27 characters are clean, with no overflow. Up to 40 overflow but display. For
another language, pass --name with the exact text shown.
"""
import json
import pathlib
import struct
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winmem import Process
from mailbox import Cave, cemu_pid, find_cave, guest_base
from findtext import read_utf16, scan

CACHE = pathlib.Path(tempfile.gettempdir()) / "botw_ap_msgtext.json"
WINDOW = 256            # bytes saved around the entry (overwrite route)
POOL_SAVE = 512         # clean copy of the pool, for --cleanup
# Carrier: the longest PLAIN TEXT name of the game (27 characters). Its slot in
# the arena is therefore 56 bytes instead of the 12 of a short name, which
# divides by nearly three what a long text overflows onto its neighbours. It
# is also a rare cooked item, seldom seen in the inventory.
DEFAULT_ACTOR = "Item_Roast_16"
DEFAULT_NAME = "Fruit de lotus tempo grillé"   # its name in the French game
CLEAN_CHARS = len(DEFAULT_NAME)   # beyond, it overflows (no crash up to 40)
MAX_CHARS = 127         # hard ceiling, whatever the reservation
# Measured, not estimated: 27, 35 and 40 characters pass; 44 crashes.
# Beyond CLEAN_CHARS it overflows onto neighbouring messages without crashing:
# --repair puts the clean copy back once the notification has expired.
SAFE_CHARS = 40


def exact_matches(p, base, name, exclude=None):
    """Addresses where the string is EXACTLY `name`, terminator included.

    The exactness filter is essential: a short name is also a prefix of longer
    names (plurals, cooked variants...). On a real measurement, 9 of the 11
    occurrences were prefixes.

    `exclude` removes OUR OWN code cave. Without it, as soon as the game has
    written into apText, the scan finds the name there and takes our buffer for
    the game's pool: the pointer is then "redirected" to itself and nothing can
    be restored any more.
    """
    out = []
    for guest, _ in scan(p, base, [(name.encode("utf-16-be"), "be")]):
        if exclude and exclude[0] <= guest < exclude[1]:
            continue
        first, _ = read_utf16(p, base, guest)
        if first == name:
            out.append(guest)
    return out


def markers(n, length):
    """n DISTINCT markers of a given length.

    Distinct, not one common marker: a live copy is rewritten from the table.
    With the same marker everywhere it would receive the table's and look
    static. Uniqueness is what makes the sort reliable.
    """
    out = []
    for i in range(n):
        m = ("ARCHIPELAGO" * (length // 11 + 1))[:length]
        tag = str(i)
        out.append((m[:-len(tag)] + tag) if length > len(tag) else tag[:length])
    return out


def classify(p, base, c, cands, name, actor, verbose=False):
    """Sort statics / live copies with ONE notification.

    The duration is saved and restored: notify() writes apDuration, and the
    game's probe only rewrites it at the next real pickup. Without this
    restore, the sorting duration (0.5 s) stayed for every later display.
    """
    marks = markers(len(cands), len(name))
    for g, m in zip(cands, marks):
        p.write(base + g, m.encode("utf-16-be"))

    saved_dur = c.get_duration()
    c.notify(actor, duration=0.5)
    time.sleep(0.3)

    static, live = [], []
    for g, m in zip(cands, marks):
        now, _ = read_utf16(p, base, g)
        (static if now == m else live).append(g)
        if verbose:
            print(f"  {g:#010x}  wrote {m!r} -> read back {now!r}  "
                  f"{'STATIC' if now == m else 'live copy'}")

    for g in cands:
        p.write(base + g, name.encode("utf-16-be"))
    if saved_dur and saved_dur > 0:
        p.write(c.duration, struct.pack(">f", saved_dur))
    return static, live


def _cache_load():
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text())
        except ValueError:
            pass
    return {}


def prime(p, c, actor, verbose=True):
    """Have the message resolved ONCE before searching.

    The destination pool is filled LAZILY: until the message has been asked
    for, its entry does not exist. Searching before priming therefore only
    finds the static table, with no live copy nor pointer -- exactly what gave
    "pool not located" right after a restart.
    """
    if verbose:
        print("  priming: a short display to fill the pool ...")
    saved = c.get_duration()
    ok = c.notify(actor, duration=0.5)
    time.sleep(0.4)
    if saved and saved > 0:
        c.p.write(c.duration, struct.pack(">f", saved))
    return ok


def check_pointer(p, base, ent, verbose=True):
    """Does the pointer still show the game's pool?

    The game WRITES through this pointer, it does not only read it: while it
    targets apText, every resolved message lands in our buffer -- so much that
    a real apple pickup shows our text. It is repaired as soon as it is seen.
    """
    if not ent.get("slot") or not ent.get("live"):
        return None
    cur = int.from_bytes(p.read(base + ent["slot"], 4) or b"\0" * 4, "big")
    if cur == ent["live"]:
        return True
    if verbose:
        print(f"  stray pointer: {ent['slot']:#010x} -> {cur:#010x} "
              f"instead of {ent['live']:#010x}")
        print("  put back.")
    p.write(base + ent["slot"], ent["live"].to_bytes(4, "big"))
    return False


def reserve_session(p, base, c, name, actor, nchars, cave=None, verbose=True):
    """Have the message's slot in the pool born LARGE.

    The pool is a compact arena: a message's slot is allocated the FIRST time
    it is resolved, at the size it has then. A 5-character name gives a tiny
    slot -- and any longer text overflows onto its neighbours (44 characters
    are enough to crash the game).

    Resolving first with a long text makes the slot born at that size, and the
    following displays fit in it WITHOUT OVERFLOW. No neighbour is overwritten
    any more, and there is nothing to repair.

    Only on a FRESH session: once the message has been resolved, its slot is
    already allocated, small, and nothing resizes it.
    """
    cands = exact_matches(p, base, name, exclude=cave)
    if len(cands) != 1:
        if verbose:
            print(f"{len(cands)} occurrences of {name!r} instead of one.")
            print("The message was already resolved in this session: its")
            print("slot is already allocated. Restart Cemu and try again")
            print("WITHOUT showing a notification first.")
        return None
    static = cands[0]

    filler = "".join(chr(0x41 + i % 26) for i in range(nchars))
    if verbose:
        print(f"reserving {nchars} characters ...")
    saved = p.read(base + static, WINDOW)
    p.write(base + static, filler.encode("utf-16-be") + b"\x00\x00")
    ok = c.notify(actor, duration=0.5)
    time.sleep(0.4)
    if saved:
        p.write(base + static, saved)
    if not ok:
        if verbose:
            print("  the display did not answer: pick up an item in the game")
        return None

    # Look for a PREFIX, not the whole string: if the game truncates the copy,
    # searching for the 120 characters finds nothing and wrongly concludes to
    # a failure. The prefix locates the slot, then what REALLY arrived there is
    # read -- the real capacity, measured and not assumed.
    probe = filler[:12]
    live = [g for g, _ in scan(p, base, [(probe.encode("utf-16-be"), "be")])
            if not (cave and cave[0] <= g < cave[1]) and g != static]
    if not live:
        if verbose:
            print("  nothing was copied: the game refused this name.")
            print("  Try a shorter reservation, e.g. --reserve 60.")
        return None

    got, _ = read_utf16(p, base, live[0], maxunits=256)
    landed = len(got)
    if verbose:
        print(f"  slot = {live[0]:#010x}")
        if landed < nchars:
            print(f"  asked {nchars} characters, {landed} really copied")
            print(f"  -> the game truncates; real capacity = {landed}")
        else:
            print(f"  {landed} characters copied without truncation")

    ent = {"static": static, "live": live[0], "slot": None,
           "pristine": None, "reserved": landed}
    prime(p, c, actor, verbose=False)          # put the real name back in it
    raw = p.read(base + ent["live"], POOL_SAVE)
    if raw:
        ent["pristine"] = raw.hex()
    if verbose:
        print(f"  table = {static:#010x}")
        print(f"  {ent['reserved']} characters available without overflow")
    return ent


def session(p, base, c, name, actor, force=False, verbose=True, cave=None):
    """Everything to know for this session: entries, pointer, clean copy.

    Cached because the search costs ~6 s and is redone at every Cemu start
    (the addresses are in the heap). The cache's validity is checked on the
    CONTENT, not only on the PID.
    """
    key = f"{p.pid}:{name}"
    data = _cache_load()
    ent = data.get(key)
    if not force and isinstance(ent, dict) and ent.get("static"):
        first, _ = read_utf16(p, base, ent["static"])
        if first == name:
            check_pointer(p, base, ent, verbose)
            return ent

    if verbose:
        print(f"locating {name!r} (~6 s) ...")

    # Search BEFORE priming. Until the message has been resolved, only the
    # static table holds the name: a single occurrence is necessarily that
    # one, and it is located without any display. The former order cost three
    # visible flashes on screen -- the name, "ARCH0", then the name -- before
    # the real message.
    cands = exact_matches(p, base, name, exclude=cave)

    if not cands:
        # nothing at all: the table is not loaded yet, prime it
        if not prime(p, c, actor, verbose):
            if verbose:
                print("  the priming display did not answer.")
                print("  The message table is not loaded yet.")
                print("  Load a save, then run again.")
            return None
        cands = exact_matches(p, base, name, exclude=cave)
        if not cands:
            return None

    if len(cands) == 1:
        ent = {"static": cands[0], "live": None, "slot": None, "pristine": None}
    else:
        # the pool is already filled: sorting is needed, which costs a short flash
        static, live = classify(p, base, c, cands, name, actor)
        if not static:
            return None
        ent = {"static": static[0], "live": live[0] if live else None,
               "slot": None, "pristine": None}
        if ent["live"]:
            # The pool still holds the sorting marker. Have it rewritten by a
            # NORMAL resolution before taking the clean copy: without that,
            # --repair put "ARCH0" back on screen.
            prime(p, c, actor, verbose=False)
            raw = p.read(base + ent["live"], POOL_SAVE)
            if raw:
                ent["pristine"] = raw.hex()
            slots = [g for g, _ in scan(
                p, base, [(ent["live"].to_bytes(4, "big"), "p")], align=4)]
            # one pointer = an unambiguous redirection; several = abstain
            # rather than guess which one the widget uses
            if len(slots) == 1:
                ent["slot"] = slots[0]

    data[key] = ent
    CACHE.write_text(json.dumps(data))
    if verbose:
        print(f"  table  = {ent['static']:#010x}")
        if ent["live"]:
            print(f"  pool   = {ent['live']:#010x}")
        print(f"  OVERWRITE route, {SAFE_CHARS} characters per line")
    return ent


def say_via_pointer(p, base, c, text, slot, actor, duration=None, keep=False):
    """Redirect the widget's pointer to apText.

    Nothing is written into the game's tables: no length limit, no damage.
    The pointer is given back in a `finally` -- except with --keep, which tells
    whether the widget reads the pointer again every frame (in which case
    giving it back too early would drop the text back to the original name).
    """
    orig = p.read(base + slot, 4)
    addr = c.write_text(text)
    if not p.write(base + slot, addr.to_bytes(4, "big")):
        raise RuntimeError("pointer write refused")
    try:
        return c.notify(actor, duration=duration)
    finally:
        if orig and not keep:
            p.write(base + slot, orig)
            # read back: the game may rewrite this pointer on its side. Without
            # this check, it would stay aimed at apText and every resolved
            # message -- a real pickup included -- would show our text.
            back = p.read(base + slot, 4)
            if back != orig:
                print(f"  WARNING: the pointer did not hold "
                      f"({int.from_bytes(back or b'', 'big'):#010x} "
                      f"instead of {int.from_bytes(orig, 'big'):#010x})")
                print("  use --cleanup before playing on.")


# The game's color control code: marker, group 0, type 3, 2 bytes of
# parameter. Found in the message archive (14,824 occurrences), not guessed:
#   000E 0000 0003 0002 000N   switch to color N
#   000E 0000 0003 0002 FFFF   back to the default
COLOR = "\u000e\u0000\u0003\u0002"
RESET = COLOR + "￿"
TAG_COST = 5                    # code units per tag, taken from the budget


def colorize(s):
    """Translate the {N} ... {/} markup into the game's control codes."""
    out, i = [], 0
    while i < len(s):
        if s[i] == "{":
            j = s.find("}", i)
            if j != -1:
                body = s[i + 1:j]
                if body == "/":
                    out.append(RESET)
                    i = j + 1
                    continue
                if body.isdigit() and int(body) < 0xFFFF:
                    out.append(COLOR + chr(int(body)))
                    i = j + 1
                    continue
        out.append(s[i])
        i += 1
    return "".join(out)


def has_markup(s):
    return colorize(s) != s


def wrap(text, width=SAFE_CHARS):
    """Split into lines of at most `width` characters, at spaces.

    It is the answer kept for long texts. Widening the carrier's slot proved
    impractical (measurement not reproducible, crashes), while stacking
    several notifications already works and overflows onto nothing: each line
    fits in the measured margin.
    """
    lines, cur = [], ""
    for word in text.split():
        if len(word) > width:                 # a word longer than the line
            if cur:
                lines.append(cur)
                cur = ""
            while len(word) > width:
                lines.append(word[:width])
                word = word[width:]
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= width:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def repair_pool(p, base, ent, verbose=True):
    """Put back the pool's clean copy taken at the first location."""
    if not ent.get("pristine") or not ent.get("live"):
        return False
    ok = p.write(base + ent["live"], bytes.fromhex(ent["pristine"]))
    if verbose:
        print(f"  pool repaired: {'OK' if ok else 'REFUSED'}")
    return bool(ok)


def say_inplace(p, base, c, text, ent, name, actor, duration=None,
                force=False, repair=None, room=None):
    """Write into the static table, display, restore -- then repair the pool.

    It is the only route that ever showed our text. The game copies the table
    into the pool at display time; as the pool is a compact arena, a text
    longer than the carrier name overflows onto neighbouring messages. Hence
    the repair: `repair` is the delay in seconds before putting the clean copy
    back.

    `repair=0` repairs at once -- which tells whether the widget reads the
    pool again every frame (the text would then drop back to the original name
    on screen) or took a copy of it.
    """
    # a reserved slot allows its own size without overflow; otherwise stay
    # under the measured bound (40 pass, 44 crash)
    cap = MAX_CHARS if force else (room or ent.get("reserved") or SAFE_CHARS)
    if len(colorize(text)) > cap:
        raise ValueError(
            f"{len(text)} characters, ceiling {cap}. Without a widened carrier, 40 "
            f"pass and 44 crash the game.")
    # the saved window must cover what is written: with a carrier reserved at
    # 120 characters, 256 bytes would no longer be enough to restore it all.
    # The markup becomes control codes: the FINAL string counts for the
    # budget, each tag costing 5 code units
    payload = colorize(text)
    saved = p.read(base + ent["static"], max(WINDOW, len(payload) * 2 + 32))
    p.write(base + ent["static"], payload.encode("utf-16-be") + b"\x00\x00")
    try:
        ok = c.notify(actor, duration=duration)
    finally:
        if saved:
            p.write(base + ent["static"], saved)
    if repair is not None:
        if repair:
            time.sleep(repair)
        repair_pool(p, base, ent)
    return ok


def cleanup(p, base, ent):
    """Put the pointer back, then the pool's clean copy.

    The pointer first: it is what makes our text show instead of the name of
    an item really picked up.
    """
    if not ent:
        print("nothing cached for this session.")
        return False
    ok = True
    if ent.get("slot") and ent.get("live"):
        ok &= bool(p.write(base + ent["slot"],
                           ent["live"].to_bytes(4, "big")))
        print(f"pointer {ent['slot']:#010x} -> {ent['live']:#010x}: "
              f"{'OK' if ok else 'REFUSED'}")
    if ent.get("pristine") and ent.get("live"):
        raw = bytes.fromhex(ent["pristine"])
        w = p.write(base + ent["live"], raw)
        ok &= bool(w)
        print(f"{len(raw)} bytes of the pool restored: {'OK' if w else 'REFUSED'}")
    elif not ent.get("slot"):
        print("no clean copy cached.")
        print("Restart Cemu: the damage is only in RAM.")
        return False
    return ok


def inspect(p, base, c, name, actor, ent):
    print(f"static table    = {ent['static']:#010x}")
    print(f"pool (widget)   = "
          f"{ent['live']:#010x}" if ent.get("live") else "pool not located")
    if ent.get("slot"):
        cur = int.from_bytes(p.read(base + ent["slot"], 4) or b"\0" * 4, "big")
        print(f"pointer         = {ent['slot']:#010x} -> {cur:#010x}")
        print(f"route           = POINTER, up to {MAX_CHARS} characters")
    else:
        print(f"route           = OVERWRITE, ceiling {len(name)} characters")
    if ent.get("live"):
        raw = p.read(base + ent["live"], 64)
        if raw:
            txt = "".join(chr(int.from_bytes(raw[i:i + 2], "big"))
                          if 32 <= int.from_bytes(raw[i:i + 2], "big") < 0xD800
                          else "." for i in range(0, 48, 2))
            print(f"pool content: {txt!r}")
            print("  (garbled characters here = damaged pool, "
                  "use --cleanup)")


def main():
    argv = sys.argv[1:]
    if not argv:
        sys.exit(__doc__)

    def opt(n, default=None):
        """Value of an option, or the default.

        The bound is checked: an option placed LAST (--palette alone) raised an
        IndexError instead of taking its default.
        """
        if n not in argv:
            return default
        i = argv.index(n) + 1
        if i >= len(argv) or argv[i].startswith("--"):
            return default
        return argv[i]

    # carrier.json, when present, says which item carries the filler and
    # which text to search for. Without it, the unmodified game is assumed
    # (DEFAULT_NAME, 40 characters per line).
    carrier = pathlib.Path(__file__).resolve().parent / "carrier.json"
    cinfo = {}
    if carrier.exists():
        try:
            cinfo = json.loads(carrier.read_text(encoding="utf-8"))
        except ValueError:
            pass
    name = opt("--name", cinfo.get("name", DEFAULT_NAME))
    actor = opt("--actor", cinfo.get("actor", DEFAULT_ACTOR))
    room = cinfo.get("chars")
    duration = None
    if "--persist" in argv:
        duration = 100000.0
    elif "--duration" in argv:
        duration = float(opt("--duration"))
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
        base, cave_g, _ = guest_base(p, a - 12)
        if base is None:
            sys.exit("guest/host base not found")
        c = Cave(p, a, base)
        # our cave, excluded from the scan: the game writes into it as soon as
        # the pointer is redirected, and our own buffer would then be found
        cave = (cave_g, cave_g + 2048)

        if "--check" in argv:
            # No display: useful precisely when displaying crashes. Only says
            # whether the carrier name is in memory, hence whether Cemu applied
            # the file replacement.
            hits = exact_matches(p, base, name, exclude=cave)
            print(f"expected carrier: {name[:24]!r}... ({len(name)} characters)")
            if hits:
                print(f"FOUND at {', '.join(f'{h:#010x}' for h in hits)}")
                print("Cemu applied the file replacement.")
            else:
                print("NOT in memory.")
                short = exact_matches(p, base, DEFAULT_NAME, exclude=cave)
                if short:
                    print(f"But {DEFAULT_NAME!r} is there: the mod is")
                    print("NOT loaded (pack unchecked, or Cemu does not replace")
                    print("the file).")
                else:
                    print("And the original name is not either: the game may")
                    print("not have finished loading.")
            return


        ok, rn, tick = c.resolve_ready()
        if not ok:
            sys.exit(
                f"the loaded patch's resolver does not run "
                f"(apResolveN={rn}, tick={tick}).\n"
                "CLOSE AND REOPEN CEMU: reloading a save is not "
                "enough.")
        if not c.ready():
            sys.exit(
                "the notification row pool is not resolved\n"
                "(screen 0x28 missing from the screen table).\n"
                "Load a save, then run again.")

        if "--reserve" in argv:
            # A route set aside: two attempts gave 78 then 13 characters, and
            # the third crashed the game. Writing a very long name into the
            # static table corrupts the following messages while the game may
            # read them.
            sys.exit(
                "--reserve is disabled: measurement not reproducible (78 then\n"
                "13 characters) and a game crash at the third attempt.\n"
                "Use the split into several lines, which is reliable:\n"
                '  python tools/cemu/say.py "a long text..." --duration 8')

        ent = session(p, base, c, name, actor,
                      force="--relocate" in argv, cave=cave)
        if ent is None:
            print(f"entry {name!r} not found.")
            print("  - the text must be exactly the one shown on screen")
            print("  - has a notification been shown at least once?")
            return

        if "--cleanup" in argv:
            cleanup(p, base, ent)
            return
        if "--inspect" in argv:
            inspect(p, base, c, name, actor, ent)
            return
        if not positional:
            print("")
            print("Give the text to show as an argument.")
            return

        repair = float(opt("--repair")) if "--repair" in argv else None

        if "--palette" in argv:
            # One hue per stacked line: a line's budget does not allow showing
            # several colors at once (10 code units per colored segment).
            n = int(opt("--palette") or 8)
            print(f"{n} hues, one per line -- note the ones you like")
            for k in range(n):
                line = "{%d}color %d{/}" % (k, k)
                try:
                    say_inplace(p, base, c, line, ent, name, actor,
                                duration or 12.0, force=True, room=room)
                except (ValueError, RuntimeError) as e:
                    sys.exit(str(e))
                time.sleep(0.35)
            print("Look at the screen.")
            return

        text = " ".join(positional)
        if opt("--color") is not None:
            text = "{%s}%s{/}" % (opt("--color"), text)
        width = room or SAFE_CHARS
        if has_markup(text):
            # markup would cross a line break badly: an opening without its
            # closing would tint everything after it
            lines = [text]
        else:
            lines = wrap(text, width) if "--nowrap" not in argv else [text]
        if len(lines) > 1:
            print(f"{len(text)} characters -> {len(lines)} stacked lines")
            for i, line in enumerate(lines):
                print(f"  {i + 1}. {line!r}")
                try:
                    say_inplace(p, base, c, line, ent, name, actor,
                                duration, force="--force" in argv,
                                repair=repair, room=room)
                except (ValueError, RuntimeError) as e:
                    sys.exit(str(e))
                time.sleep(0.35)   # let the previous line move down
            print("")
            print("Look at the screen.")
            return

        text = lines[0]
        print(f"showing: {text!r} ({len(text)} characters)")
        try:
            if "--pointer" in argv:
                # kept for reference: the game WRITES the resolved message
                # through this pointer, so our text is overwritten before it is
                # drawn. Checked in the game -- only shows the original name.
                ok = say_via_pointer(p, base, c, text, ent["slot"], actor,
                                     duration, keep="--keep" in argv)
            else:
                ok = say_inplace(p, base, c, text, ent, name, actor,
                                 duration, force="--force" in argv,
                                 repair=repair, room=room)
        except (ValueError, RuntimeError) as e:
            sys.exit(str(e))
        print("notification triggered -- look at the screen" if ok
              else "the injected code did not answer (tick at 0?)")


if __name__ == "__main__":
    main()
