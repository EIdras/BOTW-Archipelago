"""Experimental owner protocol; no grant, ledger, queue replay or forced UI close."""
import struct
import time
import ctypes
from ctypes import wintypes
from contextlib import contextmanager
from tools.build_owned_presentation import SITES, owner_source

PHASES = ("idle", "staged", "submitting", "accepted", "bound", "action_complete",
          "released", "refused", "uncertain", "finished")


@contextmanager
def publisher_lock(pid):
    """One publisher per emulator, including different Python processes.

    An abandoned OS mutex grants no permission to replay: the native phase
    still decides whether staging is allowed after acquisition.
    """
    if type(pid) is not int or pid <= 0:
        raise ValueError("publisher requires an explicit emulator PID")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.ReleaseMutex.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.CreateMutexW(None, False, f"Local\\BOTW_AP_Owner_{pid}")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    acquired = False
    try:
        status = kernel.WaitForSingleObject(handle, 0)
        if status not in (0, 0x80):
            raise RuntimeError("Another presentation publisher is active or the mutex is unavailable")
        acquired = True
        yield
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


def layout(version=1, *, retired_guard=False, resource_gate=True, event_gate=False, messages=False):
    labels, offset = {}, 0
    source = owner_source(version, retired_guard=retired_guard,
                          resource_gate=resource_gate, event_gate=event_gate)
    if messages:
        if version != 2 or not (retired_guard and resource_gate and event_gate):
            raise ValueError('Messages require the complete guarded owner v2')
        from tools.build_message_action import compose_executor_hooks
        from tools.message_submission import compose_submission
        source = compose_submission(compose_executor_hooks(source))
    for line in source.splitlines():
        line = line.split(";", 1)[0].strip()
        if not line or "=" in line:
            continue
        if line.endswith(":"):
            labels[line[:-1]] = offset
        else:
            offset += 4
    return labels, offset


def read(process, base, address):
    for _ in range(4):
        raw = process.read(base + address, 64)
        if raw is None or len(raw) != 64:
            raise RuntimeError("short owner state read")
        if raw == process.read(base + address, 64):
            break
    else:
        raise RuntimeError("owner state changed during read")
    (magic, version, phase, generation, action, native_return, completed, left,
     bound, aborted, quota, reserved, busy, fault, title_left, desc_left) = struct.unpack(">16I", raw)
    if (magic != 0x41504F57 or version not in (1,2) or phase >= (9 if version==1 else 10)
            or reserved or quota not in (2, 4)):
        raise ValueError("owner state signature mismatch")
    return dict(version=version, phase=PHASES[phase], phase_number=phase, generation=generation, action=action,
                native_return=native_return, bound_generation=bound, completed_generation=completed,
                left_generation=left, aborted_generation=aborted, busy=busy, fault=fault,
                resolution_quota=quota, title_before_native_cleanup=title_left, description_before_native_cleanup=desc_left)


def inspect(process, base):
    from tools.cemu.scoped_text import verify_gates
    # Locate the header using each supported generated layout. Never guess the
    # version from a patched branch without checking its data signature.
    first_site=SITES[0][0]
    raw=process.read(base+first_site,4)
    if raw is None or len(raw)!=4:
        raise RuntimeError('short owner version hook read')
    word=int.from_bytes(raw,'big')
    displacement=word&0x03fffffc
    if displacement&0x02000000:
        displacement-=0x04000000
    if word & 0xFC000003 != 0x48000000:
        raise ValueError('owner version hook missing/conflicting')
    # Resource preflight adds instructions before Bind, without changing the
    # protocol version. Historical immutable packs must remain recognizable.
    variants = [(v, r, e, False) for v, r, e in
                ((1,False,False),(1,True,False),(2,False,False),(2,True,False),(1,True,True),(2,True,True))]
    variants.append((2, True, True, True))
    for version,resource_gate,event_gate,messages in variants:
        labels,size=layout(version,resource_gate=resource_gate,event_gate=event_gate,
                           messages=messages, retired_guard=messages)
        candidate=first_site+displacement-labels['apOwnedBind']
        if process.read(base+candidate,8)==struct.pack('>2I',0x41504f57,version):
            break
    else:
        raise ValueError('owner protocol version not located')
    data = None
    hooks = []
    for site, original, name in SITES:
        raw = process.read(base+site, 4)
        if raw is None or len(raw) != 4:
            raise RuntimeError("short owner hook read")
        word = int.from_bytes(raw, "big")
        displacement = word & 0x03FFFFFC
        if displacement & 0x02000000:
            displacement -= 0x04000000
        target = site + displacement
        candidate = target - labels["apOwned"+name]
        if (word & 0xFC000003 != 0x48000000 or not 0x01000000 <= candidate < 0x02000000
                or (data is not None and data != candidate)):
            raise ValueError("owner hook missing/conflicting")
        data = candidate
        if process.read(base+target, 8) != struct.pack(">2I", original, 0x9421FFE0):
            raise ValueError("owner hook original/prologue mismatch")
        hooks.append(dict(site=site, target=target, name=name))
    state = read(process, base, data)
    for entry in verify_gates(process, base):
        start = entry["gate"] - 32
        words = struct.unpack(">8I", process.read(base+start, 32))
        expected = (0x3D800000 | ((data+0x8000) >> 16), 0x398C0000 | (data & 0xFFFF),
                    0x800C0034, 0x2C000000, None, 0x800C0008, 0x2C000004, None)
        for index, value in enumerate(expected):
            if value is not None and words[index] != value:
                raise ValueError("owner text gate mismatch")
        for index in (4, 7):
            word = words[index]
            displacement = word & 0xFFFC
            if displacement & 0x8000:
                displacement -= 0x10000
            if word & 0xFFFF0003 != 0x40820000 or start+index*4+displacement != entry["reject_target"]:
                raise ValueError("owner text gate does not reject")
    submit = data + labels["apOwnedSubmit"]
    if process.read(base+submit, 16) != bytes.fromhex("9421ffe07c0802a69001002493e1001c"):
        raise ValueError("owner submit prologue mismatch")
    result=dict(address=data, submit=submit, extension_size=size, hooks=hooks,
                state=state, version=version, resource_gate=resource_gate, event_gate=event_gate)
    if version==2:
        from tools.native_presentation_join import SITES as join_sites
        # Historical owner-v2 builds and the executor-reuse fix share the
        # header/owner hooks. Select only a fully matching native join layout.
        for retired_guard in ((True,) if messages else (False, True)):
            candidate_labels, candidate_size = layout(
                2, retired_guard=retired_guard, resource_gate=resource_gate,event_gate=event_gate,
                messages=messages)
            if all(process.read(base+site, 4) == (
                    0x48000000 | ((data+candidate_labels[f'apJoin{i}']-site)&0x03fffffc)
                    ).to_bytes(4, 'big')
                    for i, (site, *_) in enumerate(join_sites, 1)):
                labels, size = candidate_labels, candidate_size
                result.update(extension_size=size, retired_executor_guard=retired_guard)
                break
        else:
            raise ValueError('Native finish hook layout missing/conflicting')
        for i,(site,original,*_) in enumerate(join_sites,1):
            target=data+labels[f'apJoin{i}']
            raw=process.read(base+site,4)
            if raw is None or int.from_bytes(raw,'big') != (0x48000000|((target-site)&0x03fffffc)):
                raise ValueError('Native finish hook missing')
            replay=data+labels[f'apJoin{i}Done']+32
            prologue = bytes.fromhex('9421fff0' if messages else '9421ffe0')
            if process.read(base+target,4)!=prologue or process.read(base+replay,4)!=original.to_bytes(4,'big'):
                raise ValueError('Native finish hook signature mismatch')
            if messages:
                kind = ('Created', 'Terminal', 'Manager', 'Retired')[i-1]
                callback = data + labels['apMessageExecutor' + kind]
                call = 0x48000001 | ((callback - (target + 16)) & 0x03fffffc)
                expected = struct.pack('>10I', 0x9421fff0, 0x90010008, 0x7c0802a6,
                    0x9001000c, call, 0x8001000c, 0x7c0803a6, 0x80010008, 0x38210010, 0x9421ffe0)
                if process.read(base+target, 40) != expected:
                    raise ValueError('Shared message observer dispatcher mismatch')
        result['join_address']=data+labels['apJoinData']
        result['join']=read_join(process,base,result['join_address'])
    if messages:
        from tools.build_message_action import SITES as message_sites
        for site, original, name, replay in message_sites:
            target = data + labels['apMessage' + name]
            expected = (0x48000000 | ((target-site) & 0x03fffffc)).to_bytes(4, 'big')
            prefix = ((original.to_bytes(4, 'big') if replay else b'') + bytes.fromhex('9421ffe0'))
            if (process.read(base+site, 4) != expected or process.read(base+target, len(prefix)) != prefix):
                raise ValueError('Native message action hook mismatch')
        result['message'] = {name: data + labels['apMessage' + suffix] for name, suffix in
            (('address','Data'), ('join_address','JoinData'), ('submit','Submit'),
             ('inbox','Inbox'), ('inbox_units','InboxUnits'))}
        if process.read(base + result['message']['address'], 8) != struct.pack('>2I', 0x41504d41, 1):
            raise ValueError('Native message signature mismatch')
        if process.read(base + result['message']['submit'], 16) != bytes.fromhex('9421ffe07c0802a69001002493e1001c'):
            raise ValueError('Message submit prologue mismatch')
    return result


def read_join(process,base,address):
    raw=process.read(base+address,32)
    if raw is None or len(raw)!=32 or raw!=process.read(base+address,32):
        raise RuntimeError('Native join snapshot incomplete/changing')
    values=struct.unpack('>8I',raw)
    if values[:2]!=(0x41504a4e,1):
        raise ValueError('Native join signature mismatch')
    return dict(zip(('generation','executor','terminal_generation','manager_generation','retired_generation','ack_generation'),values[2:]))


def finished(state,join):
    generation=state['generation']
    return (state.get('version')==2 and state['phase']=='finished' and released(state)
        and join.get('executor',0)!=0 and all(join.get(k)==generation for k in
            ('generation','terminal_generation','manager_generation','retired_generation','ack_generation')))


def released(state):
    generation = state["generation"]
    return (state["phase"] in ("released","finished") and generation > 0 and not state["fault"] and not state["busy"]
            and all(state[key] == generation for key in
                    ("bound_generation", "completed_generation", "left_generation")))


def request(process, cave, owner, title, description, ready, checkpoint, timeout=3, *, resolution_quota=2):
    with publisher_lock(process.pid):
        return _request(process, cave, owner, title, description, ready, checkpoint, timeout,
                        resolution_quota=resolution_quota)


def _request(process, cave, owner, title, description, ready, checkpoint, timeout=3, *, resolution_quota=2):
    """Publish once after a caller-supplied full readiness guard.

    `ready` must cover the experimental gameplay/UI/protection guard. The test
    runner supplies that adapter; this is not enabled in the production client.
    No Python cleanup after dispatch: an unknown call must never be replayed.
    """
    from tools.cemu.autonomous_eventflow import inspect as inspect_wrapper
    from tools.cemu.mailbox import Cave
    # All validation before any mailbox write.
    title_data, title_len, _ = Cave._sub_payload(title, 256, 0)
    desc_data, desc_len, _ = Cave._sub_payload(description, 512, 0)
    if type(resolution_quota) is not int or resolution_quota not in (2, 4):
        raise ValueError("Only normal quota2 or laboratory cleanup probe4 is supported")
    state = read(process, cave.base, owner["address"])
    available=(finished(state,read_join(process,cave.base,owner['join_address'])) if state.get('version')==2 else released(state))
    if (state["busy"] or state["fault"] or state["generation"] == 0xFFFFFFFF
            or not (state["phase"] in ("idle", "refused") or available)):
        raise RuntimeError("Owner pending/uncertain: no new request")
    if not inspect_wrapper(process, cave.base)["manager_available"] or not ready():
        raise RuntimeError("Gameplay/UI/protections not ready")
    def word(address):
        raw = process.read(address, 4)
        if raw is None or len(raw) != 4:
            raise RuntimeError("short mailbox read")
        return int.from_bytes(raw, "big")
    if not cave.pf_ready() or not cave.ui_ready() or word(cave.pf_req) or word(cave.opn_req):
        raise RuntimeError("Invoker unavailable or pending")
    title_pending, _, desc_pending, _, auto = cave.sub_state()
    if title_pending or desc_pending or auto:
        raise RuntimeError("Existing text quota")
    before_generation = state["generation"]
    generation = before_generation + 1
    result = dict(status="prepared", generation=generation, title=title, description=description,
                  owner_before=state, text_armed_by_python=False, resolution_quota=resolution_quota)
    checkpoint(result)
    def write(address, raw):
        if not process.write(address, raw):
            raise RuntimeError("Owner mailbox write failed; no automatic retry")
    for address, raw in ((cave.sub_buf, title_data), (cave.sub_len, title_len),
                         (cave.sub_desc_buf, desc_data), (cave.sub_desc_len, desc_len),
                         (cave.call_addr, struct.pack(">I", owner["submit"])),
                         (cave.base + owner["address"] + 40, struct.pack(">I", resolution_quota))):
        write(address, raw)
    before = word(cave.call_n)
    # Fixed native arguments; no shared Python flow/entry strings to race.
    write(cave.base + owner["address"] + 8, struct.pack(">I", 1))
    result["status"] = "dispatching"
    checkpoint(result)
    write(cave.pf_req, struct.pack(">I", 1))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = read(process, cave.base, owner["address"])
        if word(cave.call_n) != before:
            result.update(owner_after=state, native_return=word(cave.call_ret))
            valid = state["generation"] == generation and not state["fault"] and not state["busy"]
            deferred_text = cave.sub_state()
            deferred = (state["generation"] == before_generation
                        and state["phase"] == "idle" and not state["fault"]
                        and not state["busy"] and result["native_return"] == 2
                        and not any((deferred_text[0], deferred_text[2], deferred_text[4])))
            if deferred:
                result.update(status="deferred", generation=before_generation,
                              reason="native presentation resource not ready; wrapper not called")
            elif valid and state["phase"] == "refused" and result["native_return"] == 0:
                result["status"] = "refused"
            elif valid and state["phase"] in ("accepted", "bound", "action_complete", "released", "finished") and result["native_return"] == 1:
                result["status"] = "accepted"
            else:
                result["status"] = "uncertain"
            checkpoint(result)
            return result
        time.sleep(0.01)
    result.update(status="uncertain", owner_after=read(process, cave.base, owner["address"]),
                  reason="acknowledgement timeout; no cancellation or retry")
    checkpoint(result)
    return result
