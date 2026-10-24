"""Read-only gameplay/UI/protection guard of the presentation queue."""
import zlib

PROTECTIONS = ("CarryProhibition", "TrashProhibition", "PlayFlashbackDemoProhibition")


def flag_reader(process, cave):
    from tools.cemu.livegdt import LiveGdt
    live = LiveGdt(process, cave.base)
    live.build(kinds=("s32", "bool"))
    def read():
        result = {name: live.get(zlib.crc32(name.encode()), "s32")
                  for name in ("APReceivedCursor", "APSeedToken")}
        result.update({name: live.get(zlib.crc32(name.encode()), "bool") for name in PROTECTIONS})
        if any(value is None for value in result.values()):
            raise RuntimeError("Flags illisibles")
        return result
    return read


def presentation_gameplay_state(catalog):
    """Classify strict overworld and the HUD-less playable shrine state.

    The loading diagnostic deliberately keeps requiring the active HUD. Native
    presentations may also run after a shrine terminal, where that HUD screen
    stays allocated but inactive even though every menu/loading/dialogue screen
    is closed.
    """
    from tools.cemu.loading_diagnostic import gameplay_state, loading_closed
    from tools.cemu.menu_diagnostic import menu_state

    strict = gameplay_state(catalog)
    rows = catalog["screens"]
    hud = rows[42]
    hudless = (menu_state(catalog, "map")["idle"] and loading_closed(rows)
               and not rows[74]["pointer"] and rows[74]["activity"] == 255
               and bool(hud["pointer"]) and hud["activity"] == 255
               # Both exact inactive HUD states were measured in playable
               # shrines: 0, and 0x00fc0000.
               # Keep active/unknown states excluded; the caller additionally
               # requires live gameplay pointers, advancing tick and save guard.
               and hud["state_94"] in (0, 0x00fc0000))
    mode = "strict_hud" if strict["ready"] else "hudless_shrine" if hudless else "blocked"
    return dict(ready=bool(strict["ready"] or hudless), mode=mode,
                strict_ready=bool(strict["ready"]), hudless_ready=bool(hudless),
                loading_observed=strict["loading_observed"],
                dialogue_observed=strict["dialogue_observed"],
                screens=strict["screens"])


def ready(process, cave, read_flags, *, allow_hudless=False):
    from tools.cemu.menu_diagnostic import screens
    from tools.cemu.getdemo_state import snapshot
    ui = snapshot(process, cave.base)
    if not ui["manager"] or ui["screen"] or ui["name"]:
        return False
    gameplay = presentation_gameplay_state(screens(process, cave.base))
    if not gameplay["strict_ready"] and not (allow_hudless and gameplay["hudless_ready"]):
        return False
    flags = read_flags()
    return all(flags[name] == 0 for name in PROTECTIONS)


# What each screen of the catalog shows while Link plays (menu_diagnostic,
# loading_diagnostic): (name, present, activity, states); None: not checked.
CLOSED = (0x01000000, 0x01fc0000)
GAMEPLAY_SCREENS = {
    44: ("map", True, 255, CLOSED), 46: ("menu", True, 255, CLOSED), 47: ("inventory", False, 255, None),
    68: ("menu 68", True, 255, CLOSED), 78: ("loading", True, 255, CLOSED),
    84: ("loading 84", True, 255, (0x01000000,)), 85: ("loading 85", False, 255, None),
    74: ("dialogue", False, 255, None),
}


def unexpected_screens(catalog) -> list[str]:
    """The screens of the catalog not as they are while Link plays, with what
    they show (the HUD apart: summary() gives it)."""
    out, rows = [], catalog.get("screens") or []
    for index, (name, present, activity, states) in GAMEPLAY_SCREENS.items():
        if index >= len(rows):
            continue
        row = rows[index]
        state = row["state_94"]
        if (bool(row["pointer"]) != present or row["activity"] != activity
                or (states is not None and state not in states)):
            out.append(f"{name} (screen {index}): {'present' if row['pointer'] else 'absent'}, "
                       f"activity {row['activity']}" + (f", state {state:#x}" if isinstance(state, int) else ""))
    return out


def summary(diagnosis: dict) -> str:
    """One line of diagnose(): what holds the presentations, the screens not as
    while Link plays, and the HUD screen's state."""
    hud = (diagnosis.get("gameplay", {}).get("screens") or [{}])[0]
    state = hud.get("state_94")
    screens = diagnosis.get("unexpected_screens") or []
    return (", ".join(diagnosis.get("reasons", ())) or "ready") + (
        f" ({'; '.join(screens)})" if screens else "") + (
        f"; HUD {'present' if hud.get('pointer') else 'absent'}, activity {hud.get('activity')}, "
        f"state {state:#x}" if isinstance(state, int) else "")


def diagnose(process, cave, read_flags, *, allow_hudless=False):
    """Compact explanation of the same conservative readiness predicate."""
    from tools.cemu.menu_diagnostic import screens
    from tools.cemu.getdemo_state import snapshot

    ui = snapshot(process, cave.base)
    ui_summary = {name: ui.get(name) for name in (
        "manager", "screen", "name", "activity", "screen_active")}
    reasons = []
    if not ui.get("manager"):
        reasons.append("getdemo_manager_absent")
    if ui.get("screen"):
        reasons.append("getdemo_screen_present")
    if ui.get("name"):
        reasons.append("getdemo_name_retained")
    catalog = screens(process, cave.base)
    gameplay = presentation_gameplay_state(catalog)
    if not gameplay["strict_ready"] and not (allow_hudless and gameplay["hudless_ready"]):
        reasons.append("screen_catalog_not_gameplay")
    flags = read_flags()
    active = [name for name in PROTECTIONS if flags.get(name) != 0]
    reasons.extend("protection:" + name for name in active)
    return {
        "ready": not reasons,
        "reasons": reasons,
        "getdemo": ui_summary,
        "gameplay": gameplay,
        "unexpected_screens": unexpected_screens(catalog),
        "flags": flags,
    }

