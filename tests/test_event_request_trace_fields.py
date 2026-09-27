"""Console /ap-evt: the request fields read from the runtime trace."""
import struct
import unittest

from tools.cemu.event_request_trace import descriptor_fields


def descriptor(flow, entry, kind, flags):
    raw = bytearray(0x118)
    raw[0x20:0x20 + len(flow)] = flow.encode()
    raw[0x6c:0x6c + len(entry)] = entry.encode()
    raw[0xf8:0xf8 + len(kind)] = kind.encode()
    struct.pack_into(">I", raw, 0x108, flags)
    return bytes(raw)


class TraceFieldTests(unittest.TestCase):
    def test_request_fields_at_the_wii_u_metadata_offsets(self):
        # These offsets read the game's own Npc_King_Vagrant001<Near>
        # as type Near, flags 0x19a, as zeldaret/botw initFlags_ computes.
        self.assertEqual(descriptor_fields(descriptor("Npc_King_Vagrant001", "Near", "Near", 0x19a)),
                         {"flow": "Npc_King_Vagrant001", "entry": "Near", "type": "Near",
                          "flags": 0x19a})


if __name__ == "__main__":
    unittest.main()
