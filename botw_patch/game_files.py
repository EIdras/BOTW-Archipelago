"""The game's files as Cemu shows them to the game.

A seed pack is built from the files the game will actually load: the update
(content/) and the DLC (aoc/0010/), unless a graphic pack replaces one, in
which case the replacing pack that Cemu lets win (highest fsPriority, then
the first one it loads; tools/player_packs.py) gives it. `packs` lists those
graphic pack folders, the winning one first; without any, the files are the
update's and the DLC's own.

Names are relative to content/ (Pack/Bootup.pack) or, for the DLC, to
aoc/0010/ (Map/MainField/A-1/A-1_Static.smubin).

What a pack replaces is accepted as it is, but for the event flows a seed
pack rewrites: one a graphic pack changes too is refused (ModConflict),
naming the pack. The update and the DLC themselves must stay the game's own:
checked() compares their copy with the expected hash, whatever replaces it.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path, PurePosixPath
from typing import Callable, Iterator, Sequence

# The members a seed pack rebuilds whole rather than adds to: another mod's
# changes to them would be lost, or break the rebuild.
REWRITTEN = (".bfevfl",)


class ModConflict(ValueError):
    pass


def dlc_reader(aoc: GameFiles | Path) -> Callable[[str], bytes]:
    """read(name) of the DLC's files: from the game's files, or a DLC folder (content/0010)."""
    if isinstance(aoc, GameFiles):
        return aoc.read_aoc
    return lambda name: (Path(aoc) / name).read_bytes()


def dlc_checked(aoc: GameFiles | Path, error: str = "unexpected DLC map") -> Callable[[str, str], bytes]:
    """checked(name, expected) of the DLC's files (GameFiles.checked_aoc), from
    the game's files or a DLC folder (content/0010)."""
    if isinstance(aoc, GameFiles):
        return lambda name, expected: aoc.checked_aoc(name, expected, error)

    def checked(name: str, expected: str) -> bytes:
        from .resources import vanilla_digest
        raw = (Path(aoc) / name).read_bytes()
        if vanilla_digest(raw) != expected:
            raise ValueError(f"{error}: {name}")
        return raw
    return checked


_ACTIVE: ContextVar[GameFiles | None] = ContextVar("botw_game_files", default=None)


def own_member(archive: str, member: str) -> bytes | None:
    """The update's own `member` of `archive` (unpacked) when a graphic pack
    gives the archive, while a build reads the game's files; else None. A pack
    may hold a smaller encoding of the same data (UKMM writes the quests in
    half the size): the size table already fits the game's own."""
    game = _ACTIVE.get()
    if game is None:
        return None
    try:
        if game.provider(archive) is None:
            return None
        return game._member(archive, member, True)
    except (ValueError, FileNotFoundError):
        return None


def guard(archive: str, member: str) -> None:
    """Called before a member of `archive` is transformed: refuses to rewrite a
    member a graphic pack changed, while a build reads the game's files
    (GameFiles.active())."""
    game = _ACTIVE.get()
    if game is not None:
        game.check_rewrite(archive, member)


class GameFiles:
    def __init__(self, content: Path, aoc: Path | None = None, packs: Sequence[Path] = ()):
        self.content = Path(content).resolve()      # the update's content/: the clean dump
        self.aoc = Path(aoc).resolve() if aoc is not None else None     # the DLC's content/0010/
        self.packs = tuple(Path(pack).resolve() for pack in packs)
        self._archives: dict[tuple[str, bool], object] = {}

    @classmethod
    def of(cls, content: GameFiles | Path, aoc: Path | None = None) -> GameFiles:
        """`content` itself, or the update folder it names (with the DLC `aoc`)."""
        return content if isinstance(content, GameFiles) else cls(content, aoc)

    def _roots(self, aoc: bool) -> list[tuple[Path | None, Path]]:
        """(pack, folder) to look into, the winning one first; pack None: the game's."""
        own = self.aoc if aoc else self.content
        if own is None:
            raise FileNotFoundError("no DLC folder (aoc/0010) for this build")
        inner = ("aoc", "0010") if aoc else ("content",)
        return [*((pack, pack.joinpath(*inner)) for pack in self.packs), (None, own)]

    @staticmethod
    def _parts(name: str) -> tuple[str, ...]:
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError("resource path escapes content root")
        return relative.parts

    def _locate(self, name: str, aoc: bool) -> tuple[Path | None, Path] | None:
        parts = self._parts(name)
        for pack, root in self._roots(aoc):
            path = root.joinpath(*parts)
            if path.is_file():
                return pack, path
        return None

    def original(self, name: str) -> bytes:
        """The update's own `name`, whatever pack replaces it."""
        return self._roots(False)[-1][1].joinpath(*self._parts(name)).read_bytes()

    def original_aoc(self, name: str) -> bytes:
        return self._roots(True)[-1][1].joinpath(*self._parts(name)).read_bytes()

    def checked(self, name: str, expected: str, error: str = "unexpected update resource") -> bytes:
        """`name` as the game loads it, once the update's own copy is the one
        `expected` (vanilla_digest) names: a pack may replace it, nothing may
        change the update."""
        from .resources import vanilla_digest
        if vanilla_digest(self.original(name)) != expected:
            raise ValueError(f"{error}: {name}")
        return self.read(name)

    def checked_aoc(self, name: str, expected: str, error: str = "unexpected DLC map") -> bytes:
        from .resources import vanilla_digest
        if vanilla_digest(self.original_aoc(name)) != expected:
            raise ValueError(f"{error}: {name}")
        return self.read_aoc(name)

    @contextmanager
    def active(self) -> Iterator[GameFiles]:
        """While it lasts, guard() checks the rewrites of a build against these files."""
        token = _ACTIVE.set(self)
        try:
            yield self
        finally:
            _ACTIVE.reset(token)

    def _member(self, archive: str, member: str, own: bool) -> bytes | None:
        import oead
        from .resources import unpack
        key = (archive, own)
        if key not in self._archives:
            raw = unpack(self.original(archive) if own else self.read(archive))
            self._archives[key] = (raw, oead.Sarc(raw))     # the Sarc reads into raw: keep both
        found = self._archives[key][1].get_file(member)
        return None if found is None else unpack(bytes(found.data))

    def check_rewrite(self, archive: str, member: str) -> None:
        """Refuse to rebuild `member` of `archive` when a pack gives the archive
        with that member changed (ModConflict, naming the pack)."""
        if not member.endswith(REWRITTEN):
            return
        try:
            pack = self.provider(archive)
        except ValueError:
            return
        if pack is None:
            return
        try:
            own = self._member(archive, member, True)
        except FileNotFoundError:
            own = None
        if self._member(archive, member, False) != own:
            raise self.conflict(pack, archive, member)

    @staticmethod
    def conflict(pack: Path, archive: str, member: str) -> ModConflict:
        return ModConflict(f"the graphic pack {pack.name} changes {member} in {archive}, which Archipelago "
                           "changes too: turn that mod off for the Archipelago game")

    def read(self, name: str) -> bytes:
        found = self._locate(name, False)
        if found is None:
            raise FileNotFoundError(f"no {name} in the game's files")
        return found[1].read_bytes()

    def exists(self, name: str) -> bool:
        return self._locate(name, False) is not None

    def provider(self, name: str) -> Path | None:
        """The graphic pack that gives `name`, or None (the game's own)."""
        found = self._locate(name, False)
        return found[0] if found is not None else None

    def names(self, folder: str, pattern: str) -> list[str]:
        """The files of `folder` matching `pattern` in any layer, as names,
        ordered as the paths of one folder are."""
        found = set()
        for _pack, root in self._roots(False):
            directory = root / folder
            if directory.is_dir():
                found |= {f"{folder}/{path.name}" for path in directory.glob(pattern) if path.is_file()}
        return sorted(found, key=Path)

    def read_aoc(self, name: str) -> bytes:
        found = self._locate(name, True)
        if found is None:
            raise FileNotFoundError(f"no {name} in the DLC's files")
        return found[1].read_bytes()

    def provider_aoc(self, name: str) -> Path | None:
        found = self._locate(name, True)
        return found[0] if found is not None else None
