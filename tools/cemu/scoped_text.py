"""Read-only verification of the assembled Item_AP label gates."""
from tools.build_scoped_text import SCOPES


def assess_text(evidence, expected_displays=2):
    reasons = []
    samples = evidence.get("samples", [])
    closes = evidence.get("before_cleanup", [])
    if evidence.get("read_error") or evidence.get("truncated"):
        reasons.append("text diagnostic incomplete")
    if not samples or len(closes) < expected_displays:
        reasons.append("missing text observations")
    else:
        previous = samples[0]["substitution"]
        for close in closes[:expected_displays]:
            current = close["substitution"]
            if current[0] or current[2] or current[4]:
                reasons.append("text quota remained before Python cleanup")
            if (current[1] - previous[1], current[3] - previous[3]) != (2, 2):
                reasons.append("expected two native title/description substitutions per display")
            previous = current
    return dict(status="needs_review" if reasons else "collected", reasons=reasons,
                limitation="Counters do not prove rendered text or request identity.")


def verify_gates(process, base):
    evidence = []
    for site, offset, storage, label, _, _ in SCOPES:
        raw = process.read(base + site, 4)
        if raw is None or len(raw) != 4:
            raise ValueError("short hook read")
        branch = int.from_bytes(raw, "big")
        if branch & 0xFC000003 != 0x48000003:
            raise ValueError("expected absolute linking substitution hook")
        target = branch & 0x03FFFFFC
        if not 0x01000000 <= target < 0x02000000:
            raise ValueError("unexpected substitution cave address")
        code = process.read(base + target, 1024)
        if code is None or len(code) != 1024:
            raise ValueError("short gate read")
        prefix = b"".join(w.to_bytes(4, "big") for w in
                          (0x39810000 | storage, 0x80010000 | offset, 0x7C006000))
        positions = [i for i in range(0, len(code) - len(prefix), 4) if code[i:i+12] == prefix]
        if len(positions) != 1:
            raise ValueError("Item_AP gate missing or ambiguous")
        start = positions[0]
        exits = []
        def check_exit(pos):
            word = int.from_bytes(code[pos:pos+4], "big")
            if word & 0xFFFF0003 != 0x40820000:
                raise ValueError("gate must reject mismatches")
            displacement = word & 0xFFFC
            if displacement & 0x8000:
                displacement -= 0x10000
            exits.append(target + pos + displacement)
        check_exit(start + 12)
        for index, value in enumerate(label):
            pos = start + 16 + index * 12
            expected = (0x89810000 | (storage + index), 0x2C0C0000 | value)
            if code[pos:pos+8] != b"".join(w.to_bytes(4, "big") for w in expected):
                raise ValueError("exact label comparison missing")
            check_exit(pos + 8)
        if len(set(exits)) != 1 or exits[0] <= target + start + 16 + len(label) * 12:
            raise ValueError("gate exits do not skip substitution")
        evidence.append(dict(site=site, hook=target, gate=target+start,
                             label=label[:-1].decode(), reject_target=exits[0]))
    return evidence
