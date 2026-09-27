"""Ask the native event wrapper to construct and submit its own request."""
import struct
import time
from tools.cemu.getdemo_state import snapshot

HELPER = 0x02DDF744
MANAGER_PTR = 0x1046D3AC  # lis 0x1047 + signed displacement -0x2c54; RPX relocation.
SIGNATURE = bytes.fromhex("9421fe88bf4101607c0802a67c7a1b787c9b23787cbc2b787cfe3b789001017c")


def retry_until_accepted(attempt, ready, checkpoint, timeout=90):
    """Retry only explicit native refusals; never retry acceptance/unknown outcome."""
    started = time.monotonic()
    evidence = {"status": "waiting", "attempts": [], "text_armed": False}
    checkpoint(evidence)
    try:
        while time.monotonic() - started < timeout:
            if ready():
                current = {}
                evidence["attempts"].append(current)
                def progress(value):
                    current.update(value)
                    checkpoint(evidence)
                result = attempt(progress)
                if result.get("native_return") == 1:
                    evidence.update(status="accepted", seconds=time.monotonic() - started)
                    return result
                if result.get("native_return") != 0:
                    raise RuntimeError("Resultat natif incertain : aucun nouvel essai automatique")
                evidence["status"] = "native_refused_waiting"
                checkpoint(evidence)
            time.sleep(0.5)
        raise RuntimeError("Demande non acceptee en90 secondes ; aucun evenement force")
    except BaseException as exc:
        evidence.update(status="failed", error=str(exc))
        raise
    finally:
        checkpoint(evidence)


def inspect(process, base):
    if process.read(base + HELPER, len(SIGNATURE)) != SIGNATURE:
        raise ValueError("event wrapper signature mismatch")
    manager = int.from_bytes(process.read(base + MANAGER_PTR, 4), "big")
    return dict(helper=HELPER, manager_pointer=MANAGER_PTR, manager=manager, signature_verified=True,
                manager_available=0x01000000 <= manager < 0x60000000)


def manager_diagnostic(process, base):
    """Read-only raw manager fields used by the v208 submission path.

    These are observations, not a new readiness rule. The authoritative
    outcome remains the native ACK; no manager state is modified here.
    """
    result = inspect(process, base)
    if not result['manager_available']:
        return result
    manager = result['manager']
    def raw(offset, size):
        if not 0x01000000 <= manager+offset < manager+offset+size <= 0x60000000:
            raise ValueError('event manager diagnostic outside guest range')
        data = process.read(base+manager+offset, size)
        if data is None or len(data) != size:
            raise RuntimeError('short event manager diagnostic read')
        return data
    result['submission_flags_175d0'] = int.from_bytes(raw(0x175d0,4),'big')
    result['admission_block_175b0'] = int.from_bytes(raw(0x175b0,4),'big')
    result['submission_byte_174b7'] = raw(0x174b7,1)[0]
    result['executor_slots_17530'] = [int.from_bytes(raw(0x17530+i*4,4),'big') for i in range(32)]
    return result


def request(process, cave, number, checkpoint, custom_text=False, *,
            flow="Demo007_1", entry="APDisplayStandalone"):
    for label, value in (("flow", flow), ("entry", entry)):
        try:
            encoded = value.encode("ascii")
        except (AttributeError, UnicodeEncodeError) as exc:
            raise ValueError(f"{label} EventFlow must be ASCII") from exc
        if not encoded or len(encoded) >= 0x40 or b"\0" in encoded:
            raise ValueError(f"{label} EventFlow exceeds native buffer")
    def word(address):
        raw = process.read(address, 4)
        if raw is None or len(raw) != 4:
            raise RuntimeError("short mailbox read")
        return int.from_bytes(raw, "big")
    state = inspect(process, cave.base)
    ui = snapshot(process, cave.base)
    pf_ready, ui_ready = cave.pf_ready(), cave.ui_ready()
    result = dict(number=number, flow=flow, entry=entry, before=state,
                  before_ui=ui, pf_ready=pf_ready, ui_ready=ui_ready, status="preflight")
    checkpoint(result)
    if not state["manager_available"] or not pf_ready or not ui_ready:
        result.update(status="not_ready")
        checkpoint(result)
        raise RuntimeError("Gestionnaire/invocateur non pret")
    if ui["screen"] or ui["name"] or not ui["manager"] or word(cave.pf_req) or word(cave.opn_req):
        raise RuntimeError("Fenetre ou demande deja presente")
    title, _, desc, _, auto = cave.sub_state()
    if title or desc or auto:
        raise RuntimeError("Substitution de texte deja armee")
    if custom_text:
        from tools.cemu.scoped_text import verify_gates
        result["text_gates"] = verify_gates(process, cave.base)
    before = word(cave.call_n)
    result.update(call_count_before=before, status="prepared")
    # Stable mailbox strings; the native wrapper constructs/copies its descriptor.
    process.write(cave.text_buf, flow.encode("ascii") + b"\0")
    process.write(cave.text_buf + 0x40, entry.encode("ascii") + b"\0")
    process.write(cave.text_buf + 0xc0, struct.pack(">4I", cave.guest(cave.text_buf), 0x10263910,
                  cave.guest(cave.text_buf + 0x40), 0x10263910))
    checkpoint(result)
    accepted = False
    try:
        if custom_text:
            title = f"Test Archipelago {number}"
            description = f"Message numero {number}.\nAffichage par EventFlow."
            cave.show_item_text(title, description)
            result.update(title=title, description=description)
            checkpoint(result)
        # r3 owner=NULL is used by vanilla at 03048228/03048290.
        # r6=1/r7=0 match the observed campfire wrapper 02de0730.
        cave.call_pf(HELPER, 0, cave.guest(cave.text_buf + 0xc0), cave.guest(cave.text_buf + 0xc8), 1, 0)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            count = word(cave.call_n)
            if count != before:
                result.update(status="returned", call_count_after=count, native_return=word(cave.call_ret))
                accepted = result["native_return"] == 1
                checkpoint(result)
                return result
            time.sleep(0.01)
        result.update(status="timeout")
        checkpoint(result)
        raise RuntimeError("Demande sans accuse de reception; requete restante annulee")
    finally:
        process.write(cave.pf_req, bytes(4))
        if custom_text and not accepted:
            cave.sub_disarm()
