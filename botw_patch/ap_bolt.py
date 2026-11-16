"""The Lightning Strike trap's bolt: Calamity Ganon's lightning, quicker.

LastBossThunder (botw_client/elemental_strike.py) is an actor of its own: its AI
(Actor/AIProgram/LastBossThunder.baiprog, LastBossThunderRoot) shows a warning
sign for SignTime frames (30), then strikes for AppearTime (30), then is deleted.
Seen in play: the trap's bolt came a while after its damage. AP_Thunder is its
copy (ActorInfo entry and actor pack, as the shop items are made,
botw_patch/shop_items.py) with an AI of its own whose sign lasts SIGN_FRAMES:
Ganon's own bolt is left as it is. The client creates the bolt, then the electric
field on Link SIGN_FRAMES later, as it lands.
"""
from __future__ import annotations

import io

import oead

from botw_patch.resources import unpack

MODEL = "LastBossThunder"
ACTOR = "AP_Thunder"
SIGN_FRAMES = 6.0
ACTOR_INFO = "Actor/ActorInfo.product.sbyml"
TABLE = "System/Resource/ResourceSizeTable.product.srsizetable"
SOURCE_FILES = ("botw_patch/ap_bolt.py",)


def quicker(pack: bytes) -> tuple[bytes, dict]:
    """The cloned pack with an AI of its own (AIProgramUser ACTOR) whose sign lasts SIGN_FRAMES."""
    archive = oead.Sarc(unpack(pack))
    writer = oead.SarcWriter.from_sarc(archive)
    link_name = f"Actor/ActorLink/{ACTOR}.bxml"
    link = oead.aamp.ParameterIO.from_binary(bytes(archive.get_file(link_name).data))
    target = link.objects["LinkTarget"].params
    if str(target["AIProgramUser"].v) != MODEL:
        raise ValueError(f"unexpected AI of {MODEL}: {target['AIProgramUser'].v}")
    target["AIProgramUser"] = oead.aamp.Parameter(ACTOR)
    old = f"Actor/AIProgram/{MODEL}.baiprog"
    program = oead.aamp.ParameterIO.from_binary(bytes(archive.get_file(old).data))
    changed = []
    for name, action in program.lists["Action"].lists.items():
        definition = action.objects["Def"].params
        if str(definition["ClassName"].v) == "LastBossThunderSign":
            params = action.objects["SInst"].params
            changed.append((float(params["SignTime"].v), SIGN_FRAMES))
            params["SignTime"] = oead.aamp.Parameter(SIGN_FRAMES)
    if len(changed) != 1:
        raise ValueError(f"{MODEL}: {len(changed)} warning signs found, one expected")
    del writer.files[old]
    writer.files[f"Actor/AIProgram/{ACTOR}.baiprog"] = bytes(program.to_binary())
    writer.files[link_name] = bytes(link.to_binary())
    return bytes(oead.yaz0.compress(bytes(writer.write()[1]))), {"sign_frames": changed[0]}


def generate(files: dict[str, bytes], game) -> tuple[dict[str, bytes], list[dict]]:
    """AP_Thunder's ActorInfo entry and actor pack, with its size table entries, into
    `files`, which holds the size table."""
    import rstb
    from botw_patch.shop_items import ApShopItem, add_declarations, clone_actor_pack
    files = dict(files)
    item = ApShopItem(ACTOR, None, "", "", model_actor=MODEL)
    info = files[ACTOR_INFO] if ACTOR_INFO in files else game.read(ACTOR_INFO)
    files[ACTOR_INFO], declared = add_declarations(info, [item])
    cloned, _ = clone_actor_pack(game.read(f"Actor/Pack/{MODEL}.sbactorpack"), MODEL, ACTOR)
    files[f"Actor/Pack/{ACTOR}.sbactorpack"], detail = quicker(cloned)
    table = rstb.ResourceSizeTable(unpack(files[TABLE]), True)
    for kind, ext in (("Actor/Pack", "bactorpack"), ("Actor/ActorLink", "bxml"), ("Actor/AIProgram", "baiprog")):
        table.set_size(f"{kind}/{ACTOR}.{ext}", table.get_size(f"{kind}/{MODEL}.{ext}"))
    stream = io.BytesIO()
    table.write(stream, True)
    files[TABLE] = bytes(oead.yaz0.compress(stream.getvalue()))
    return files, [{"resource": ACTOR_INFO, "declarations": declared},
                   {"resource": f"Actor/Pack/{ACTOR}.sbactorpack", "cloned_from": MODEL, **detail}]
