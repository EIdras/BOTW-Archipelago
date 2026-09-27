"""Build a hash -> host address index for BOTW's live GameData flags in Cemu.

The live table is not one contiguous array: it is a set of sorted fragments of
roughly 2000 entries each, 8 bytes per entry {u32 hash, u32 value}, big-endian.
Two decoys share the same hashes and must be rejected - a 16-byte definition
table sorted by name holding defaults, and a 16-byte hash->index table. A real
entry is recognised by its neighbours also being known hashes in ascending
order, which the 16-byte tables never satisfy at an 8-byte stride.
"""
import json, pathlib, sys
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winmem import Process

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
MIN_RUN = 24


def load_flags():
    g = json.load(open(ROOT / "data" / "gamedata.json", encoding="utf-8"))
    return ({int(k) & 0xFFFFFFFF: v[1] for k, v in g.items()},
            {int(k) & 0xFFFFFFFF: v[0] for k, v in g.items()},
            {v[1]: int(k) & 0xFFFFFFFF for k, v in g.items()})


def _runs(mask, min_len):
    if not mask.any():
        return []
    edges = np.flatnonzero(np.diff(np.concatenate(([0], mask.view(np.int8), [0]))))
    return [(int(s), int(e - s)) for s, e in zip(edges[0::2], edges[1::2]) if e - s >= min_len]


def build_index(p: Process, known: np.ndarray, window=32 << 20):
    """Return {hash: host_address} for every flag found in a live fragment."""
    index = {}
    for base, size in p.regions(min_size=1 << 20):
        off = 0
        while off < size:
            n = min(window, size - off)
            buf = p.read(base + off, n)
            off += n
            if not buf or len(buf) < 32:
                continue
            for phase in (0, 4):
                body = buf[phase:]
                body = body[: (len(body) // 8) * 8]
                if len(body) < 32:
                    continue
                a = np.frombuffer(body, dtype=">u4").reshape(-1, 2)
                hs = a[:, 0]
                hit = np.isin(hs, known)
                if int(hit.sum()) < MIN_RUN:
                    continue
                good = hit[:-1] & hit[1:] & (np.diff(hs.astype(np.int64)) > 0)
                for start, length in _runs(good, MIN_RUN):
                    seg = hs[start:start + length + 1]
                    addr0 = base + off - n + phase + start * 8
                    for j, h in enumerate(seg.tolist()):
                        index.setdefault(h, addr0 + j * 8)
    return index


def read_values(p: Process, index: dict, hashes):
    """Read current values for the given hashes. Returns {hash: value}."""
    out = {}
    for h in hashes:
        a = index.get(h)
        if a is None:
            continue
        raw = p.read(a, 8)
        if raw and len(raw) == 8:
            out[h] = int(np.frombuffer(raw, dtype=">u4")[1])
    return out
