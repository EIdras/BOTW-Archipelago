"""What killed Link: the cause of the DeathLink the client sends.

The game keeps the type of the last damage Link took, and the actor that dealt
it; the Game Over tips read them (TipsGameOver.bfevfl). Measured at deaths by
fire, fall, enemy, bomb, drowning and cold:

  * the EventFlow query CheckPlayerDeadCause (doQuery DEAD_CAUSE_QUERY) needs
    no `this`: it finds the player through the PlayerInfo singleton and
    returns 0..13, named by TipsGameOver: 0 Hot and the default (an enemy's
    blow), 1 Cold, 2 Ice, 3 Poison, 4 Fire, 5 Shock, 6 Lightning, 7 Drown,
    8 Fall, 9 Bomb, 10 Press, 11 MasterSword, 12 SuddenDeath, 13 Fall. The
    client calls it through the cave's per-frame hook, as it calls the event
    manager. DEAD_CAUSE_RAW(player) is the value it maps: its low 16 bits
    tell heat (1) from an enemy's blow (0), which the query does not;
  * the last attacker is the SafeString {text, vtable} at player + ATTACKER
    (the query CheckLastDamageAttacker compares with it): an actor name such
    as Enemy_Bokoblin_Junior, or RemoteBomb. Damage from the environment
    (fire, cold...) and a reload clear it.

It is the type of the last damage, not a cause of death as such: the
DeathLink entry's damage sets none, so a received DeathLink leaves whatever
came before (it is recognized by its flag instead, botw_patch/death_link.py).
"""
from __future__ import annotations

from tools.cemu.guest import in_guest, in_heap

PLAYER_INFO = 0x10463F38           # PlayerInfo*; its player at + PLAYER_OFFSET
PLAYER_OFFSET = 0x30
ATTACKER = 0x974
DEAD_CAUSE_QUERY = 0x02A6BC18
DEAD_CAUSE_RAW = 0x02B72C30
HEAT = 1                           # low 16 bits of the raw value

# Attackers without a name of their own in the game's texts, named as the actor
# they stand for: the angry cuccos' attackers (the Cucco Swarm's too), the Yiga
# archer (a Yiga Footsoldier in the game's texts).
ALIASES = {"Kokko_Simple": "Animal_Kokko_A",
           "Enemy_Assassin_Shooter_Junior": "Enemy_Assassin_Junior"}

VERBS = {
    1: "froze to death", 2: "froze to death", 3: "was poisoned", 4: "burned to death",
    5: "was electrocuted", 6: "was struck by lightning", 7: "drowned",
    8: "fell to their death", 13: "fell to their death", 10: "was crushed",
    11: "was rejected by the Master Sword", 12: "died suddenly",
}


def player(read) -> int | None:
    """read(guest, size) -> bytes | None. The player actor, when there is one."""
    def u32(guest):
        raw = read(guest, 4)
        return int.from_bytes(raw, "big") if raw and len(raw) == 4 else None

    info = u32(PLAYER_INFO)
    if not in_heap(info):
        return None
    actor = u32(info + PLAYER_OFFSET)
    return actor if in_heap(actor) else None


def attacker(read, actor: int | None) -> str | None:
    """The last actor that hurt Link, or None."""
    if actor is None:
        return None
    raw = read(actor + ATTACKER, 4)
    text = int.from_bytes(raw, "big") if raw and len(raw) == 4 else 0
    if not in_guest(text):
        return None
    name = (read(text, 96) or b"").split(b"\0")[0]
    try:
        name = name.decode("ascii")
    except UnicodeDecodeError:
        return None
    return name if name.isprintable() and name else None


def _article(name: str) -> str:
    return "an" if name[:1].lower() in "aeiou" else "a"


def death_text(slot: str, cause: int | None, raw: int | None, killer: str | None,
               names: dict[str, str]) -> str:
    """The DeathLink cause sent for Link's death."""
    name = names.get(ALIASES.get(killer, killer)) if killer else None
    if cause == 9:
        if killer == "RemoteBomb":
            return f"{slot} was caught in their own bomb blast"
        return f"{slot} was blown up by {_article(name)} {name}" if name else f"{slot} was blown up"
    if cause in VERBS:
        return f"{slot} {VERBS[cause]}"
    if cause == 0 and raw is not None and raw & 0xFFFF == HEAT:
        return f"{slot} died of the heat"
    if cause == 0 and name:
        return f"{slot} was slain by {_article(name)} {name}"
    return f"{slot} died in Hyrule"
