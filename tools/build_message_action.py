"""Uninstalled native dialogue stage; companion integration is still missing.

Requires an executor owner to stage a generation before binding. Phase 4 means
action leave, NEVER permission to reuse the text buffer or deliver another item.
"""
from botw_patch.message_flow import MARKER
from tools.build_owned_presentation import ints, lock, unlock
from tools.cemu.guest import MEM2_END, below

# All replaced instructions are non-linking except the leaf return, which is
# replayed as a return after instrumentation. No existing AP hook is replaced.
SITES = (
    (0x02346D50, 0x9361001C, 'Bind', 'stw r27, 28(r1)'),
    (0x035FB658, 0x811F0004, 'Text', 'lwz r8, 4(r31)'),
    (0x02346DEC, 0x7FE3FB78, 'Complete', 'mr r3, r31'),
    (0x02346E08, 0x4E800020, 'Leave', None),
)


def pointer(label, reg):
    return [f'lis r{reg}, {label}@ha', f'addi r{reg}, r{reg}, {label}@l']


def source():
    from tools.message_event_join import callbacks, finish
    # Header: magic/version/phase/generation/action/executor/bound/completed/
    # left/screen/text_units/reserved/lock/fault/text_generation/reserved.
    # phase: idle0, staged1, bound2, completed3, left4, uncertain8.
    lines = ['[BOTW_AP_MessageAction_V208]', 'moduleMatches = 0x6267BFD0',
        '.origin = codecave', 'apMessageData:', '.int 0x41504d41', '.int 1'] + ['.int 0'] * 14
    for label, text in [('Arc', 'DemoMsg/Demo008_2'), ('Label', 'talk00')]:
        lines += [f'apMessage{label}:'] + ints(text.encode() + b'\0')
        lines += [f'apMessage{label}Safe:', f'.int apMessage{label}', '.int 0x10263910']
    # Not apMessageText: that is the label of the Text hook below (Cemu refused
    # the pack: "Label apMessageText is already defined").
    lines += ['apMessageTextBuffer:'] + ['.int 0'] * 1024
    for site, word, kind, replay in SITES:
        label = 'apMessage' + kind
        lines += [label + ':'] + ([replay] if replay else [])
        lines += ['stwu r1, -32(r1)', 'stw r0, 8(r1)', 'stw r9, 12(r1)',
            'stw r10, 16(r1)', 'stw r11, 20(r1)', 'stw r12, 24(r1)',
            '.int 0x7c000026', 'stw r0, 28(r1)'] + pointer('apMessageData', 11)
        if kind == 'Bind':
            lines += ['lwz r12, 16(r26)', 'lis r10, 0x0100', 'cmplw r12, r10',
                f'blt {label}Done', *below(MEM2_END, 'r12', 'r10', f'{label}Done', margin=0x40)]
            for i, byte in enumerate(MARKER.encode() + b'\0'):
                lines += [f'lbz r0, {i}(r12)', f'cmpwi r0, {byte}', f'bne {label}Done']
            # Resolve a known vanilla carrier even when no request is armed.
            # Only this private marker changes arguments; ordinary dialogs pass.
            lines += pointer('apMessageArcSafe', 4) + pointer('apMessageLabelSafe', 5)
        elif kind == 'Text':
            # Both SafeString object identities must be ours, not merely equal
            # archive/label text. They are forwarded unchanged by 035ff8fc.
            for reg, name in [(31, 'Arc'), (26, 'Label')]:
                lines += pointer('apMessage' + name + 'Safe', 10)
                lines += [f'cmpw r{reg}, r10', f'bne {label}Done']
        else:
            reg = 31 if kind == 'Complete' else 3
            lines += ['lwz r0, 16(r11)', f'cmpw r0, r{reg}', f'bne {label}Done']
        lines += lock(11, label + 'Busy')
        lines += ['lwz r0, 52(r11)', 'cmpwi r0, 0', f'bne {label}Unlock',
            'lwz r9, 12(r11)', 'cmpwi r9, 0', f'beq {label}Unlock',
            'lwz r0, 20(r11)', 'cmpwi r0, 0', f'beq {label}Unlock',
            'lwz r0, 8(r11)']
        expected = {'Bind': 1, 'Text': 2, 'Complete': 2, 'Leave': 3}[kind]
        if kind in ('Complete', 'Leave'):
            lines += ['cmpwi r0, 9', f'bne {label}Unfinished']
            lines += pointer('apMessageJoinData', 10)
            lines += ['lwz r0, 12(r10)', 'cmpw r0, r9', f'beq {label}Unlock',
                f'b {label}Fault', label + 'Unfinished:']
        lines += [f'cmpwi r0, {expected}', f'bne {label}Fault']
        if kind == 'Bind':
            lines += ['lwz r0, 16(r11)', 'cmpwi r0, 0', f'bne {label}Fault',
                'stw r26, 16(r11)', 'stw r9, 24(r11)', 'li r0, 2']
        else:
            lines += ['lwz r0, 24(r11)', 'cmpw r0, r9', f'bne {label}Fault']
            if kind == 'Text':
                lines += ['lwz r0, 56(r11)', 'cmpwi r0, 0', f'bne {label}Fault',
                    'lwz r0, 40(r11)', 'cmplwi r0, 2048', f'bge {label}Fault']
                lines += pointer('apMessageTextBuffer', 10)
                lines += ['stw r10, 464(r27)', 'stw r0, 468(r27)',
                    'stw r27, 36(r11)', 'stw r9, 56(r11)', f'b {label}Unlock']
            else:
                reg = 31 if kind == 'Complete' else 3
                lines += ['lwz r0, 16(r11)', f'cmpw r0, r{reg}', f'bne {label}Fault']
                lines += ['lwz r0, 56(r11)', 'cmpw r0, r9', f'bne {label}Fault']
                if kind == 'Leave':
                    lines += ['lwz r0, 28(r11)', 'cmpw r0, r9', f'bne {label}Fault']
                lines += [f'stw r9, {28 if kind == "Complete" else 32}(r11)',
                          f'li r0, {3 if kind == "Complete" else 4}']
        if kind != 'Text':
            lines += ['.int 0x7c0004ac', 'stw r0, 8(r11)']
        if kind == 'Leave':
            lines += finish(label + 'Unlock')
        lines += [f'b {label}Unlock', label + 'Fault:', 'li r0, 1', 'stw r0, 52(r11)',
            'li r0, 8', '.int 0x7c0004ac', 'stw r0, 8(r11)', label + 'Unlock:']
        lines += unlock(11) + [f'b {label}Done', label + 'Busy:',
            'li r0, 1', 'stw r0, 52(r11)', label + 'Done:',
            'lwz r0, 28(r1)', '.int 0x7c0ff120', 'lwz r0, 8(r1)',
            'lwz r9, 12(r1)', 'lwz r10, 16(r1)', 'lwz r11, 20(r1)',
            'lwz r12, 24(r1)', 'addi r1, r1, 32',
            'blr' if kind == 'Leave' else f'b 0x{site+4:08x}',
            f'0x{site:08x} = b {label}']
    return '\n'.join(lines) + '\n' + callbacks()


def compose_executor_hooks(item_source):
    """Chain dialogue observers at the existing owner hooks, exactly once.

    This only composes observers. message_submission.compose_submission adds
    native admission; the companion adapter is required before activation.
    """
    if 'apMessageData:' in item_source:
        raise ValueError('Message observer already composed')
    kinds = ('Created', 'Terminal', 'Manager', 'Retired')
    for i, kind in enumerate(kinds, 1):
        anchor = f'apJoin{i}:\n'
        if item_source.count(anchor) != 1:
            raise ValueError(f'Expected one existing executor hook: apJoin{i}')
    for i, kind in enumerate(kinds, 1):
        anchor = f'apJoin{i}:\n'
        # The original join preserves r0 and CR but did not need LR storage.
        # Wrap our call before it without changing its original register view.
        wrapper = ['stwu r1, -16(r1)', 'stw r0, 8(r1)', 'mflr r0',
            'stw r0, 12(r1)', f'bl apMessageExecutor{kind}',
            'lwz r0, 12(r1)', 'mtlr r0', 'lwz r0, 8(r1)', 'addi r1, r1, 16']
        item_source = item_source.replace(anchor, anchor + '\n'.join(wrapper) + '\n', 1)
    # Share the codecave/group of the existing patch; no second patch directive
    # for the four executor sites. Message action sites are distinct.
    return item_source + '\n' + '\n'.join(source().splitlines()[3:]) + '\n'
