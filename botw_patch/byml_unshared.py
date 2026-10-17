"""BYML (version 2, big endian) written with every container a node of its own.

oead's writer gives identical containers one shared node: the game's
Quest/QuestProduct.sbquestpack, read and written again unchanged, went from
883444 to 466736 bytes. The game does not take such a file: with it (and our
quest added, or not even started), the Shrine of Resurrection's pedestal, then
every tower and shrine terminal, offered no interaction (seen in play, 16/10,
lab probe 24). Its own file shares no container. This writer keeps them apart,
as the game's: the hash keys and the strings in their two sorted tables, then
the nodes, each container once per place it holds, its children after it.

Only the value types such files hold: hash, array, string, bool, S32, U32, F32.
"""
from __future__ import annotations

import struct

import oead

STRING, ARRAY, HASH, TABLE = 0xA0, 0xC0, 0xC1, 0xC2
BOOL, INT, FLOAT, UINT, NULL = 0xD0, 0xD1, 0xD2, 0xD3, 0xFF


def _collect(node, keys: set, strings: set) -> None:
    if isinstance(node, oead.byml.Hash):
        for key, value in node.items():
            keys.add(key)
            _collect(value, keys, strings)
    elif isinstance(node, oead.byml.Array):
        for value in node:
            _collect(value, keys, strings)
    elif isinstance(node, str):
        strings.add(node)


def _table(values: list[str]) -> bytes:
    encoded = [v.encode("utf-8") + b"\0" for v in values]
    head = 4 + 4 * (len(values) + 1)
    offsets, position = [], head
    for raw in encoded:
        offsets.append(position)
        position += len(raw)
    offsets.append(position)
    out = struct.pack(">I", (TABLE << 24) | len(values)) + struct.pack(f">{len(offsets)}I", *offsets)
    out += b"".join(encoded)
    return out + b"\0" * (-len(out) % 4)


def to_binary(root) -> bytes:
    """The document `root` (a Hash or an Array), version 2, big endian."""
    keys, strings = set(), set()
    _collect(root, keys, strings)
    key_list = sorted(keys, key=lambda k: k.encode("utf-8"))
    string_list = sorted(strings, key=lambda s: s.encode("utf-8"))
    key_index = {k: i for i, k in enumerate(key_list)}
    string_index = {s: i for i, s in enumerate(string_list)}
    key_table, string_table = _table(key_list), _table(string_list)
    out = bytearray(16)
    out += key_table
    strings_at = len(out)
    out += string_table

    def value(node) -> tuple[int, int | None]:
        """(type, inline value), or (type, None) for a container written later."""
        if isinstance(node, oead.byml.Hash):
            return HASH, None
        if isinstance(node, oead.byml.Array):
            return ARRAY, None
        if isinstance(node, str):
            return STRING, string_index[node]
        if isinstance(node, bool):
            return BOOL, int(node)
        if isinstance(node, oead.U32):
            return UINT, int(node)
        if isinstance(node, (oead.S32, int)):
            return INT, int(node) & 0xFFFFFFFF
        if isinstance(node, (oead.F32, float)):
            return FLOAT, struct.unpack(">I", struct.pack(">f", float(node)))[0]
        if node is None:
            return NULL, 0
        raise TypeError(f"unsupported BYML value: {type(node).__name__}")

    def emit(node) -> int:
        while len(out) % 4:
            out.append(0)
        at = len(out)
        if isinstance(node, oead.byml.Hash):
            items = sorted(node.items(), key=lambda kv: key_index[kv[0]])
            out.extend(struct.pack(">I", (HASH << 24) | len(items)))
            slots = []
            for key, child in items:
                kind, inline = value(child)
                slots.append((len(out) + 4, child if inline is None else None))
                out.extend(struct.pack(">I", (key_index[key] << 8) | kind))
                out.extend(struct.pack(">I", inline or 0))
        else:
            children = list(node)
            out.extend(struct.pack(">I", (ARRAY << 24) | len(children)))
            kinds = [value(child) for child in children]
            out.extend(bytes(kind for kind, _ in kinds))
            while len(out) % 4:
                out.append(0)
            slots = []
            for child, (kind, inline) in zip(children, kinds):
                slots.append((len(out), child if inline is None else None))
                out.extend(struct.pack(">I", inline or 0))
        for where, child in slots:
            if child is not None:
                struct.pack_into(">I", out, where, emit(child))
        return at

    root_at = emit(root)
    struct.pack_into(">2sHIII", out, 0, b"BY", 2, 16, strings_at, root_at)
    return bytes(out)
