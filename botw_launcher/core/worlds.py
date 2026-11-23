"""Which versions of the project play a seed.

Since 0.4.0 a release states the seeds it plays in its release.json
(botw_client/compatibility.py): the launcher reads it on disk for an installed
version, from the first bytes of its zip for a published one (core/updates.py),
and from its own code for itself. The releases before say nothing: a table
stands in for them, frozen, the world schema each played from its first
version up to the next one's.
"""
from __future__ import annotations

from botw_client import compatibility
from botw_client.version import parse

DECLARED_SINCE = "0.4.0"
LEGACY = {4: "0.1.0", 5: "0.3.0"}       # never changes: the later releases state it
# The first release that is botw.apworld alone (core/updates.py): from it on,
# Archipelago runs one version of the world, and an older one is not installed beside.
APWORLD_SINCE = "0.4.0"


def apworld_era(version: str) -> bool:
    """A seed generated with a version from APWORLD_SINCE on."""
    try:
        return bool(version) and parse(version) >= parse(APWORLD_SINCE)
    except ValueError:
        return False


def legacy(version: str) -> dict | None:
    """What a release from before DECLARED_SINCE plays, by the table."""
    if parse(version) >= parse(DECLARED_SINCE):
        return None
    schemas = [schema for schema, first in LEGACY.items() if parse(first) <= parse(version)]
    return {"world_schemas": [max(schemas)]} if schemas else None


def statement(version: str, declared: dict | None) -> dict | None:
    """What a version plays: what it states, else the table's; None when unknown
    (a later release whose zip could not be read)."""
    return declared if isinstance(declared, dict) else legacy(version)


def known(releases, installed) -> dict[str, dict | None]:
    """What each version plays, of the releases read (core/updates.py Release)
    and the versions installed (versions.Installed): None when not known."""
    found = {release.version: statement(release.version, release.plays) for release in releases}
    for one in installed:
        found[one.version] = statement(one.version, one.plays) or found.get(one.version)
    return found


def newer(world_schema: int | None, client_schema: int | None = None) -> bool:
    """A seed of a world newer than this version's, or of a newer client schema:
    only a later release plays it."""
    said = compatibility.statement()
    return ((world_schema is not None and world_schema > max(said["world_schemas"]))
            or (client_schema is not None and client_schema > max(said["client_schemas"])))


def choices(world_schema: int | None, client_schema: int | None, made_with: str,
            known: dict[str, dict | None]) -> list[str]:
    """The versions to offer for a seed this version cannot play, the best
    first: the newest that plays it (it has the fixes made since), then the
    one that generated it, which the player may prefer to keep.
    `known`: what each version installed or released plays (statement)."""
    playing = sorted((version for version, said in known.items()
                      if said is not None and compatibility.plays(said, world_schema, client_schema)),
                     key=parse, reverse=True)
    offered = playing[:1]
    if made_with in playing and made_with not in offered:
        offered.append(made_with)
    return offered
