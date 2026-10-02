"""The GameData flag table, {hash: [type, name]}, read from the player's own game.

It comes from GameData/gamedata.ssarc in the update's Pack/Bootup.pack (one
BYML per type, each entry with its DataName and HashValue). Nothing of it is in
the repository: tools/play_seed.py writes it to .build/gamedata.json from the
--content it is given, and a missing table is read from the default Cemu
update when it is there.
"""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLE = ROOT / ".build" / "gamedata.json"
DEFAULT_CONTENT = (Path.home() / "AppData/Roaming/Cemu/mlc01/usr/title"
                   / "0005000e/101c9500/content")
BOOTUP = "Pack/Bootup.pack"
GAMEDATA = "GameData/gamedata.ssarc"


class GameDataTableMissing(RuntimeError):
    pass


def extract(bootup: bytes) -> dict[str, list[str]]:
    """{signed hash as text: [type, name]} of every flag of a Bootup.pack."""
    import oead
    from botw_patch.resources import unpack
    archive = oead.Sarc(unpack(bytes(oead.Sarc(unpack(bootup)).get_file(GAMEDATA).data)))
    table = {}
    for member in archive.get_files():
        for kind, entries in oead.byml.from_binary(bytes(member.data)).items():
            for entry in entries:
                table[int(entry["HashValue"])] = [kind.removesuffix("_data"),
                                                  str(entry["DataName"])]
    if not table:
        raise ValueError(f"{GAMEDATA} holds no flag")
    return {str(key): table[key] for key in sorted(table)}


def build(content: Path, path: Path = TABLE) -> Path:
    """Write the table of the update at `content` to `path`."""
    table = extract((Path(content) / BOOTUP).read_bytes())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(table, ensure_ascii=False) + "\n", encoding="utf-8")
    load.cache_clear()
    return path


def available(path: Path = TABLE) -> bool:
    return path.is_file() or (DEFAULT_CONTENT / BOOTUP).is_file()


@lru_cache(maxsize=None)
def load(path: Path = TABLE) -> dict[str, list[str]]:
    """The table, built from the default Cemu update the first time if needed."""
    if not path.is_file():
        if not (DEFAULT_CONTENT / BOOTUP).is_file():
            raise GameDataTableMissing(
                f"{path} is missing: build the seed's pack with tools/play_seed.py "
                "--content <update/content>, which reads it from your game")
        build(DEFAULT_CONTENT, path)
    return json.loads(path.read_text(encoding="utf-8"))
