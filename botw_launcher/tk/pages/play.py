"""The Play page: the profile to make at first launch,
then the seeds, then the session while it runs."""
from __future__ import annotations

from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, ttk

from botw_client.paths import DATA
from botw_client.version import VERSION

from ...core import output, profile, room_link, rooms, seeds, storage, updates, worlds
from .. import dialogs, events, theme
from ..context import TITLE, Context
from ..events import Signal
from ..widgets import (Button, LogView, StepBar, VerticalScroll, card, human_day, human_size, label, open_folder,
                       set_role)
from . import Page

JOB = "play"
STEPS = [(output.PACK, "Game pack"), (output.CEMU, "Cemu"), (output.ROOM, "Room"), (output.GAME, "Save linked")]
WAITING = {
    output.PACK: "Checking the seed's game pack...",
    output.CEMU: "Cemu is starting. Load your save or start a new game.",
    output.ROOM: "Connected to the room. Waiting for a save to be loaded in the game.",
    output.GAME: "Playing. Close Cemu to end the session.",
    output.OFFLINE: "The room cannot be reached: checks are kept and sent when it answers again.",
    output.CLOSING: "Cemu closed: ending the session...",
}
WAITING_SILENCE = 8000      # ms: the client says items wait every 5 s (botw_client/runtime.py)
SEED_FILES = [("Breath of the Wild slot file or seed", seeds.SEED_FILE_PATTERNS), ("All files", "*")]
CEMU_FILES = [("Cemu", "Cemu.exe")] if sys.platform == "win32" else [("Cemu", "Cemu* cemu*"), ("All files", "*")]


class PlayPage(Page):
    """Holds the three views; only the one of the moment is shown."""

    def __init__(self, parent: tk.Misc, context: Context):
        tk.Frame.__init__(self, parent, bg=theme.WINDOW)
        self.context = context
        self.setup = SetupView(self, context)
        self.seeds = SeedsView(self, context)
        self.session = SessionView(self, context)
        for view in (self.setup, self.seeds, self.session):
            view.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.setup.created.connect(self.shown)
        self.seeds.play_requested.connect(self.play)
        self.session.left.connect(self.shown)
        self.session.again.connect(self.play_again)
        self._last: tuple[seeds.PreparedSeed, rooms.Room, str] | None = None
        self._pending_file: Path | None = None
        self._wanted_seed = context.options.seed
        self.view: Page = self.setup

    def _show(self, view: Page) -> None:
        self.view = view
        view.tkraise()

    def shown(self) -> None:
        if self.context.jobs.busy and self.context.jobs.name == JOB:
            self._show(self.session)
        elif not profile.exists():
            self._show(self.setup)
        else:
            self._show(self.seeds)
            wanted, self._wanted_seed = self._wanted_seed, ""
            self.seeds.refresh(select=wanted)
            if self._pending_file is not None:
                file, self._pending_file = self._pending_file, None
                self.seeds.add_file(file)

    def add_file(self, path: Path) -> None:
        self._pending_file = path
        self.shown()

    def play_again(self) -> None:
        if self._last is None or self.context.jobs.busy:
            return
        last, room, password = self._last
        seed = seeds.read(last.name)
        if seed is None:
            self.shown()
        else:
            self.play(seed, room, password)

    def play(self, seed: seeds.PreparedSeed, room: rooms.Room, password: str) -> None:
        self._last = (seed, room, password)
        self.session.begin(seed, room)
        self._show(self.session)
        self.context.jobs.start(JOB, {
            "seed": seed.name,
            "room": None if room.hosted_here else room.address,
            "password": password or None,
            "open_to_network": room.open_to_network,
            "session_arguments": list(self.context.options.session_arguments),
        }, f"Starting {seed.slot}'s game")


# ---- first launch -----------------------------------------------------------

class SetupView(Page):
    def __init__(self, parent: tk.Misc, context: Context):
        super().__init__(parent, "Welcome")
        self.context = context
        self.created = Signal()
        self.found: profile.Found | None = None
        intro, body = card(self.body, "One step before playing")
        intro.pack(fill="x")
        label(body, "The Archipelago game runs in a Cemu profile of its own, copied once from your Cemu: Cemu "
                    "itself, the game's update, the DLC and your saves. Your own Cemu is only read, never "
                    "modified.", wrap=True).pack(fill="x")
        self.choose = Button(body, "Choose Cemu...", self.choose_cemu, "primary")
        self.choose.pack(anchor="w", pady=theme.px(12, 0))
        self.problem = label(body, role="error", wrap=True)
        self.result, result = card(self.body, "Found in your Cemu")
        self.facts = label(result, wrap=True)
        self.facts.pack(fill="x")
        self.space = label(result, wrap=True)
        self.space.pack(fill="x", pady=theme.px(8, 0))
        self.create = Button(result, "Create the profile", self.create_profile, "primary")
        self.create.pack(anchor="w", pady=theme.px(12, 0))

    def _problem(self, text: str) -> None:
        self.problem.configure(text=text)
        self.problem.pack(fill="x", pady=theme.px(10, 0))

    def choose_cemu(self) -> None:
        chosen = filedialog.askopenfilename(title="Where is Cemu?", filetypes=CEMU_FILES, parent=self)
        if not chosen:
            return
        try:
            self.found = profile.detect(Path(chosen))
        except (profile.CemuInstallError, OSError) as exc:
            self.found = None
            self.result.pack_forget()
            self._problem(str(exc))
            return
        from tools.cemu_install import UPDATE_VERSION
        self.problem.pack_forget()
        self.choose.set(kind="secondary")
        self.facts.configure(text=f"Breath of the Wild: {self.found.game}\nUpdate v{UPDATE_VERSION}: "
                                  f"{self.found.update}\nDLC: {self.found.dlc}")
        free = storage.free_space(DATA)
        enough = free >= profile.EXPECTED_SIZE
        self.space.configure(text=f"The profile takes about {human_size(profile.EXPECTED_SIZE)} in {DATA} "
                                  f"({human_size(free)} free there)."
                                  + ("" if enough else " That is not enough room: free some first."))
        set_role(self.space, "" if enough else "error")
        self.create.set(enabled=enough)
        self.result.pack(fill="x", pady=theme.px(16, 0))

    def create_profile(self) -> None:
        if self.found is None or self.context.jobs.busy:
            return
        self.create.set(enabled=False)
        self.context.jobs.start("create-profile", {"executable": str(self.found.executable)},
                                "Creating the game profile (a few minutes)", self._created)

    def _created(self, succeeded: bool, payload) -> None:
        self.create.set(enabled=True)
        if succeeded:
            self.created.emit()
        else:
            self._problem(f"The profile was not created: {payload}")


# ---- the seeds --------------------------------------------------------------

class _SeedRow(tk.Frame):
    """A seed in the list: the player's name and the world's version (orange
    when this version cannot play it), then the seed and its last day."""

    def __init__(self, parent: tk.Misc, seed: seeds.PreparedSeed, select):
        super().__init__(parent, bg=theme.WINDOW, cursor="hand2")
        self.seed, self.selected, self.hover = seed, False, False
        self.columnconfigure(0, weight=1)
        parts = [label(self, seed.slot, "heading"),
                 label(self, seed.world_version or "?", "small" if seed.playable else "warning"),
                 label(self, seed.name, "small"),
                 label(self, seed.last_used.astimezone().strftime("%d/%m/%y"), "small")]
        parts[1].configure(font=theme.FONTS["small"])
        parts[0].grid(row=0, column=0, sticky="w", padx=theme.px(12, 6), pady=theme.px(7, 0))
        parts[1].grid(row=0, column=1, sticky="e", padx=theme.px(0, 12), pady=theme.px(7, 0))
        parts[2].grid(row=1, column=0, sticky="w", padx=theme.px(12, 6), pady=theme.px(0, 7))
        parts[3].grid(row=1, column=1, sticky="e", padx=theme.px(0, 12), pady=theme.px(0, 7))
        self.parts = parts
        for widget in (self, *parts):
            widget.bind("<Button-1>", lambda _e: select(self.seed.name))
            widget.bind("<Enter>", lambda _e: self._hovered(True))
            widget.bind("<Leave>", lambda _e: self._hovered(False))

    def _hovered(self, hover: bool) -> None:
        self.hover = hover
        self.paint()

    def paint(self) -> None:
        colour = theme.SELECTED if self.selected else theme.HOVER if self.hover else theme.WINDOW
        for widget in (self, *self.parts):
            widget.configure(bg=colour)


class SeedsView(Page):
    def __init__(self, parent: tk.Misc, context: Context):
        super().__init__(parent, "Seeds")
        self.context = context
        self.play_requested = Signal()      # the seed, its room, the room's password
        self.selected: seeds.PreparedSeed | None = None
        self.offered: list[str] = []
        self.rows: dict[str, _SeedRow] = {}
        self.add_button = Button(self.header, "Add a seed...", self.choose_file)
        self.add_button.pack(side="right")
        self.link_button = Button(self.header, "Add from a room link...", self.add_from_room)
        self.link_button.pack(side="right", padx=theme.px(0, 8))
        self.empty = label(self.body, "No seed yet.\n\nAdd it from its room's link, or add your slot file "
                                      "(.apbotw) downloaded from the room's page, or the seed's zip, with the "
                                      "buttons above.", "muted", wrap=True)
        self.content = tk.Frame(self.body, bg=theme.WINDOW)
        self.list = VerticalScroll(self.content, bg=theme.WINDOW)
        self.list.configure(width=round(260 * self.winfo_fpixels("1i") / 96))
        self.list.pack_propagate(False)
        self.list.pack(side="left", fill="y", padx=theme.px(0, 18))
        self._detail(self.content).pack(side="left", fill="both", expand=True)
        context.jobs.started.connect(lambda *_: self._update_actions())
        context.jobs.finished.connect(lambda *_: self._update_actions())
        context.seeds_changed.connect(self.refresh)
        context.releases.changed.connect(self._releases_read)

    def _detail(self, parent: tk.Misc) -> tk.Frame:
        outer, body = card(parent, padding=20)
        scroll = VerticalScroll(body, bg=theme.SURFACE)
        scroll.pack(fill="both", expand=True)
        top = scroll.inner
        self.name = label(top, role="title")
        self.name.pack(fill="x")
        self.facts = label(top, role="muted", wrap=True)
        self.facts.pack(fill="x", pady=theme.px(2, 0))
        self.warning = label(top, role="warning", wrap=True)
        self.where = tk.Frame(top, bg=theme.SURFACE)
        self.where.pack(fill="x", pady=theme.px(16, 0))
        label(self.where, "Where to play", "heading").pack(anchor="w", pady=theme.px(0, 4))
        self.mode = tk.StringVar(value="join")
        self.mode.trace_add("write", lambda *_: self._update_actions())
        self.join = ttk.Radiobutton(self.where, text="Join a room", value="join", variable=self.mode)
        self.join.pack(anchor="w")
        fields = tk.Frame(self.where, bg=theme.SURFACE)
        fields.pack(fill="x", padx=theme.px(26, 0), pady=theme.px(2, 6))
        fields.columnconfigure(1, weight=1)
        label(fields, "Address", "muted").grid(row=0, column=0, sticky="w", padx=theme.px(0, 10))
        self.address = ttk.Entry(fields)
        self.address.grid(row=0, column=1, sticky="ew", pady=theme.px(3))
        label(fields, "Password", "muted").grid(row=1, column=0, sticky="w", padx=theme.px(0, 10))
        self.password = ttk.Entry(fields, show="•")
        self.password.grid(row=1, column=1, sticky="ew", pady=theme.px(3))
        for entry in (self.address, self.password):
            entry.bind("<Return>", lambda _e: self.play())
        self.host = ttk.Radiobutton(self.where, text="Host the seed on this computer", value="host",
                                    variable=self.mode)
        self.host.pack(anchor="w")
        self.open_to_network = tk.BooleanVar()
        self.open = ttk.Checkbutton(self.where, text="Let the other players of the seed join over my network",
                                    variable=self.open_to_network)
        self.open.pack(anchor="w", padx=theme.px(26, 0))
        self.problem = label(top, role="error", wrap=True)
        actions = tk.Frame(top, bg=theme.SURFACE)
        actions.pack(fill="x", pady=theme.px(16, 0))
        self.actions = actions
        self.play_button = Button(actions, "Play", self.play, "primary")
        self.play_button.pack(side="left")
        self.other_button = Button(actions, "", self.play_with_other)
        self.aids = label(actions, role="muted")
        self.aids.pack(side="left", padx=theme.px(12, 0))
        tk.Frame(body, bg=theme.BORDER, height=1).pack(fill="x", pady=theme.px(14, 12))
        bottom = tk.Frame(body, bg=theme.SURFACE)
        bottom.pack(fill="x")
        self.rebuild_button = Button(bottom, "Rebuild the game pack", self.rebuild)
        self.rebuild_button.pack(side="left")
        self.folder_button = Button(bottom, "Open its folder", lambda: open_folder(self.selected.folder))
        self.folder_button.pack(side="left", padx=theme.px(8, 0))
        self.delete_button = Button(bottom, "Delete...", self.delete, "danger")
        self.delete_button.pack(side="right")
        return outer

    # ---- the list -----------------------------------------------------------

    def refresh(self, select: str = "") -> None:
        wanted = select or (self.selected.name if self.selected else self.context.settings.last_seed)
        found = seeds.prepared()
        for row in self.rows.values():
            row.destroy()
        self.rows = {seed.name: _SeedRow(self.list.inner, seed, self.select) for seed in found}
        for row in self.rows.values():
            row.pack(fill="x", pady=theme.px(0, 2))
        if found:
            self.empty.pack_forget()
            self.content.pack(fill="both", expand=True)
            self.select(wanted if wanted in self.rows else found[0].name)
        else:
            self.content.pack_forget()
            self.empty.pack(fill="x", pady=theme.px(40))

    def step(self, delta: int) -> None:
        """The seed above (-1) or below (1) the one selected."""
        names = list(self.rows)
        if not names or self.context.jobs.busy:
            return
        at = names.index(self.selected.name) if self.selected and self.selected.name in names else 0
        chosen = names[max(0, min(len(names) - 1, at + delta))]
        if self.selected is None or chosen != self.selected.name:
            self.select(chosen)
            self.list.see(self.rows[chosen])

    def select(self, name: str) -> None:
        for row_name, row in self.rows.items():
            row.selected = row_name == name
            row.paint()
        self.selected = seed = seeds.read(name)
        if seed is None:
            return
        self.context.settings.last_seed = seed.name
        self.name.configure(text=seed.slot)
        world = f"world {seed.world_version}" if seed.world_version else "world version not recorded"
        self.facts.configure(text=f"Seed {seed.name}  ·  {world}  ·  last played {human_day(seed.last_played)}")
        newer = seeds.newer_world(seed.name)
        self.offered = ([] if seed.playable else
                        worlds.choices(seed.world_schema, seed.client_schema, seed.world_version,
                                       self.context.releases.known()))
        if not seed.playable:
            self.warning.configure(text=self._unplayable(seed))
        elif newer:
            self.warning.configure(text=f"This seed was generated with the world {newer}, newer than this "
                                        f"version ({VERSION}): if something is missing, update BOTW Archipelago.")
        if newer or not seed.playable:
            self.warning.pack(fill="x", pady=theme.px(10, 0), after=self.facts)
        else:
            self.warning.pack_forget()
        if seed.playable:
            self.where.pack(fill="x", pady=theme.px(16, 0), before=self.actions)
        else:
            self.where.pack_forget()
        if seed.playable:
            text = "Play"
        elif not self.offered:
            text = "Not playable"
        elif self.context.releases.is_update(self.offered[0]):
            text = f"Update to version {self.offered[0]}"
        else:
            text = f"Play with version {self.offered[0]}"
        self.play_button.set(text=text)
        if len(self.offered) > 1:
            self.other_button.set(text=f"Use version {self.offered[1]}")
            self.other_button.pack(side="left", padx=theme.px(8, 0), after=self.play_button)
        else:
            self.other_button.pack_forget()
        room = rooms.remembered(seed)
        hostable = rooms.can_host(seed)
        for widget in (self.host, self.open):
            if hostable:
                widget.pack(anchor="w", padx=theme.px(26, 0) if widget is self.open else 0)
            else:
                widget.pack_forget()
        self.address.delete(0, "end")
        self.address.insert(0, room.address)
        self.password.delete(0, "end")
        self.open_to_network.set(room.open_to_network)
        self.mode.set("host" if hostable and (room.hosted_here or not room.address) else "join")
        extra = self.context.options.session_arguments
        self.aids.configure(text=f"With: {' '.join(extra)}" if extra else "")
        self.problem.pack_forget()
        self._update_actions()

    def _unplayable(self, seed: seeds.PreparedSeed) -> str:
        this = f"This version ({VERSION})"
        made = f"version {seed.world_version}" if seed.world_version else "an unrecorded version"
        releases = self.context.releases
        if not self.offered and not releases.found:
            if releases.status:     # the last read failed: tried again from Settings, not in a loop
                return (f"{this} cannot play this seed, generated with {made}. {releases.status}. "
                        "Settings > Check now tries again.")
            if not releases.checking:
                releases.check()
            return f"{this} cannot play this seed, generated with {made}. Looking for the version that plays it..."
        if worlds.newer(seed.world_schema, seed.client_schema) and not self.offered:
            return f"{this} cannot play this seed, generated with {made}: update BOTW Archipelago."
        if not self.offered and None in releases.known().values():
            return (f"{this} cannot play this seed, generated with {made}. What some releases play could not "
                    "be read: try again later.")
        if not self.offered and worlds.apworld_era(seed.world_version):
            return (f"{this} cannot play this seed, generated with {made}. Archipelago runs one version of the "
                    "world at a time: generate the seed again with this one.")
        if not self.offered:
            return f"{this} cannot play this seed, generated with {made}, and no release does: generate it again."
        if releases.is_update(self.offered[0]):
            return (f"{this} cannot play this seed, generated with {made}. Version {self.offered[0]} can: it "
                    "replaces this one in Archipelago, which is then opened again.")
        newest = " (the newest of the seed's world, with the fixes made since)" if len(self.offered) > 1 else ""
        return (f"{this} cannot play this seed, generated with {made}. Version {self.offered[0]}{newest} can: "
                "it is installed the first time, then its launcher opens.")

    def _releases_read(self) -> None:
        if self.selected is not None and not self.selected.playable:
            self.select(self.selected.name)

    def _update_actions(self) -> None:
        idle = not self.context.jobs.busy
        seed = self.selected
        joining = self.mode.get() == "join"
        for entry in (self.address, self.password):
            entry.state(["!disabled"] if joining else ["disabled"])
        self.open.state(["disabled"] if joining else ["!disabled"])
        self.add_button.set(enabled=idle)
        self.play_button.set(enabled=idle and seed is not None and (seed.playable or bool(self.offered)))
        self.other_button.set(enabled=idle)
        self.rebuild_button.set(enabled=idle and seed is not None and seed.playable)
        self.delete_button.set(enabled=idle and seed is not None)

    # ---- actions ------------------------------------------------------------

    def play_with_other(self) -> None:
        if self.selected is not None and len(self.offered) > 1:
            self.context.releases.open_with(self.offered[1], ("--seed", self.selected.name))

    def play(self) -> None:
        seed = self.selected
        if seed is None or self.context.jobs.busy:
            return
        if not seed.playable:
            if self.offered:
                self.context.releases.open_with(self.offered[0], ("--seed", seed.name))
            return
        room = rooms.Room(hosted_here=self.mode.get() == "host", open_to_network=self.open_to_network.get())
        if not room.hosted_here:
            try:
                room.address = rooms.normalized(self.address.get())
            except ValueError as exc:
                self.problem.configure(text=str(exc))
                self.problem.pack(fill="x", pady=theme.px(10, 0), before=self.actions)
                self.address.focus_set()
                return
        self.problem.pack_forget()
        rooms.remember(seed, room)
        self.play_requested.emit(seed, room, self.password.get())

    def rebuild(self) -> None:
        seed = self.selected
        self.context.jobs.start("rebuild-seed", {"seed": seed.name},
                                f"Building the game pack of {seed.slot}'s seed", self._job_done)

    def _job_done(self, succeeded: bool, payload) -> None:
        if succeeded:
            self.context.seeds_changed.emit()
        else:
            dialogs.tell(self, "The game pack was not built", str(payload), "warning")

    def delete(self) -> None:
        seed = self.selected
        going = seeds.deletion(seed.name)
        what = "its folder and its game pack" if going.with_pack else "its folder"
        hosted = (" The progress of the game hosted on this computer goes with it."
                  if going.with_hosted_progress else "")
        if not dialogs.ask(
                self, f"Delete {seed.slot}'s seed?", f"Seed {seed.name}: this removes {what} "
                f"({human_size(going.size)}).{hosted}\n\nYour Breath of the Wild saves are not touched: they "
                "stay in the game profile.", yes="Delete", danger=True):
            return
        try:
            seeds.delete(seed.name)
        except (OSError, RuntimeError) as exc:
            dialogs.tell(self, "The seed was not deleted", str(exc), "warning")
        self.selected = None
        self.context.seeds_changed.emit()

    def choose_file(self) -> None:
        chosen = filedialog.askopenfilename(title="Your slot file (.apbotw) or the seed's zip",
                                            filetypes=SEED_FILES, parent=self)
        if chosen:
            self.add_file(Path(chosen))

    def add_from_room(self) -> None:
        """The slot file downloaded from the room's page, then added as a chosen one."""
        if self.context.jobs.busy:
            self.context.notice.emit("Wait for the current task to end, then add the seed.", [])
            return
        link = dialogs.ask_text(self, "Add a seed from its room", "Paste the link of the room's page, as your "
                                "browser shows it: https://archipelago.gg/room/...", yes="Add")
        if link:
            self._fetching(True)
            events.background(lambda: room_link.room_slots(link), self._room_found, self._room_failed)

    def _room_found(self, found: list[room_link.Slot]) -> None:
        slot = found[0]
        if len(found) > 1:
            names = [entry.player for entry in found]
            chosen = dialogs.choose(self, "Which player are you?", "This room has several Breath of the Wild "
                                    "players.", names)
            if chosen is None:
                self._fetching(False)
                return
            slot = found[names.index(chosen)]
        events.background(lambda: room_link.download(slot, updates.DOWNLOADS), self._room_downloaded,
                          self._room_failed)

    def _room_downloaded(self, path: Path) -> None:
        self._fetching(False)
        self.add_file(path)

    def _room_failed(self, error: Exception) -> None:
        self._fetching(False)
        dialogs.tell(self, "The seed was not added", str(error), "warning")

    def _fetching(self, fetching: bool) -> None:
        self.link_button.set(text="Opening the room..." if fetching else "Add from a room link...",
                             enabled=not fetching)

    def add_file(self, path: Path) -> None:
        if self.context.jobs.busy:
            self.context.notice.emit("Wait for the current task to end, then add the seed.", [])
            return
        try:
            file = seeds.inspect(path)
        except ValueError as exc:
            dialogs.tell(self, "This seed cannot be added", str(exc), "warning")
            return
        if file.unplayable:
            offered = worlds.choices(file.world_schema, file.client_schema, file.world_version,
                                     self.context.releases.known())
            if not offered:
                dialogs.tell(self, "This seed cannot be played", file.unplayable, "warning")
            else:
                self.context.releases.open_with(
                    offered[0], (str(file.path),), why=f"This version ({VERSION}) cannot play this seed, "
                                                       f"generated with version {file.world_version or '?'}.")
            return
        slot = file.players[0]
        if len(file.players) > 1:
            slot = dialogs.choose(self, "Which player are you?", "This seed has several Breath of the Wild "
                                  "players.", list(file.players))
            if slot is None:
                return
        self.context.jobs.start("prepare-seed", {"path": str(file.path), "slot": slot},
                                f"Preparing {slot}'s seed (about a minute)", self._prepared)

    def _prepared(self, succeeded: bool, payload) -> None:
        if succeeded:
            self.refresh(select=payload.get("seed", ""))
        else:
            dialogs.tell(self, "The seed was not prepared", str(payload), "warning")
            self.refresh()


# ---- the session ------------------------------------------------------------

class SessionView(Page):
    def __init__(self, parent: tk.Misc, context: Context):
        super().__init__(parent, "Session")
        self.context = context
        self.left, self.again = Signal(), Signal()
        self.session_folder: Path | None = None
        self.seed: seeds.PreparedSeed | None = None
        self.room: rooms.Room | None = None
        self.counts = {"check": 0, "item": 0}
        self.waiting, self._waiting_timer = 0, None
        self.linked = False
        self.where = label(self.body, role="muted")
        self.where.pack(fill="x")
        self.steps = StepBar(self.body, STEPS)
        self.steps.pack(anchor="w", pady=theme.px(12, 10))
        self.state = label(self.body, role="heading", wrap=True)
        self.state.pack(fill="x")
        self.counters = label(self.body, role="muted")
        self.counters.pack(fill="x", pady=theme.px(2, 10))
        actions = tk.Frame(self.body, bg=theme.WINDOW)
        actions.pack(side="bottom", fill="x", pady=theme.px(10, 0))
        self.again_button = Button(actions, "Play again", self.again.emit, "primary")
        self.back = Button(actions, "Back to the seeds", self.left.emit)
        self.folder_button = Button(actions, "Open the session's folder", lambda: open_folder(self.session_folder))
        command = tk.Frame(self.body, bg=theme.WINDOW)
        command.pack(side="bottom", fill="x", pady=theme.px(10, 0))
        self.command = ttk.Entry(command)
        self.command.pack(side="left", fill="x", expand=True, padx=theme.px(0, 8))
        self.command.bind("<Return>", lambda _e: self.send())
        self.send_button = Button(command, "Send", self.send, "primary")
        self.send_button.pack(side="left")
        search = tk.Frame(self.body, bg=theme.WINDOW)
        search.pack(fill="x", pady=theme.px(0, 6))
        self.found = label(search, role="muted", bg=theme.WINDOW)
        self.found.pack(side="right")
        self.search = ttk.Entry(search, width=28)
        self.search.pack(side="right", padx=theme.px(0, 8))
        label(search, "Search the log", "muted", bg=theme.WINDOW).pack(side="right", padx=theme.px(0, 8))
        self.search.bind("<KeyRelease>", self._search)
        self.search.bind("<Return>", lambda _e: self.log.step(-1))
        self.search.bind("<Shift-Return>", lambda _e: self.log.step(1))
        self.log = LogView(self.body)
        self.log.pack(fill="both", expand=True)
        self.hints = Signal()           # the slot's hints, each time the room changes them
        self._echoes: list[str] = []    # a message's lines, also printed as text by the client
        context.jobs.line.connect(self._line)
        context.jobs.event.connect(self._event)
        context.jobs.finished.connect(self._finished)

    def begin(self, seed: seeds.PreparedSeed, room: rooms.Room) -> None:
        self.seed, self.room, self._echoes = seed, room, []
        self.search.delete(0, "end")
        self._search()
        self.session_folder = None
        self.counts = {"check": 0, "item": 0}
        self._waiting(0)
        self.linked = False
        self.log.clear()
        self.steps.reset()
        place = "hosted on this computer" if room.hosted_here else room.address
        self.where.configure(text=f"{seed.slot}  ·  seed {seed.name}  ·  {place}")
        self._set_state(WAITING[output.PACK])
        self._show_counts()
        self._running(True)
        self._commands(False)

    def send(self) -> None:
        text = self.command.get().strip()
        if text and self.context.jobs.busy and self.context.jobs.name == JOB:
            self.context.jobs.send(text)
            self.log.add(f"> {text}")
            self.command.delete(0, "end")

    def can_ask(self) -> bool:
        """A command reaches the room: the session runs, and Cemu has started."""
        return self.context.jobs.busy and self.context.jobs.name == JOB and self.command.instate(["!disabled"])

    def ask_hint(self, location: bool, name: str) -> bool:
        """Ask the room for a hint of an item of this slot, or of a location of
        its world, as the console takes it (tools/play_session.py console):
        on a room, as the players type it in its chat."""
        if not self.can_ask():
            return False
        command = "hint_location" if location else "hint"
        text = f"/{command} {self.seed.slot} {name}" if self.room.hosted_here else f"/{command} {name}"
        self.context.jobs.send(text)
        self.log.add(f"> {text}")
        return True

    def _commands(self, enabled: bool) -> None:
        self.command.state(["!disabled"] if enabled else ["disabled"])
        self.send_button.set(enabled=enabled)

    def _running(self, running: bool) -> None:
        self._commands(running)
        for widget in (self.again_button, self.back, self.folder_button):
            widget.pack_forget()
        if not running:
            self.again_button.pack(side="left")
            self.back.pack(side="left", padx=theme.px(8, 0))
            if self.session_folder is not None:
                self.folder_button.pack(side="left", padx=theme.px(8, 0))

    def _set_state(self, text: str, role: str = "heading") -> None:
        self.state.configure(text=text)
        set_role(self.state, role)

    def _show_counts(self) -> None:
        text = (f"This session: {self.counts['check']} checks found, {self.counts['item']} items given in the "
                "game")
        if self.waiting:
            text += f"; {self.waiting} waiting for a moment the game can take them"
        self.counters.configure(text=text)

    def _waiting(self, count: int) -> None:
        """Items wait: said again every few seconds while they do, so a silence
        longer than WAITING_SILENCE means they were given."""
        self.waiting = count
        self._show_counts()
        if self._waiting_timer is not None:
            self.after_cancel(self._waiting_timer)
        self._waiting_timer = self.after(WAITING_SILENCE, self._waited) if count else None

    def _waited(self) -> None:
        self._waiting_timer = None
        self.waiting = 0
        self._show_counts()

    def _mine(self) -> bool:
        return self.context.jobs.name == JOB

    def _line(self, text: str) -> None:
        if not self._mine():
            return
        if self._echoes and output.untimed(text) == self._echoes[0]:
            self._echoes.pop(0)     # shown in colour already
            return
        self._echoes.clear()
        self.log.add(text)

    def _search(self, event=None) -> None:
        if event is not None and event.keysym in ("Return", "Shift_L", "Shift_R"):
            return
        needle = self.search.get()
        found = self.log.search(needle)
        self.found.configure(text="" if not needle else f"{found} found" if found else "not found")

    def _event(self, event: dict) -> None:
        if not self._mine():
            return
        if event["event"] == "count" and event.get("what") in self.counts:
            self.counts[event["what"]] += 1
            self._show_counts()
        elif event["event"] == "waiting":
            self._waiting(int(event.get("count", 0)))
        elif event["event"] == "message" and event.get("parts"):
            self.log.add_parts(event["parts"])
            self._echoes = "".join(str(part[0]) for part in event["parts"]).split("\n")
        elif event["event"] == "hints":
            self.hints.emit(event.get("hints") or [])
        elif event["event"] == "stage":
            self._stage(event.get("stage", ""))

    def _stage(self, stage: str) -> None:
        self.linked = self.linked or stage == output.GAME
        if stage in WAITING:
            self._set_state(WAITING[output.GAME if stage == output.ROOM and self.linked else stage])
        if stage == output.PACK:
            self.steps.set_state(output.PACK, "active")
        elif stage == output.CEMU:
            self.steps.set_state(output.PACK, "done")
            self.steps.set_state(output.CEMU, "done")
            self.steps.set_state(output.ROOM, "active")
            self._commands(True)
        elif stage == output.ROOM:
            self.steps.set_state(output.ROOM, "done")
        elif stage == output.OFFLINE:
            self.steps.set_state(output.ROOM, "problem")
        elif stage == output.GAME:
            self.steps.set_state(output.GAME, "done")
        elif stage == output.CLOSING:
            self.steps.stop()

    def _finished(self, name: str, succeeded: bool, payload) -> None:
        if name != JOB:
            return
        self._waiting(0)
        if succeeded:
            folder = payload.get("session", "")
            self.session_folder = Path(folder) if folder else None
            self._set_state("Session ended. Progress is saved.")
        else:
            self._set_state(f"The session stopped: {payload}", "error")
        self.steps.stop(failed=not succeeded)
        self._running(False)
