"""The game's files as Cemu shows them to the game.

A seed pack is built from the files the game will actually load: the update
(content/) and the DLC (aoc/0010/), unless a graphic pack replaces one, in
which case the replacing pack that Cemu lets win (highest fsPriority, then
the first one it loads; tools/player_packs.py) gives it. `packs` lists those
graphic pack folders, the winning one first; without any, the files are the
update's and the DLC's own.

Names are relative to content/ (Pack/Bootup.pack) or, for the DLC, to
aoc/0010/ (Map/MainField/A-1/A-1_Static.smubin).
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Callable, Sequence


def dlc_reader(aoc: GameFiles | Path) -> Callable[[str], bytes]:
    """read(name) of the DLC's files: from the game's files, or a DLC folder (content/0010)."""
    if isinstance(aoc, GameFiles):
        return aoc.read_aoc
    return lambda name: (Path(aoc) / name).read_bytes()


class GameFiles:
    def __init__(self, content: Path, aoc: Path | None = None, packs: Sequence[Path] = ()):
        self.content = Path(content).resolve()      # the update's content/: the clean dump
        self.aoc = Path(aoc).resolve() if aoc is not None else None     # the DLC's content/0010/
        self.packs = tuple(Path(pack).resolve() for pack in packs)

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

    def _locate(self, name: str, aoc: bool) -> tuple[Path | None, Path] | None:
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError("resource path escapes content root")
        for pack, root in self._roots(aoc):
            path = root.joinpath(*relative.parts)
            if path.is_file():
                return pack, path
        return None

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
