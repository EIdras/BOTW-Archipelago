"""Open the large item get window, with our text.

    python tools/cemu/getdemo.py --state
    python tools/cemu/getdemo.py Item_Fruit_A
    python tools/cemu/getdemo.py Item_Ore_E --title "Bombs" --desc "Sent by Alice"
    python tools/cemu/getdemo.py Item_Ore_E --title "{2}Bombs{/} (Alice)"
    python tools/cemu/getdemo.py Item_Fruit_A --colors   # the 7 indices on screen

MARKUP, the same as the dialog box's

    {0}..{/}      color; {/} goes back to the default
    {size:80}     size, as a percentage
    {t:g,t,hex}   any control code, to experiment
    a literal backslash-n      line break (the description accepts several;
                               the pane does not wrap by itself)

Nothing special was needed: the substitution writes raw UTF-16BE, and control
codes are units of that stream like any other.

COLORS, READ ON SCREEN IN THIS WINDOW

    {0} red       {1} green     {2} black (dark grey)   {3} blue
    {4} orange    {5} light grey    {6} white

BEWARE: this is NOT the dialog box's table. Both share indices 0 and 1, then
differ -- here {2} is black and {4} orange, there {2} is light blue and {4}
blue, and orange does not exist. The index -> hue table is defined PER LAYOUT
in the `.bflyt`: each channel has its own, and assuming it shared gives text of
the wrong color without any warning. `--colors` shows the seven indices side by
side to measure it elsewhere.

THE CALL

    0x035fe7f4(manager, string_object)
        manager = *(0x1047b054)    NOT *(0x1047e650), which is the screens' one
        string_object = { ASCII char* @+0 ; 0x1008bf50 @+4 ; size @+8 }

It does three things: create screen 0x0b, COPY THE ACTOR NAME into
`manager->0x20` (truncated at `->0x28`, 64 bytes), then open it. The middle
step is the one a synthetic window lacked, and why such a window was drawn
showing nothing: it was EMPTY.

From the actor name alone, the game resolves title, description AND icon.

WHERE THE ADDRESS COMES FROM

An anchoring chain, entirely offline:

    Randomizer (Waikuteru's mod) calls GetDemo::GetItemByNameR
      -> SUBFLOW GetDemo::ShowGetDemoDialogByName
        -> EventSystemActor::Demo_OpenGetDemoDialog
          -> EventSystemActor.baiprog, Action_100: ClassName OpenGetDemoDialog
            -> its 4 parameter names, contiguous in .rodata (0x1008bf90...)
              -> all referenced by 0x0234be58 = loadParams_
                -> a single relocation targets it: vtable 0x1008bff8
                  -> enter_ = 0x0234bba8, whose simple path does:
                       r3 = *(0x1047b054) ; r4 = this+0x1c ; bl 0x035fe7f4

The string object, measured on three sites (one of them a construction on the
stack at 0x0234bd1c): `{ const char* @+0 ; vtable @+4 ; s32 size @+8 }`. The
vptr is at +0x04, not +0x00 -- counter-intuitive, but 0x035fe7f4 does read the
char* at +0x00 to copy it, and only calls vtable[+0x1c] (length).

WHAT IS CHECKED IN THE GAME

* the window shows completely: title, description and icon;
* it STAYS OPEN by itself -- nothing needs to hold it up;
* the player closes it with the button, like a real one. There is nothing to
  implement to close it.

THE TRAP

A window left open POISONS THE NEXT ITEM: the next chest shows OUR item instead
of its own. `enter_` tests `0x035fda08()` first and takes another path
(`0x035ff004`) when a window already exists -- the real item's name is then
never copied. Hence the refusal to open over a window in progress, unless
`--force`.

THE ORACLE

Do not take the screen's word for it: the deciding check is `manager->0x20`
AFTER the call. If it holds the name, the call went through. It is the only
witness telling "nothing happened" from "the window opens but shows nothing".

A negative measurement, not to redo: setting bit 0x100 of `screen+0x94` -- the
close flag the game uses itself -- is INERT here.
"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mailbox import open_cave, CaveUnavailable, be
from saydialog import markup

# --- guest addresses, 1.5.0 EUR ------------------------------------------
MGR_PTR = 0x1047B054      # -> the get window's manager
SCR_PTR = 0x1047E650      # -> the SCREEN manager (slot 0x0b = the window)
OPEN_FN = 0x035FE7F4      # (mgr, string): creates, fills the name, opens
STR_VT = 0x1008BF50       # vtable of the string object

# The string object lives in the TAIL of apText, after the ASCII name. Never in
# sub_buf: it is the substitution's TITLE buffer, and overwriting it would arm
# a corrupt title at the first window.
OBJ_OFF = 0xC0

# A useful neighbour, not called here: 0x035fda08() says whether the window is
# free. It IGNORES its arguments -- it reads screen 0x0b itself, which screen()
# below also does, more cheaply.


def rd(p, c, guest, n=4):
    """Read n bytes at a guest address."""
    raw = p.read(c.base + guest, n)
    return be(raw) if n == 4 else raw


def screen(p, c):
    """(screen of slot 0x0b, activity byte). The same computation as 0x035fda08."""
    scr = rd(p, c, SCR_PTR)
    if not scr:
        return 0, 0xFF
    tab = rd(p, c, scr + 0x18)
    e = rd(p, c, tab + 0x0B * 4) if tab else 0
    return e, (rd(p, c, scr + 0x604, 0x10)[0x0B] if e else 0xFF)


def state(p, c, verbose=True):
    """The manager, its name buffer, the screen, the substitution."""
    mgr = rd(p, c, MGR_PTR)
    e, act = screen(p, c)
    if not verbose:
        return mgr, e, act
    print(f"manager *({MGR_PTR:#010x}) = {mgr:#010x}")
    if not mgr:
        print("  NULL -- the game has not built the get window yet.")
        print("  Pick up an item once, then run again.")
        return mgr, e, act
    buf, cap = rd(p, c, mgr + 0x20), rd(p, c, mgr + 0x28)
    print(f"  ->0x20  name buffer   = {buf:#010x}")
    print(f"  ->0x28  capacity      = {cap} ({cap:#x})")
    if buf:
        print(f"  current content      = {c.cstr(buf, min(cap, 64))!r}")
    print(f"screen slot 0x0b = {e:#010x}   activity = {act:#04x}"
          + ("   OPEN" if e and act != 0xFF else "   (absent)" if not e else ""))
    ok, req = be(p.read(c.opn_ok, 4)), be(p.read(c.opn_req, 4))
    line = "invoker: "
    if hasattr(c, "pf_req") and c.pf_ready():
        pfr = be(p.read(c.pf_req, 4))
        line += "per-frame AVAILABLE (no prerequisite)"
        line += f"   request PENDING={pfr}" if pfr else ""
        line += f"   |  former apOpnOk={ok}"
    elif hasattr(c, "pf_req"):
        line += (f"per-frame MISSING from the loaded patch (apPfReq reads "
                 f"{be(p.read(c.pf_req, 4)):#x}) -- STALE PATCH, close and "
                 f"reopen Cemu; meanwhile, the former invoker "
                 f"(apOpnOk={ok})")
    else:
        line += f"apOpnOk={ok} " + ("(alive)" if ok
                                    else "(ASLEEP -- open a chest once)")
    line += f"   former request PENDING={req}" if req else ""
    print(line)
    t_req, t_ok, d_req, d_ok, auto = c.sub_state()
    if t_req or d_req or auto:
        print(f"substitution ARMED: title={t_req} desc={d_req} auto={auto}")
    return mgr, e, act


def main():
    opt = sys.argv[1:]
    argv = [a for a in opt if not a.startswith("--")]
    # take out the values of options with an argument
    for name in ("--title", "--desc"):
        if name in opt:
            v = opt[opt.index(name) + 1] if len(opt) > opt.index(name) + 1 else None
            if v in argv:
                argv.remove(v)

    # Testing `startswith("--")` does not work: a title may start with dashes,
    # which is exactly the case of measuring rulers.
    FLAGS = {"--state", "--force", "--title", "--desc",
             "--colors", "--legacy"}

    def val(name):
        i = opt.index(name) if name in opt else -1
        if i < 0:
            return None
        if i + 1 >= len(opt) or opt[i + 1] in FLAGS:
            sys.exit(f"{name} needs a value")
        return opt[i + 1]

    try:
        p, c = open_cave()
    except CaveUnavailable as e:
        sys.exit(str(e))

    with p:
        mgr, e, act = state(p, c)
        if "--state" in opt or not mgr:
            return
        if not argv:
            sys.exit('\nGive an actor name:\n'
                     '  python tools/cemu/getdemo.py Item_Fruit_A '
                     '--title "Bombs" --desc "Sent by Alice"')

        # Two invokers. The per-frame one (apPfReq) runs from the game's
        # start; the former one (apOpnReq, mode 8) lives in the MessageGet_00
        # driver and stays silent behind apOpnOk until the real window has
        # been seen -- leaving its request PENDING, which then went off at the
        # next real chest, which showed our item.
        pf = (hasattr(c, "pf_req") and c.pf_ready()
              and "--legacy" not in opt)
        if not pf and not be(p.read(c.opn_ok, 4)):
            sys.exit(
                "\nREFUSED: the former invoker is not alive yet "
                "(apOpnOk=0).\n"
                "  Open a chest once, or drop --legacy.\n"
                "  Nothing was armed: the next chest is intact.")

        if e and act != 0xFF and "--force" not in opt:
            sys.exit(
                "\nREFUSED: a window is already open.\n"
                "  Opening one over it would not copy the name, and the\n"
                "  NEXT REAL CHEST would show this item instead of its\n"
                "  own. Close the window with the button, then run again.\n"
                "  (--force to override, knowingly.)")

        name = argv[0]
        # The pane DOES NOT WRAP by itself: the game's descriptions carry
        # their own line breaks. A literal "\n" is therefore accepted.
        #
        # MARKUP: the same as the dialog box -- {N}...{/} for the color,
        # {size:80} for the size, {t:g,t,hex} to try any code. Nothing special
        # is required here: the substitution writes raw UTF-16BE into
        # this->{text, length}, exactly like the other channels, and control
        # codes are units of that stream. The length passed to the game counts
        # them, which is right -- the game does so for its own messages.
        #
        # CAVEAT, not lifted: the index -> hue table is defined PER LAYOUT in
        # the .bflyt. The one read on screen holds for the dialog box; nothing
        # guarantees that the get window uses the same. `--colors` shows the
        # seven indices to measure it.
        title, desc = val("--title"), val("--desc")
        if "--colors" in opt:
            title = "{0}A{1}B{2}C{3}D{4}E{5}F{6}G{/}H"
            desc = ("{0}zero {1}one {2}two {3}three\\n"
                    "{4}four {5}five {6}six{/} default")
        if title is not None:
            title = markup(title)
        if desc is not None:
            desc = markup(desc)
        cap = rd(p, c, mgr + 0x28)
        if len(name) + 1 > cap:
            print(f"\nWARNING: {len(name)} characters for a capacity of "
                  f"{cap} -- the game will truncate.")

        # The text is armed BEFORE the opening: the pane freezes its content
        # when it is built, not afterwards.
        if title is not None:
            c.sub_write(title)
            print(f"title armed      : {title!r}")
        if desc is not None:
            c.sub_write_desc(desc)
            print(f"description armed: {desc!r}")

        name_g = c.write_text(name, "ascii")
        obj_g = c.guest(c.text_buf + OBJ_OFF)
        p.write(c.text_buf + OBJ_OFF,
                name_g.to_bytes(4, "big")
                + STR_VT.to_bytes(4, "big")
                + (0x40).to_bytes(4, "big"))
        print(f"string object at {obj_g:#010x} = "
              f"{{ {name_g:#010x} ; {STR_VT:#010x} ; 0x40 }}   name={name!r}")

        n = be(p.read(c.call_n, 4))
        route = "per-frame (apPfReq)" if pf else "MessageGet_00 driver (mode 8)"
        print(f"call 0x035fe7f4({mgr:#010x}, {obj_g:#010x})  via {route}")
        (c.call_pf if pf else c.call)(OPEN_FN, mgr, obj_g)

        for _ in range(300):
            if be(p.read(c.call_n, 4)) > n:
                break
            time.sleep(0.01)
        else:
            # A request not consumed STAYS PENDING in the cave and goes off at
            # the driver's next pass -- so at the next real chest, which then
            # showed our item. Cancelling it is mandatory.
            p.write(c.pf_req if pf else c.opn_req, bytes(4))
            if title is not None or desc is not None:
                c.sub_disarm()
            sys.exit("the cave did not answer: request CANCELLED, substitution "
                     "disarmed.\n  Is the game running?")

        buf = rd(p, c, mgr + 0x20)
        seen = c.cstr(buf, min(cap, 64)) if buf else None
        ok = seen == name
        print(f"\nmgr->0x20 after the call = {seen!r}  "
              + ("<-- the name went through" if ok else "<-- NOT the expected name"))
        e, act = screen(p, c)
        print(f"screen slot 0x0b = {e:#010x}   activity = {act:#04x}"
              + ("" if e and act != 0xFF else "   NOTHING WILL BE DRAWN"))

        # An arming that is not consumed would hit the next REAL chest. On a
        # failure it is disarmed rather than left as a mine.
        if not ok and (title is not None or desc is not None):
            c.sub_disarm()
            print("substitution disarmed (the call did not go through)")

        if e:
            print("\nClose the window with the button before playing on:\n"
                  "  left open, it will show THIS item at the next "
                  "chest.")


if __name__ == "__main__":
    main()
