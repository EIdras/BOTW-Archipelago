"""Cutscenes skipped with + alone, from a first game on (the world's cutscene_skip option).

Native, a patch group after the injection's. The game lets a cutscene be skipped
(X opens the prompt, + confirms) once its skip controller (0x02DCD430, states
0 idle, 1 skippable, 2 prompt shown, 3 skip asked) sees it skippable. Measured
in the laboratory (lab/journal/etude_saut_cinematiques.md):

* first game: 0x02DCD6E0 sends the opening (Demo102_0) back to idle while no save
  exists, and an Archipelago game always starts on a fresh Cemu account. The
  branch to that reset is gone: the opening is skippable as on a later game;
* + alone: state 1 waited for X. Without X, it now runs state 2's own confirm
  test (0x02DCD580): + asks the skip as it does after X, and X still opens the
  prompt. State 4 (prompt already shown, X skips) takes + as well;
* fade: a cutscene became skippable only once the Fade screen (UI 0x4E) is idle,
  some 5 s into the opening. The skip drives that same screen: it is allowed
  during the fade;
* intro: a new game's code (0x02C2AE4C) requests the 48 s black-screen intro,
  Demo169_0<Timeline>, which no skip reaches (the controller never sees a
  timeline event). The request is never made; the wake-up follows at once.
  Demo169_0 sets no flag;
* forbidden: a cutscene was never skippable when its request forbids the skip
  (0x20000, from the request's byte +0x22) or its .bdemo's SkipPolicy is Forbid.
  The Great Plateau's first view, Demo103_0, is both; its only flag, its flow
  sets again after it. Neither decides any more. Forbid is on three .bdemo only,
  the other two played by event flows (below), which this test never sees.

Cutscenes played by an event flow's own actions are not timelines the controller
sees: the Shrine of Resurrection's pedestal (Demo700_0) and exit (Demo701_0).
Their flows are made cancellable the game's own way (botw_patch/event_cancel.py,
generate()): + cancels them, and the cancel plays their effects again.
"""
from __future__ import annotations

from pathlib import Path
import tempfile

MODULE = 0x6267BFD0     # moduleMatches of the v208 executable, in every version
GROUP = "BOTW_AP_CutsceneSkip_V208"
# address -> (the game's word, the patch, why); checked against the executable by the tests.
PATCHES = {
    0x02DCD7D4: (0x40820030, "nop",
                 "first game: bne 0x02DCD804, the opening's reset while no save exists"),
    0x02DCD568: (0x4182009C, ".int 0x41820018 ; beq 0x02DCD580",
                 "+ alone: state 1 without X runs state 2's confirm test"),
    0x02DCD5E0: (0x55890739, ".int 0x71890808 ; andi. r9, r12, 0x808",
                 "+ alone: state 4 skips on X or +"),
    0x02DD53C0: (0x41820008, "nop",
                 "fade: beq 0x02DD53C8, not skippable while the Fade screen runs"),
    0x02C2AE48: (0x40820058, ".int 0x48000058 ; b 0x02C2AEA0",
                 "intro: bne 0x02C2AEA0, Demo169_0<Timeline> requested only when not yet"),
    0x031DE9B0: (0x4082001C, ".int 0x48000018 ; b 0x031DE9C8",
                 "forbidden: bne 0x031DE9CC, then SkipPolicy Forbid, not skippable when either forbids it"),
}
NATIVE = (f"[{GROUP}]\nmoduleMatches = 0x{MODULE:08X}\n"
          + "".join(f"; {why}\n0x{address:08X} = {patch}\n"
                    for address, (_, patch, why) in PATCHES.items()))
SOURCE_FILES = ("botw_patch/cutscene_skip.py", "botw_patch/event_cancel.py")

TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
# The flows made cancellable: archive -> (flow, the event the segment follows, the
# segment's last event, the effects a cancel plays again, in order).
FLOWS = {
    "Event/Demo700_0.sbeventpack": (
        "Demo700_0", "Event7", "Event65",
        # the Slate bound and taken (GetDemo), Open_FirstDoor, IsGet_PortableUnit, the last warp
        ["Event85", "Event70", "Event61", "Event160", "Event29", "Event104", "Event62", "Event12", "Event96"]),
    "Event/Demo701_0.sbeventpack": (
        "Demo701_0", "Event99", "Event53",
        # the Slate held and put away, the terminal on (Demo041_0), Open_Door, the light, the warp
        ["Event41", "Event14", "Event2", "Event102", "Event106", "Event109", "Event42", "Event110", "Event50"]),
}


def enabled(status: dict | None) -> bool:
    """The slot asks for the cutscenes skipped (the world's cutscene_skip)."""
    return bool(status and status.get("slot_data", {}).get("cutscene_skip"))


def patch_injection(text: str) -> str:
    """The injection with the cutscene patch group after its own."""
    if GROUP in text:
        raise ValueError("parent injection already has the cutscene skip")
    return text.rstrip("\n") + "\n\n" + NATIVE


def cancellable(flow_name: str, after: str, last: str, expected: list[str]):
    """The transform of a flow made cancellable, checked against what was studied."""
    from botw_patch.event_cancel import make_cancellable
    from botw_patch.events import read_flow, write_flow

    def transform(raw: bytes) -> tuple[bytes, dict]:
        flow = read_flow(raw)
        if flow.flowchart.name != flow_name:
            raise ValueError(f"expected the flow {flow_name}")
        replayed = make_cancellable(flow, after, last)
        if replayed != expected:
            raise ValueError(f"{flow_name}: a cancel would play {replayed}, not {expected}")
        return write_flow(flow), {"cancellable": [after, last], "replayed": replayed}
    return transform


def generate(files: dict[str, bytes], content) -> tuple[dict[str, bytes], list[dict]]:
    """The flows of FLOWS made cancellable (the size table is read from `files`).
    content: the update folder, or the game's files (botw_patch/game_files.py)."""
    from botw_patch.game_files import GameFiles
    from botw_patch.resources import ResourceBuilder
    game = GameFiles.of(content)
    if TABLE not in files:
        raise ValueError(f"{TABLE} expected in the overlay")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        stage = Path(temp)
        for name in (*FLOWS, TABLE):
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(files[name] if name in files else game.read(name))
        builder = ResourceBuilder(stage)
        for archive, (flow_name, after, last, expected) in FLOWS.items():
            builder.patch_archive(archive, {f"EventFlow/{flow_name}.bfevfl":
                                            cancellable(flow_name, after, last, expected)})
        out = builder.finish()
    files = dict(files)
    files.update(out)
    return files, builder.changes
