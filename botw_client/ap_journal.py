"""What the in-game AP journal shows, and how it reads (Simon, 25/09).

The journal shows the AP server's own messages (PrintJSON), as any AP client
does, coloured in the tip frame's markup ({N}...{/}): players {2}, items {1}.
By default only what concerns this slot:
  * items it receives (from another player or found in its own world): the
    server's line is shown by the runtime just before the item's
    presentation (BotwClientRuntime._received_announcement), in order;
  * items it sends to other players;
  * hints about its items or locations;
  * chat, which can be turned off.
Other players' traffic is hidden unless asked.
"""
from __future__ import annotations

from typing import Callable

PLAYER, ITEM = 2, 1


def _node(entry: dict, kind: str) -> dict | None:
    return next((n for n in entry.get("nodes") or () if isinstance(n, dict)
                 and n.get("type") == kind), None)


def _plain(text: str) -> str:
    """Received text never carries our colour markup."""
    return str(text).replace("{", "(").replace("}", ")")


def coloured(entry: dict, render: Callable[[dict], str]) -> str:
    """The server's message, its players and items coloured."""
    out = []
    for node in entry.get("nodes") or ():
        if not isinstance(node, dict):
            continue
        text = _plain(render(node))
        colour = {"player_id": PLAYER, "player_name": PLAYER,
                  "item_id": ITEM, "item_name": ITEM}.get(node.get("type"))
        out.append(f"{{{colour}}}{text}{{/}}" if colour is not None and text else text)
    return "".join(out).strip() or _plain(entry.get("text", "")).strip()


def is_received_item(entry: dict, me: int) -> bool:
    """A server line announcing an item for this slot (shown with its item)."""
    return (isinstance(entry, dict) and entry.get("kind") == "ItemSend"
            and entry.get("receiving") == me)


def matches_item(entry: dict, me: int, item) -> bool:
    """The server's ItemSend line of this received NetworkItem."""
    if not is_received_item(entry, me) or entry.get("sender") != item.player:
        return False
    node, location = _node(entry, "item_id"), _node(entry, "location_id")
    return (node is not None and location is not None
            and str(node.get("text")) == str(item.item)
            and str(location.get("text")) == str(item.location))


def journal_line(entry: dict, me: int, render: Callable[[dict], str], *,
                 chat: bool = True, everyone: bool = False) -> str | None:
    """The journal line of one received AP message, or None if not shown here."""
    if not isinstance(entry, dict):
        return None
    kind = entry.get("kind")
    if kind in ("Chat", "ServerChat"):
        return coloured(entry, render) if chat else None
    if kind == "ItemSend":
        if entry.get("receiving") == me:
            return None                   # shown with the item it announces
        if entry.get("sender") == me or everyone:
            return coloured(entry, render)
        return None
    if kind == "Hint":
        if me in (entry.get("receiving"), entry.get("sender")) or everyone:
            return coloured(entry, render)
        return None
    return coloured(entry, render) if everyone else None
