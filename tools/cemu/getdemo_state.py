"""Read-only UI oracle, from the measurements of the get window (getdemo.py).

This never opens/closes a screen or queues a native call. An unchanged name
does not prove that no call occurred; polling may miss brief transitions.
"""

MGR_PTR = 0x1047B054
SCR_PTR = 0x1047E650


def close_trace_address(log_text):
    import re
    matches = re.findall(r"BOTW_AP_UICloseTrace_V208.*?Codecave: ([0-9a-fA-F]+)-", log_text)
    return int(matches[-1], 16) if matches else None


def close_trace(process, base, address):
    if address is None or not 0x01000000 <= address < 0x60000000:
        raise ValueError("close trace not located in Cemu log")
    data = process.read(base + address, 16)
    if data is None or len(data) != 16 or data[:8] != bytes.fromhex("4150554900000001"):
        raise ValueError("close trace signature mismatch")
    return {"close_count": int.from_bytes(data[8:12], "big"),
            "last_close_return_address": int.from_bytes(data[12:16], "big")}


def snapshot(process, base):
    def raw(address, size):
        if not 0x01000000 <= address < 0x60000000 or size < 1 or size > 64:
            raise ValueError(f"invalid UI read: {address:#x}, {size}")
        data = process.read(base + address, size)
        if data is None or len(data) != size:
            raise RuntimeError(f"short UI read: {address:#x}")
        return data

    def word(address):
        return int.from_bytes(raw(address, 4), "big")

    manager = word(MGR_PTR)
    result = {"manager": manager, "name_buffer": 0, "name": None,
              "screen_manager": 0, "screen": 0, "activity": None,
              "screen_active": False}
    if manager:
        buf, capacity = word(manager + 0x20), word(manager + 0x28)
        result.update(name_buffer=buf, name_capacity=capacity)
        if buf and capacity:
            result["name"] = raw(buf, min(capacity, 64)).split(b"\0", 1)[0].decode("ascii", "replace")
    screen_manager = word(SCR_PTR)
    result["screen_manager"] = screen_manager
    if screen_manager:
        table = word(screen_manager + 0x18)
        if table:
            result["screen"] = word(table + 0x0B * 4)
        if result["screen"]:
            result["activity"] = raw(screen_manager + 0x604 + 0x0B, 1)[0]
            result["screen_active"] = result["activity"] != 0xFF
    return result
