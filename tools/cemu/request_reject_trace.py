"""Bounded read-only decoder for the lab request-stage trace."""
import re
import struct

MAGIC = 0x4150524a
SIZE = 112
STAGES = ('descriptor_prepare', 'resource_validate', 'request_result')


def decode(raw):
    if raw is None or len(raw) != SIZE:
        raise RuntimeError('short request trace read')
    words = struct.unpack('>28I', raw)
    if words[:2] != (MAGIC, 1):
        raise ValueError('request trace signature mismatch')
    if words[3]:
        raise RuntimeError('request trace publication in progress')
    result = {'version':1, 'sequence':words[2], 'scope':'wrapper_calls_only', 'stages':{}}
    for i, stage in enumerate(STAGES):
        seq, returned, caller, manager, code, *_ = words[4+i*8:12+i*8]
        result['stages'][stage] = {'sequence':seq, 'reached':bool(seq),
            'returned_raw':returned, 'caller_return':caller, 'manager':manager,
            'engine_code_raw':code if i == 2 else None}
    return result


def snapshot(process, base, log):
    matches = re.findall(r'BOTW_AP_RequestReject_V208[^\n]*Codecave: ([0-9a-fA-F]+)-([0-9a-fA-F]+)',
                         log.read_text(encoding='utf-8', errors='replace'))
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError('ambiguous request trace codecave')
    start, end = (int(v,16) for v in matches[0])
    if not 0x01000000 <= start < start+SIZE <= end <= 0x10000000:
        raise ValueError('request trace codecave outside guest range')
    for _ in range(4):
        raw = process.read(base+start,SIZE)
        if (raw is not None and len(raw) == SIZE and raw[12:16] == bytes(4)
                and raw == process.read(base+start,SIZE)):
            return decode(raw)
    raise RuntimeError('unstable request trace read')
