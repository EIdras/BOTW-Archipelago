"""Show OUR text in the dialog window -- the blue box.

    python tools/cemu/saydialog.py --state
    python tools/cemu/saydialog.py --open              # original carrier
    python tools/cemu/saydialog.py "Alice sends you a Sword"
    python tools/cemu/saydialog.py --colors            # which index = which hue
    python tools/cemu/saydialog.py --fill 300          # marks every 10
    python tools/cemu/saydialog.py "..." --nowrap      # keep your own \n
    python tools/cemu/saydialog.py "..." --arc DemoMsg/Demo008_2 --label talk00

MARKUP

    {0}..{/}      color; {/} goes back to the default
    {size:80}     code group 0 / type 2, as a percentage
    {t:g,t,hex}   any control code, to experiment
    \n            line break

COLORS, READ ON SCREEN

    {0} red       {1} green    {2} light blue   {3} black (dark grey)
    {4} blue      {5} grey     {6} white        {/} white (default)

The order of zeldamods' list (blue, red, grey...) is NOT the order of the
indices: only the screen told. The hues being defined per layout in the
`.bflyt`, this table holds for the dialog window -- nothing guarantees it holds
for the tip frame or the notification.

DURATION: NOT FOUND

The two candidates of the census (group 1 type 3, group 1 type 0) had no
visible effect: the text shows at once, there is no typewriter effect to time
on this path. `{pause:N}` was therefore REMOVED from the markup rather than
left to suggest it works.

The `-1` passed as 6th argument of `0x0358fd38` is not a duration either: the
constant `0x24924925` that follows is the magic reciprocal of 7, and the
function computes `(index(label) + r6) mod 7` -- a variant selector.

Pages are therefore chained by the window, not by the text.

HOW MANY CHARACTERS

The carrier limits nothing: the message arena is not overwritten,
`this+0x1d0` is made to point to our own buffer.

Measured: **three lines of 30 characters per page**, and the game pages by
itself beyond that -- 309 units showed in three pages. The text is therefore
split at spaces at 30 characters by default, markup not counting in the width.
`--nowrap` leaves it to you, `--width N` changes the width.

The total ceiling comes from our buffer (2047 units); the window swallowed 826
units without a hitch. `--fill N` places marks every ten characters to read a
truncation at a glance.

THE CHAIN, ESTABLISHED BY MEASUREMENT

The message resolution tracer showed that the label `talk00` of the shrine
message is resolved from the site `0x035fb64c`. Going up:

    0x035ff8fc(_, SafeString* archive, SafeString* label, a, b, flag)
        opens the window if needed, then if flag == 0 calls
    0x035fb5f8(this, archive, label)
        resolves the message and stores { text, length } in this+0x1d0

The first argument of `0x035ff8fc` is ignored (the window comes from a
global), and `a` / `b` are only read on the branch with a non-zero flag --
checked: r26 and r27 only appear again at `0x035ffa1c` / `0x035ffa20`. They are
therefore left at zero. `--replay` replays the ones a real opening left, to
compare.

FREE TEXT

No detour through the message arena: `this+0x1d0` is overwritten directly with
`{ our UTF-16BE buffer, length }`, in the SAME frame as the opening
(`apCheckDlg` then `apCheckDlgText` are two consecutive blocks of the per-frame
hook). The length is in UTF-16 units, terminator excluded -- measured on the
tip frame: a carrier of 101 units, a length read as 100.

PREREQUISITE: NONE ANY MORE, except that the game's UI exists

The flag (6th argument) is ALWAYS forced to zero. At 1, the function goes into
0x035fb1b4, which dereferences the 4th and 5th arguments: replaying those of an
earlier call -- heap pointers already dead -- crashed the game. At zero they
are never read.

A real dialog box used to be needed since the start. It was a lock of OUR
making, and it protected nothing: the arguments it waited for are forced to
zero anyway. 0x035ff8fc itself asks for nothing -- it fetches screen 0x26 from
the manager's table and CREATES it when missing (`li r3, 0x26 ; bl
0x033924c4`). Checked cold: slot 0x26 went from 0x00000000 to a live screen on
our call.

The only prerequisite left comes from the game: 0x035ff8fc dereferences
*(0x1047E650) without testing it. The cave therefore resolves the screen table
every frame (apScrTable) and refuses while it is 0.
"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winmem import Process
from mailbox import Cave, be, cemu_pid, diagnose, find_cave, guest_base
from say import colorize

DEFAULT_ARC = "DemoMsg/Demo008_2"
DEFAULT_LABEL = "talk00"


def tag(grp, typ, params=b""):
    """A control code: 0x000E, group, type, size, parameters.

    Encoding read from the game's MSBT files, not assumed: the color already
    used by say.py (`000e 0000 0003 0002 <index>`) is the special case
    group 0 / type 3, and every other code has the same form.
    """
    if len(params) % 2:
        raise ValueError("parameters are counted in 16-bit units")
    units = [0x000E, grp, typ, len(params)]
    units += [int.from_bytes(params[i:i + 2], "big")
              for i in range(0, len(params), 2)]
    for u in units:
        if 0xD800 <= u <= 0xDFFF:
            raise ValueError(f"unit {u:#06x} in the UTF-16 surrogate range: "
                             f"cannot be encoded")
    return "".join(chr(u) for u in units)


# Found by a census of the game's 991 MSBT files: the percentage is the only
# parameter seen (100, 80, 125, 120). The encoding's form is certain, its
# effect only for color and size -- the two timing candidates changed nothing
# on screen. {t:g,t,hex} tries any other code without touching the source.
SIZE = lambda pct: tag(0, 2, pct.to_bytes(2, "big"))  # 100, 80, 125, 120


def markup(s):
    """Extended markup, on top of say.py's {N}...{/}.

        {0}..{/}      color (index 0 to 6, {/} goes back to the default)
        {size:80}     code group 0 / type 2, percentage
        {t:g,t,hex}   any code, to experiment
        \\n            line break (the window shows three)
    """
    s = s.replace("\\n", "\n")
    out, i = [], 0
    while i < len(s):
        if s[i] == "{":
            j = s.find("}", i)
            if j != -1:
                body = s[i + 1:j]
                if body.startswith("size:"):
                    out.append(SIZE(int(body[5:], 0)))
                    i = j + 1
                    continue
                if body.startswith("t:"):
                    g, t, hx = body[2:].split(",")
                    out.append(tag(int(g, 0), int(t, 0), bytes.fromhex(hx)))
                    i = j + 1
                    continue
        out.append(s[i])
        i += 1
    return colorize("".join(out))


WIDTH = 30          # measured: three lines of 30 fit on a page
LINES = 3


def wrap_markup(s, width=WIDTH):
    """Split at spaces, without counting markup in the width.

    A `{0}` takes no room on screen: counting it would make lines too short,
    and splitting in its middle would break the tag. Groups between braces are
    therefore zero-width tokens, never split.
    """
    if "\n" in s or "\\n" in s:
        return s                      # split already chosen by the caller

    def visible(tok):
        out, i = 0, 0
        while i < len(tok):
            if tok[i] == "{" and tok.find("}", i) != -1:
                i = tok.find("}", i) + 1
                continue
            out += 1
            i += 1
        return out

    lines, cur, cur_len = [], "", 0
    for word in s.split(" "):
        w = visible(word)
        if cur and cur_len + 1 + w > width:
            lines.append(cur)
            cur, cur_len = word, w
        else:
            cur = word if not cur else cur + " " + word
            cur_len = w if cur_len == 0 else cur_len + 1 + w
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def poke_cstr(p, addr, s, size):
    data = s.encode("ascii", "replace")
    if len(data) + 1 > size:
        raise ValueError(f"{s!r} exceeds the {size}-byte buffer")
    p.write(addr, data + bytes(size - len(data)))


def wait(p, field, before, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(0.05)
        raw = p.read(field, 4)
        if not raw:
            raise RuntimeError("Cemu no longer answers (the game crashed).")
        if be(raw) != before:
            return True
    return False


def state(p, c):
    print(f"  screen table (apScrTable)    : {be(p.read(c.scr_table, 4)):#010x}")
    print(f"  openings seen (0x035ff8fc)   : {be(p.read(c.dlg_open_n, 4))}"
          f"  of which with a zero flag: {be(p.read(c.dlg_open0_n, 4))}")
    print(f"  messages set (0x035fb5f8)    : {be(p.read(c.dlg_set_n, 4))}")
    print(f"  window (this)                : {be(p.read(c.dlg_this, 4)):#010x}")
    print(f"  arguments read               : "
          f"a={be(p.read(c.dlg_arg6, 4)):#010x} "
          f"b={be(p.read(c.dlg_arg7, 4)):#010x} "
          f"flag={be(p.read(c.dlg_arg8, 4))}")
    this = be(p.read(c.dlg_this, 4))
    if this and c.base is not None:
        raw = p.read(this + 0x1D0 + c.base, 8)
        if raw:
            print(f"  this+0x1d0                   : "
                  f"ptr={be(raw[0:4]):#010x} length={be(raw[4:8])}")


def main():
    argv = sys.argv[1:]

    def opt(name, default=None):
        if name in argv and len(argv) > argv.index(name) + 1:
            return argv[argv.index(name) + 1]
        return default

    arc = opt("--arc", DEFAULT_ARC)
    label = opt("--label", DEFAULT_LABEL)
    text = next((a for a in argv if not a.startswith("--")
                 and a not in (arc, label)), None)

    if "--colors" in argv:
        # Indices 0 to 6 exist (census of the MSBT files) but nothing says
        # which gives which hue: the only judge is the screen.
        text = ("{0}zero{/} {1}one{/} {2}two{/}\\n"
                "{3}three{/} {4}four{/} {5}five{/}\\n"
                "{6}six{/} seven-default")
    if "--fill" in argv:
        n = int(opt("--fill", "200"))
        # Marks every ten characters: a truncation reads at a glance, where
        # a uniform text would say nothing.
        base = "".join(f"{(k // 10) % 10}" if k % 10 else "|"
                       for k in range(n))
        text = "\\n".join(base[k:k + 30] for k in range(0, len(base), 30))

    pid = cemu_pid()
    if not pid:
        sys.exit("Cemu is not running")

    with Process(pid, writable=True) as p:
        a = find_cave(p)
        if a is None:
            print("cave not found.\n")
            diagnose()
            return
        base, _, _ = guest_base(p, a - 12)
        c = Cave(p, a, base)

        if "--state" in argv or (not text and "--open" not in argv):
            print("state of the dialog window:\n")
            state(p, c)
            print("")
            print("To open it:     --open")
            print("With some text: saydialog.py \"my text\"")
            return

        ok, rn, tick = c.resolve_ready()
        if not ok:
            sys.exit(f"the loaded patch's resolver does not run "
                     f"(apResolveN={rn}, tick={tick}).\n"
                     "CLOSE AND REOPEN CEMU: reloading a save is not "
                     "enough.")
        if not be(p.read(c.scr_table, 4)):
            sys.exit("the game's UI is not built (screen table "
                     "not found).\nLoad a save, then run again.")

        # --- the flag stays at zero, and it is not a detail ------------------
        # At 1, 0x035ff8fc goes into 0x035fb1b4, which DEREFERENCES the 4th and
        # 5th arguments. Replaying those of an earlier call -- two heap pointers
        # already dead -- crashed the game. At 0 they are never read: they are
        # left at zero rather than passing on values with no guarantee.
        a6 = a7 = 0
        flag = 0
        if "--replay" in argv:
            a6 = be(p.read(c.dlg_arg6, 4))
            a7 = be(p.read(c.dlg_arg7, 4))
            print(f"  --replay: a={a6:#010x} b={a7:#010x} (flag forced to 0)")
        p.write(c.dlg_arg6, a6.to_bytes(4, "big"))
        p.write(c.dlg_arg7, a7.to_bytes(4, "big"))
        p.write(c.dlg_arg8, flag.to_bytes(4, "big"))

        poke_cstr(p, c.arc_buf, arc, 64)
        poke_cstr(p, c.lbl_buf, label, 32)

        if text:
            if "--nowrap" not in argv:
                text = wrap_markup(text, int(opt("--width", WIDTH)))
            s = markup(text)
            try:
                ptr, n = c.write_dlg_text(s)
            except ValueError as e:
                sys.exit(f"{e}\nNothing was sent to the game: the request is\n"
                         f"only placed once the text is written.")
            p.write(c.dlg_str_ptr, ptr.to_bytes(4, "big"))
            p.write(c.dlg_str_len, n.to_bytes(4, "big"))

        print(f"archive {arc!r}  label {label!r}")
        before_open = be(p.read(c.dlg_done, 4))
        before_text = be(p.read(c.dlg_text_done, 4))

        # --- never write into a stale 'this' ---------------------------------
        # The window is a transient object: the pointer captured in the
        # previous session may have been freed, and writing onto it is what
        # crashed the game on the PickUpWin side. It is reset to zero; only
        # the probe of OUR call, in the same frame, fills it again. If the
        # call does not happen, the text block does nothing.
        p.write(c.dlg_this, bytes(4))

        if text:
            p.write(c.dlg_text_req, (1).to_bytes(4, "big"))
        p.write(c.dlg_req, (1).to_bytes(4, "big"))

        ok = wait(p, c.dlg_done, before_open)
        print(f"  opening: {'call made' if ok else 'NONE'}")
        if text:
            ok2 = wait(p, c.dlg_text_done, before_text)
            print(f"  text   : {n} UTF-16 units, "
                  f"{'written' if ok2 else 'NOT WRITTEN'}")
        print("")
        state(p, c)


if __name__ == "__main__":
    main()
