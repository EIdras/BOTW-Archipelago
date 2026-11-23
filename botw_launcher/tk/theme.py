"""The window's look: one dark scheme, like the Archipelago clients', set on
tk's own widgets and on ttk's "clam" theme (the native one ignores colours).
Every colour and font of the window is here."""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font as tkfont, ttk

WINDOW = "#12151c"
SIDEBAR = "#0d1016"
SURFACE = "#191e28"
FIELD = "#202634"
BORDER = "#2a3140"
HOVER = "#232a38"
SELECTED = "#22324a"
TEXT = "#e6e9ef"
MUTED = "#8b94a6"
ACCENT = "#2f6a91"
ACCENT_HOVER = "#3a7dab"
FOCUS = "#8fc3e8"       # the outline of what has the keyboard's focus
SECONDARY = "#272e3c"
SECONDARY_HOVER = "#313a4b"
DANGER = "#a8403f"
DISABLED = "#1e232d"
DISABLED_TEXT = "#5c6475"
OK, WARNING, ERROR = "#3fb27a", "#e0a53a", "#e06060"

FAMILY = "Segoe UI" if sys.platform == "win32" else "TkDefaultFont"
FONTS = {"body": (FAMILY, 10), "small": (FAMILY, 8), "heading": (FAMILY, 11, "bold"),
         "title": (FAMILY, 17, "bold"), "brand": (FAMILY, 13, "bold"), "button": (FAMILY, 10),
         "mono": ("Consolas" if sys.platform == "win32" else "TkFixedFont", 9)}
# The colour of a label's text, by its role.
ROLES = {"": TEXT, "muted": MUTED, "heading": TEXT, "title": TEXT, "warning": WARNING, "error": ERROR,
         "ok": OK, "small": MUTED}

# The parts of a room's message, in the colours of Archipelago's own text client
# (made for a dark background): players, locations, entrances, and items by kind.
PARTS = {"me": "#ee00ee", "player": "#fafad2", "location_id": "#00ff7f", "entrance_name": "#6495ed"}
ITEMS = {"progression": "#af99ef", "useful": "#6d8be8", "trap": "#fa8072", "filler": "#00eeee"}
FOUND = "#5a4a14"           # a search's match in a log
FOUND_CURRENT = "#8a6d12"   # the match shown


def item_kind(flags: int) -> str:
    """An item's kind from its flags (Archipelago's ItemClassification)."""
    return "progression" if flags & 1 else "useful" if flags & 2 else "trap" if flags & 4 else "filler"


def part_colour(kind: str, flags: int = 0) -> str | None:
    """The colour of a message's part, None for plain text."""
    return ITEMS[item_kind(flags)] if kind == "item_id" else PARTS.get(kind)


# Pixels per pixel of a 96 dpi screen: margins and drawn sizes follow the screen's
# scale, as the fonts (in points) do. Set by apply(), once the process is DPI aware.
SCALE = 1.0


def px(*values: float):
    """Pixels at the screen's scale: one value, or a tuple of them (padx=px(8, 0))."""
    scaled = tuple(round(value * SCALE) for value in values)
    return scaled[0] if len(scaled) == 1 else scaled


def apply(root: tk.Tk) -> None:
    global SCALE
    SCALE = root.winfo_fpixels("1i") / 96
    root.configure(background=WINDOW)
    tkfont.nametofont("TkDefaultFont").configure(family=FAMILY, size=10)
    root.option_add("*Font", FONTS["body"])
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=SURFACE, foreground=TEXT, fieldbackground=FIELD, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER, troughcolor=WINDOW, focuscolor=ACCENT,
                    selectbackground=ACCENT, selectforeground=TEXT, insertcolor=TEXT, font=FONTS["body"])
    style.configure("TEntry", padding=px(8, 6), fieldbackground=FIELD, foreground=TEXT, insertcolor=TEXT)
    style.map("TEntry", fieldbackground=[("disabled", DISABLED)], foreground=[("disabled", DISABLED_TEXT)],
              bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)])
    style.configure("TCombobox", padding=px(8, 5), arrowcolor=TEXT, fieldbackground=FIELD, foreground=TEXT)
    style.map("TCombobox", fieldbackground=[("readonly", FIELD)], selectbackground=[("readonly", FIELD)],
              selectforeground=[("readonly", TEXT)])
    root.option_add("*TCombobox*Listbox.background", FIELD)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    for kind in ("TRadiobutton", "TCheckbutton"):
        style.configure(kind, background=SURFACE, foreground=TEXT, indicatorbackground=FIELD,
                        indicatorforeground=TEXT, indicatorsize=px(15), indicatormargin=px(0, 0, 9, 0),
                        upperbordercolor=BORDER, lowerbordercolor=BORDER, padding=px(0, 4))
        style.map(kind, background=[("active", SURFACE)], foreground=[("disabled", DISABLED_TEXT)],
                  indicatorbackground=[("selected", ACCENT), ("disabled", DISABLED)])
        # The same, on a page's background rather than a card's.
        style.configure(f"Page.{kind}", background=WINDOW)
        style.map(f"Page.{kind}", background=[("active", WINDOW)])
    style.configure("Vertical.TScrollbar", background=SECONDARY, troughcolor=SURFACE, bordercolor=SURFACE,
                    arrowcolor=MUTED, gripcount=0, relief="flat")
    style.map("Vertical.TScrollbar", background=[("active", SECONDARY_HOVER)])
    style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=FIELD, bordercolor=FIELD,
                    lightcolor=ACCENT, darkcolor=ACCENT, thickness=px(6))
    style.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=TEXT, bordercolor=BORDER,
                    rowheight=px(26), font=FONTS["body"], borderwidth=0)
    style.map("Treeview", background=[("selected", SELECTED)], foreground=[("selected", TEXT)])
    style.configure("Treeview.Heading", background=SURFACE, foreground=MUTED, relief="flat", font=FONTS["body"],
                    padding=px(6, 5), borderwidth=0)
    style.map("Treeview.Heading", background=[("active", HOVER)])


def dark_title_bar(window: tk.Misc) -> None:
    """Windows draws the title bar: asked to draw it dark, as the window."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        window.update_idletasks()
        handle = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1)
        for attribute in (20, 19):      # DWMWA_USE_IMMERSIVE_DARK_MODE, then its name before Windows 10 20H1
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(handle, attribute, ctypes.byref(value), 4) == 0:
                break
    except (AttributeError, OSError):
        pass
