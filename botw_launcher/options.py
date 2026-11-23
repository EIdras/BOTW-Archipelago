"""The launcher's command line."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Options:
    """The launcher's command line."""
    file: Path | None = None            # a slot file or a seed's zip to add
    seed: str = ""                      # the prepared seed to select
    # Arguments this launcher does not know go to the play session as they
    # are: the test aids of a source checkout (tools/play_session.py).
    session_arguments: tuple[str, ...] = ()
    arguments: tuple[str, ...] = field(default=(), repr=False)

    @classmethod
    def parse(cls, arguments: list[str]) -> "Options":
        """The file comes first, as a file dropped on the launcher does. Read by
        hand: a parser would take the value of an option it does not know
        (--speed 3) for the file."""
        rest = list(arguments)
        file = Path(rest.pop(0).strip('"')) if rest and not rest[0].startswith("-") else None
        seed = ""
        if "--seed" in rest[:-1]:
            at = rest.index("--seed")
            seed = rest[at + 1]
            del rest[at:at + 2]
        return cls(file, seed, tuple(rest), tuple(arguments))
