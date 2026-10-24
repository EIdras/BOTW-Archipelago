"""The versions of Breath of the Wild the pack is built for: what tells them apart.

The update v208 of the European (EUR), American (USA) and Japanese (JPN)
versions run the same U-King.rpx, and their update and DLC hold the same
resources once Yaz0 is undone and archives are opened, their languages apart:
the message archives (Pack/Bootup_<language>.pack), voices and fonts (measured,
18/10). Their files were compressed apart, so their bytes differ, and not by
version only: a player's European update held the American files byte for
byte, and its language archives compressed as the American ones (24/10).

The build checks every resource it reads against the SHA-256 of the European
file. data/region_hashes.json (written by tools/measure_region.py from each
version and the European one) gives, for another version, the hash of each such file holding the
same data, and pins its own language archives: vanilla_digest() names a file
by the European hash of its content, inputs() puts a version's language
archives in place of the European ones. A file of another distribution,
known by none of these hashes, is named by its content (content_digest()):
data/content_hashes.json gives the pinned hash of each pinned resource's
content. A text added in a language is its own when the build has one, else
its European counterpart's (localized()).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import hashlib
import json
from pathlib import Path

HASHES = Path(__file__).resolve().parents[1] / "data/region_hashes.json"
CONTENTS = Path(__file__).resolve().parents[1] / "data/content_hashes.json"


@dataclass(frozen=True)
class Region:
    key: str
    title: str                  # the low half of the title ids, as Cemu's folders name it
    name: str
    languages: tuple[str, ...]  # its message archives, Pack/Bootup_<language>.pack
    # Cemu's console languages (settings.xml console_language) the version has
    # texts for; any other one, as the game, falls back to its main language.
    console: dict[int, str] = field(default_factory=dict, hash=False)

    @property
    def main(self) -> str:
        """Its English, else its only language: that of the names sent to the
        other players (DeathLink), and the game's when Cemu's is not one of its own."""
        return next((language for language in self.languages if language.endswith("en")), self.languages[0])

    def title_id(self, kind: str = "00050000") -> str:
        """The title id of the game (or, with its kind, of its update or DLC)."""
        return (kind + self.title).upper()


EUR = Region("EUR", "101c9500", "European", ("EUde", "EUen", "EUes", "EUfr", "EUit", "EUnl", "EUru"),
             {1: "EUen", 2: "EUfr", 3: "EUde", 4: "EUit", 5: "EUes", 8: "EUnl", 10: "EUru"})
USA = Region("USA", "101c9400", "American", ("USen", "USes", "USfr"),
             {1: "USen", 2: "USfr", 5: "USes"})
JPN = Region("JPN", "101c9300", "Japanese", ("JPja",), {0: "JPja"})
# The order a Cemu holding several versions is read in.
REGIONS = (EUR, USA, JPN)


def by_key(key: str) -> Region:
    return next(region for region in REGIONS if region.key == key)


def by_title(title: str) -> Region | None:
    return next((region for region in REGIONS if region.title == title.lower()[-8:]), None)


def of_content(content: Path) -> Region:
    """The version of an update's content folder, by its main message archive."""
    for region in REGIONS:
        if (Path(content) / f"Pack/Bootup_{region.main}.pack").is_file():
            return region
    raise ValueError(f"not the update of a supported version of Breath of the Wild: {content}")


def european(language: str) -> str | None:
    """The European language whose texts a language takes (USfr: EUfr)."""
    counterpart = "EU" + language[2:]
    return counterpart if counterpart in EUR.languages else None


def localized(texts: dict[str, str], language: str) -> str:
    """The text of `language` in `texts` (by European language, and the others
    the build writes): its own, else its European counterpart's."""
    return texts[language] if language in texts else texts[european(language)]


@lru_cache(maxsize=None)
def _table() -> dict:
    return json.loads(HASHES.read_text(encoding="utf-8")) if HASHES.is_file() else {}


@lru_cache(maxsize=None)
def _equivalents() -> dict[str, str]:
    return {theirs: ours for entry in _table().values() for theirs, ours in entry["equivalents"].items()}


@lru_cache(maxsize=None)
def _contents() -> dict[str, str]:
    return json.loads(CONTENTS.read_text(encoding="utf-8")) if CONTENTS.is_file() else {}


@lru_cache(maxsize=None)
def _pinned() -> frozenset[str]:
    return frozenset(_contents().values())


def content_digest(data: bytes) -> str:
    """The hash of what a resource holds, however it was compressed: Yaz0
    undone, an archive by its members' names and contents."""
    import oead
    try:
        if data[:4] == b"Yaz0":
            data = bytes(oead.yaz0.decompress(data))
        if data[:4] == b"SARC":
            members = sorted((m.name, content_digest(bytes(m.data))) for m in oead.Sarc(data).get_files())
            return hashlib.sha256(json.dumps(members).encode()).hexdigest()
    except Exception:       # not what it looks like (oead's own errors): its bytes
        pass
    return hashlib.sha256(data).hexdigest()


_named: dict[str, str] = {}     # by a file's own hash: the build reads a file at each stage


def vanilla_digest(data: bytes) -> str:
    """The SHA-256 of `data`, or of the pinned file holding the same resource
    when `data` is another version's or another distribution's."""
    digest = hashlib.sha256(data).hexdigest()
    named = _equivalents().get(digest, digest)
    if named in _pinned() or data[:4] not in (b"Yaz0", b"SARC"):
        return named
    if digest not in _named:
        _named[digest] = _contents().get(content_digest(data), named)
    return _named[digest]


def inputs(hashes: dict[str, str], content: Path) -> dict[str, str]:
    """`hashes` (European resources the build reads, by path) for the version
    of `content`: its language archives in place of the European ones read
    (each by its own hash): those whose counterpart is read, and those with no
    counterpart (JPja) as soon as one is."""
    region = of_content(content)
    if region is EUR:
        return dict(hashes)
    pinned = _table().get(region.key, {}).get("languages", {})
    europe = {f"Pack/Bootup_{language}.pack": language for language in EUR.languages}
    read = {europe[name] for name in hashes if name in europe}
    out = {name: sha for name, sha in hashes.items() if name not in europe}
    for language in region.languages:
        counterpart = european(language)
        if counterpart in read or (counterpart is None and read):
            out[f"Pack/Bootup_{language}.pack"] = pinned[f"Pack/Bootup_{language}.pack"]
    return out
