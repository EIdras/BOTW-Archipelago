"""Dialogue executor callbacks for future shared-hook composition.

These are callable instrumentation routines, NOT patches at the executor sites:
the item owner already hooks those sites. compose_executor_hooks chains both
observers while preserving the original register/LR view. Submission admission
is composed by message_submission; companion integration remains required.
"""
from botw_patch.message_flow import FLOW, ENTRY
from tools.build_owned_presentation import lock, unlock


def pointer(label, reg=10):
    return [f'lis r{reg}, {label}@ha', f'addi r{reg}, r{reg}, {label}@l']


def finish(end):
    # Owner lock held, r11=message owner; r9/r10/r0 are scratch.
    lines = ['lwz r0, 8(r11)', 'cmpwi r0, 4', f'bne {end}',
        'lwz r9, 12(r11)', 'cmpwi r9, 0', f'beq {end}']
    for offset in (24, 28, 32, 56):
        lines += [f'lwz r0, {offset}(r11)', 'cmpw r0, r9', f'bne {end}']
    lines += pointer('apMessageJoinData')
    for offset in (0, 4, 8):
        lines += [f'lwz r0, {offset}(r10)', 'cmpw r0, r9', f'bne {end}']
    return lines + ['stw r9, 12(r10)', 'li r0, 9', '.int 0x7c0004ac', 'stw r0, 8(r11)']


def callbacks():
    lines = ['apMessageJoinData:'] + ['.int 0'] * 4
    for kind in ('Created', 'Terminal', 'Manager', 'Retired'):
        label = 'apMessageExecutor' + kind
        lines += [label + ':', 'stwu r1, -32(r1)', 'stw r0, 8(r1)',
            'stw r9, 12(r1)', 'stw r10, 16(r1)', 'stw r11, 20(r1)', 'stw r12, 24(r1)',
            '.int 0x7c000026', 'stw r0, 28(r1)'] + pointer('apMessageData', 11)
        if kind == 'Created':
            lines += ['cmpwi r3, 0', f'beq {label}Done']
            for offset, text in ((0x24, FLOW), (0x70, ENTRY)):
                lines += [f'lwz r12, {offset}(r30)', 'lis r0, 0x0100', 'cmplw r12, r0',
                    f'blt {label}Done', 'lis r0, 0x5fff', 'ori r0, r0, 0xffc0',
                    'cmplw r12, r0', f'bge {label}Done']
                for i, byte in enumerate(text.encode() + b'\0'):
                    lines += [f'lbz r0, {i}(r12)', f'cmpwi r0, {byte}', f'bne {label}Done']
        else:
            lines += ['lwz r0, 20(r11)', 'cmpw r0, r30', f'bne {label}Done']
            if kind == 'Terminal':
                lines += ['cmpwi r26, 0', f'beq {label}Done']
        lines += lock(11, label + 'Busy')
        lines += ['lwz r0, 52(r11)', 'cmpwi r0, 0', f'bne {label}Unlock',
            'lwz r9, 12(r11)', 'cmpwi r9, 0', f'beq {label}Unlock']
        lines += pointer('apMessageJoinData')
        if kind == 'Created':
            lines += ['lwz r0, 8(r11)', 'cmpwi r0, 1', f'bne {label}Fault',
                'lwz r0, 20(r11)', 'cmpwi r0, 0', f'bne {label}Fault',
                'stw r3, 20(r11)', f'b {label}Unlock']
        else:
            lines += ['lwz r0, 20(r11)', 'cmpw r0, r30', f'bne {label}Unlock',
                'lwz r0, 8(r11)', 'cmpwi r0, 9', f'bne {label}Active',
                'lwz r0, 12(r10)', 'cmpw r0, r9', f'beq {label}Unlock', f'b {label}Fault',
                label + 'Active:', 'cmpwi r0, 3', f'beq {label}Completed',
                'cmpwi r0, 4', f'bne {label}Fault', label + 'Completed:']
            for offset in (24, 28, 56):
                lines += [f'lwz r0, {offset}(r11)', 'cmpw r0, r9', f'bne {label}Fault']
            if kind == 'Terminal':
                lines += ['cmpwi r26, 1', f'bne {label}Fault',
                    'lwz r0, 0x18c(r30)', 'cmpwi r0, 0', f'bne {label}Fault',
                    'lwz r0, 0(r10)', 'cmpwi r0, 0', f'bne {label}Fault', 'stw r9, 0(r10)']
            elif kind == 'Manager':
                lines += ['lwz r0, 0(r10)', 'cmpw r0, r9', f'bne {label}Fault',
                    'lwz r0, 0x18c(r30)', 'cmpwi r0, 0', f'bne {label}Fault', 'stw r9, 4(r10)']
            else:
                # r30 is already freed: only read the original manager slot r11.
                lines += ['lwz r0, 4(r10)', 'cmpw r0, r9', f'bne {label}Fault',
                    'lwz r12, 20(r1)', 'lwz r0, 0(r12)', 'cmpwi r0, 0',
                    f'bne {label}Fault', 'stw r9, 8(r10)'] + finish(label + 'Unlock')
            lines += [f'b {label}Unlock']
        lines += [label + 'Fault:', 'li r0, 1', 'stw r0, 52(r11)', 'li r0, 8',
            '.int 0x7c0004ac', 'stw r0, 8(r11)', label + 'Unlock:']
        lines += unlock(11) + [f'b {label}Done', label + 'Busy:', 'li r0, 1',
            'stw r0, 52(r11)', label + 'Done:', 'lwz r0, 28(r1)', '.int 0x7c0ff120',
            'lwz r0, 8(r1)', 'lwz r9, 12(r1)', 'lwz r10, 16(r1)', 'lwz r11, 20(r1)',
            'lwz r12, 24(r1)', 'addi r1, r1, 32', 'blr']
    return '\n'.join(lines) + '\n'
