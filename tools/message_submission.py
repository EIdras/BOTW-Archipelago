"""Native submission and two-channel admission, not enabled by the play builder.

Lock order is always item owner then message owner. Locks are released before
calling the engine, after publishing the active message phase. Input text has
its own inbox; the screen's buffer is copied only after admission succeeds.
"""
from botw_patch.message_flow import FLOW, ENTRY
from tools.build_owned_presentation import ints, lock, unlock, resource_ready_guard
from tools.build_message_action import pointer


def item_gate():
    lines = pointer('apMessageData', 11) + lock(11, 'apOwnedDeferred')
    lines += ['lwz r0, 52(r11)', 'cmpwi r0, 0', 'bne apItemMessageBusy',
        'lwz r0, 8(r11)', 'cmpwi r0, 0', 'beq apItemMessageReady',
        'cmpwi r0, 7', 'beq apItemMessageReady',
        'cmpwi r0, 9', 'bne apItemMessageBusy', 'lwz r9, 12(r11)']
    lines += pointer('apMessageJoinData', 10)
    lines += ['lwz r0, 12(r10)', 'cmpw r0, r9', 'bne apItemMessageBusy',
        'apItemMessageReady:'] + unlock(11) + ['b apItemMessageGateEnd', 'apItemMessageBusy:']
    return lines + unlock(11) + ['b apOwnedDeferred', 'apItemMessageGateEnd:']


def submission_source():
    lines = ['apMessageInboxUnits:', '.int 0', 'apMessageInbox:'] + ['.int 0'] * 1024
    for label, value in [('Flow', FLOW), ('Entry', ENTRY)]:
        lines += [f'apMessage{label}:'] + ints(value.encode() + b'\0')
        lines += [f'apMessage{label}Safe:', f'.int apMessage{label}', '.int 0x10263910']
    lines += ['apMessageSubmit:', 'stwu r1, -32(r1)', 'mflr r0', 'stw r0, 36(r1)',
        'stw r31, 28(r1)'] + pointer('apOwnedData', 11)
    lines += lock(11, 'apMessageSubmitContended')
    # Pending/staged items have priority; no message is started alongside them.
    lines += ['lwz r0, 52(r11)', 'cmpwi r0, 0', 'bne apMessageItemBusy',
        'lwz r0, 8(r11)', 'cmpwi r0, 0', 'beq apMessageItemReady',
        'cmpwi r0, 9', 'bne apMessageItemBusy', 'lwz r9, 12(r11)']
    lines += pointer('apJoinData', 10)
    lines += ['lwz r0, 28(r10)', 'cmpw r0, r9', 'bne apMessageItemBusy',
        'apMessageItemReady:'] + pointer('apMessageData', 31)
    lines += lock(31, 'apMessageItemBusy')
    lines += ['lwz r0, 52(r31)', 'cmpwi r0, 0', 'bne apMessageSubmitInvalid',
        'lwz r0, 8(r31)', 'cmpwi r0, 0', 'beq apMessageCanStage',
        'cmpwi r0, 7', 'beq apMessageCanStage', 'cmpwi r0, 9',
        'bne apMessageSubmitInvalid', 'lwz r9, 12(r31)']
    lines += pointer('apMessageJoinData', 10)
    lines += ['lwz r0, 12(r10)', 'cmpw r0, r9', 'bne apMessageSubmitInvalid',
        'apMessageCanStage:'] + pointer('apMessageInboxUnits', 10)
    lines += ['lwz r0, 0(r10)', 'cmpwi r0, 0', 'beq apMessageSubmitInvalid',
        'cmplwi r0, 2048', 'bge apMessageSubmitInvalid',
        'stw r0, 24(r1)',
        'lwz r9, 12(r31)', 'cmpwi r9, -1', 'beq apMessageSubmitInvalid']
    lines += [line.replace('apOwnedDeferred', 'apMessageSubmitDeferred')
              for line in resource_ready_guard(event_gate=True)]
    # Calls in the resource gate may clobber volatile registers. Reload all.
    lines += ['lwz r9, 12(r31)', 'addi r9, r9, 1', 'stw r9, 12(r31)', 'li r0, 0']
    for offset in (16, 20, 24, 28, 32, 36, 56, 60):
        lines += [f'stw r0, {offset}(r31)']
    lines += pointer('apMessageJoinData', 10)
    lines += [f'stw r0, {offset}(r10)' for offset in (0, 4, 8, 12)]
    lines += ['li r0, -1', 'stw r0, 44(r31)',
        'lwz r9, 24(r1)', 'stw r9, 40(r31)', 'slwi r9, r9, 1']
    lines += pointer('apMessageInbox', 10) + pointer('apMessageTextBuffer', 12)
    lines += ['apMessageCopy:', 'lbz r0, 0(r10)', 'stb r0, 0(r12)',
        'addi r10, r10, 1', 'addi r12, r12, 1', 'addi r9, r9, -1',
        'cmpwi r9, 0', 'bne apMessageCopy', 'li r0, 0', 'stb r0, 0(r12)', 'stb r0, 1(r12)',
        'li r0, 1', '.int 0x7c0004ac', 'stw r0, 8(r31)']
    lines += unlock(31) + pointer('apOwnedData', 11) + unlock(11)
    lines += ['li r3, 0'] + pointer('apMessageFlowSafe', 4) + pointer('apMessageEntrySafe', 5)
    lines += ['li r6, 1', 'li r7, 0', 'bl 0x02ddf744']
    lines += lock(31, 'apMessageSubmitUncertainBusy')
    lines += ['stw r3, 44(r31)', 'lwz r0, 52(r31)', 'cmpwi r0, 0',
        'bne apMessageSubmitUncertain', 'cmpwi r3, 1', 'beq apMessageReturnOneLock',
        'cmpwi r3, 0', 'bne apMessageSubmitUncertain',
        'lwz r0, 8(r31)', 'cmpwi r0, 1', 'bne apMessageSubmitUncertain']
    for offset in (16, 20, 24, 28, 32, 36, 56):
        lines += [f'lwz r0, {offset}(r31)', 'cmpwi r0, 0', 'bne apMessageSubmitUncertain']
    lines += ['li r0, 7', '.int 0x7c0004ac', 'stw r0, 8(r31)', 'b apMessageReturnOneLock',
        'apMessageSubmitUncertain:', 'li r0, 1', 'stw r0, 52(r31)', 'li r0, 8',
        '.int 0x7c0004ac', 'stw r0, 8(r31)', 'li r3, -1',
        'apMessageReturnOneLock:'] + unlock(31) + ['b apMessageSubmitReturn',
        'apMessageSubmitUncertainBusy:', 'li r0, 1', 'stw r0, 52(r31)',
        'li r3, -1', 'b apMessageSubmitReturn',
        'apMessageSubmitInvalid:', 'li r3, -1', 'b apMessageReturnBothLocks',
        'apMessageSubmitDeferred:', 'li r3, 2', 'apMessageReturnBothLocks:']
    lines += unlock(31) + pointer('apOwnedData', 11) + unlock(11) + ['b apMessageSubmitReturn',
        'apMessageItemBusy:'] + pointer('apOwnedData', 11) + unlock(11)
    lines += ['apMessageSubmitContended:', 'li r3, 2', 'apMessageSubmitReturn:',
        'lwz r31, 28(r1)', 'lwz r0, 36(r1)', 'mtlr r0', 'addi r1, r1, 32', 'blr']
    return '\n'.join(lines) + '\n'


def compose_submission(native):
    anchor = 'apOwnedQuotaValid:\n'
    if native.count(anchor) != 1 or 'apOwnedDeferred:' not in native or 'apMessageData:' not in native:
        raise ValueError('Expected guarded item owner and composed message observer')
    if 'apMessageSubmit:' in native:
        raise ValueError('Message submission already composed')
    return native.replace(anchor, anchor + '\n'.join(item_gate()) + '\n', 1) + submission_source()


def build(output):
    """Emit an immutable, uninstalled native component; no resource/profile writes."""
    import re
    from pathlib import Path
    from tools.build_message_action import SITES, compose_executor_hooks
    from tools.build_native_from_source import ROOT, RPX_SHA256, generate, digest, encode, SOURCE_FILES
    from tools.cemu.rpx import Rpx
    if digest((ROOT / 'U-King.rpx').read_bytes()) != RPX_SHA256:
        raise ValueError('Unsupported RPX for native message stage')
    rpx = Rpx()
    for site, expected, _, _ in SITES:
        if rpx.read(site, 4) != expected.to_bytes(4, 'big'):
            raise ValueError(f'Unexpected message hook instruction: {site:#x}')
    files = generate(resource_gate=True, event_gate=True)
    name = 'runtime/patch_apInject.asm'
    files[name] = compose_submission(compose_executor_hooks(files[name].decode())).encode()
    sites = {}
    for name, raw in files.items():
        for site in re.findall(r'^\s*(0x[0-9a-fA-F]+)\s*=', raw.decode(), re.M):
            address = int(site, 16)
            if address in sites:
                raise ValueError(f'Conflicting native hook at {site}: {sites[address]} and {name}')
            sites[address] = name
    sources = (*SOURCE_FILES, 'tools/build_message_action.py', 'tools/message_event_join.py',
               'tools/message_submission.py', 'botw_patch/message_flow.py')
    manifest = dict(component='experimental_native_messages', installed=False,
        runtime_ready=False, rpx_sha256=RPX_SHA256,
        files={name: digest(raw) for name, raw in files.items()},
        sources={name: digest((ROOT / name).read_bytes()) for name in sources},
        requires=['client layout recognition and durable message adapter',
                  'composition with current resources, seed binding and RSTB',
                  'Cemu assembly/load and gameplay validation'],
        verification='RPX anchors and hook conflicts checked; not assembled by Cemu')
    encoded = encode(manifest)
    target = Path(output).resolve() / digest(encoded)[:16]
    files['manifest.json'] = encoded
    if target.exists():
        if {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()} != set(files):
            raise ValueError('Native message component file list changed')
        for name, raw in files.items():
            if (target / name).read_bytes() != raw:
                raise ValueError('Immutable native message component changed')
        return target
    for name, raw in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return target


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='.build/message-native')
    print(build(parser.parse_args().output))
