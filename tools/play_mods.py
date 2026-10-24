"""The player's own mods in the Archipelago game, and the seed pack built over them.

The play profile runs the Breath of the Wild graphic packs the player's Cemu
runs (tools/player_packs.py), copied into it, but those that patch the code a
seed pack needs or replace the game's executable. The seed pack is built over
the copies holding game files (botw_patch/game_files.py) and wins the files
it shares with them: Linkle's TitleBG.pack, for one, becomes the seed pack's,
made from Linkle's.

Mods that add to the game take memory, and Archipelago adds its own: with
mods holding game files, the game may lack memory and never finish loading,
without any error (measured with the Linkle mods, 24/10). So the Archipelago
game then runs Extended Memory, of Cemu's community packs, when the player's
Cemu has it installed; it says so, or how to install it. The seed pack's
code follows no pointer past the end of the game's main memory: it is built
for the end the packs give it (tools/cemu/guest.py).

A mod whose change the seed pack cannot build on (an event flow both rewrite:
ModConflict) is left out of the Archipelago game, by name, and the seed pack
built again without it. The player's Cemu and its packs are only read.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botw_patch.game_files import ModConflict  # noqa: E402
from tools import cemu_profile, player_packs  # noqa: E402
from tools.cemu import guest  # noqa: E402

MEMORY_ADDED = ("{name} is enabled in the Archipelago game: with your mods, the game needs more memory "
                "than it has, and would never finish loading.")
MEMORY_MISSING = ("Your mods may need more memory than the game has: if the game never finishes loading, "
                  "download Cemu's community graphic packs (Options > Graphic packs > Download latest "
                  "community graphic packs), then launch again: the Archipelago game enables their "
                  "Extended Memory with your mods.")


@dataclass
class Mods:
    found: list[player_packs.PlayerPack]            # the packs the player's Cemu runs
    left: dict[str, str]                            # entry -> why the Archipelago game runs it not
    added: list[player_packs.PlayerPack] = field(default_factory=list)  # run for the Archipelago game
    entries: list[dict] = field(default_factory=list)   # the copies to enable (player_packs.mirror)
    layers: list[dict] = field(default_factory=list)    # those a seed pack is built over

    @property
    def kept(self) -> list[player_packs.PlayerPack]:
        """The packs the Archipelago game runs, in the order Cemu loads them."""
        return sorted([pack for pack in self.found if pack.entry not in self.left] + self.added,
                      key=lambda pack: pack.order)

    @property
    def mem2_end(self) -> int:
        """Where the game's main memory ends with them (tools/cemu/guest.py)."""
        return player_packs.mem2_end(self.kept)


def prepare(say=print) -> Mods:
    """Read the player's packs and copy those the play profile runs (Cemu must be closed)."""
    cemu_profile.check_isolated()
    try:
        every = player_packs.installed(cemu_profile.source_user_data(), cemu_profile.region().title)
    except (OSError, KeyError, ValueError) as exc:
        say(f"Your Cemu's graphic packs could not be read: {exc}")
        every = []
    patched = player_packs.our_addresses()
    found = [pack for pack in every if pack.enabled]
    _kept, left = player_packs.carried(found, patched)
    mods = Mods(found, left)
    if any(pack.content or pack.aoc for pack in mods.kept) and mods.mem2_end == guest.MEM2_END:
        memory = player_packs.memory_pack(every)
        if memory is not None and not memory.patched & patched:
            mods.added.append(memory)
            say(MEMORY_ADDED.format(name=memory.virtual_path or memory.name))
        else:
            say(MEMORY_MISSING)
    _copy(mods)
    return mods


def _copy(mods: Mods) -> None:
    graphic_packs = cemu_profile.PORTABLE / "graphicPacks"
    mods.entries = player_packs.mirror(mods.kept, graphic_packs)
    mods.layers = player_packs.layers(mods.entries, graphic_packs)


def leave_out(mods: Mods, conflict: ModConflict, say=print) -> player_packs.PlayerPack:
    """Leave the pack a conflict names out of the Archipelago game (its copy goes), and say so."""
    by_copy = {(cemu_profile.PORTABLE / entry["entry"]).parent.resolve(): entry["source"]
               for entry in mods.entries}
    source = by_copy.get(Path(conflict.pack).resolve()) if conflict.pack is not None else None
    pack = next((pack for pack in mods.found if pack.entry == source), None)
    if pack is None:
        raise conflict
    mods.left[pack.entry] = f"it changes {conflict.member}, which the Archipelago pack changes too"
    _copy(mods)
    say(f"{pack.virtual_path or pack.name} is left out of the Archipelago game: {mods.left[pack.entry]}."
        + (" It holds every mod UKMM manages." if "UKMM" in pack.entry else ""))
    return pack


def fresh_pack(folder: Path, mods: Mods, say=print) -> Path:
    """The seed's pack, built again when the project's sources, the mods under
    it or the game's memory changed; a mod it cannot be built over is left
    out, named."""
    from tools.play_pack import outdated, selected_pack
    from tools.play_seed import refresh
    try:
        stale = outdated(selected_pack(folder), mods.layers, mods.mem2_end)
    except (OSError, ValueError, RuntimeError, KeyError):
        stale = ["(no pack)"]
    if not stale:
        return selected_pack(folder)
    say(f"Building the game pack of seed {folder.name} again (about a minute): changed since: "
        f"{', '.join(stale[:3])}{'...' if len(stale) > 3 else ''}.")
    while True:         # each conflict leaves one pack out
        try:
            return refresh(folder, mods.layers, mods.mem2_end)
        except ModConflict as conflict:
            leave_out(mods, conflict, say)
