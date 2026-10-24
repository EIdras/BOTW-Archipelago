"""Native join of executor retirement and action leave, under the owner lock."""
from tools.build_event_end_trace import SITES
from tools.cemu.guest import MEM2_END, below


def pointer(label, reg=10):
    return [f'lis r{reg}, {label}@ha', f'addi r{reg}, r{reg}, {label}@l']


def finish(label):
    # Called while holding the owner lock, r11=owner. Both orders are valid.
    lines=pointer('apJoinData')
    lines += ['lwz r0, 8(r11)','cmpwi r0, 6',f'bne {label}',
              'lwz r9, 12(r11)','cmpwi r9, 0',f'beq {label}']
    for offset in (24,28,32):
        lines += [f'lwz r0, {offset}(r11)','cmpw r0, r9',f'bne {label}']
    for offset in (8,16,20,24):
        lines += [f'lwz r0, {offset}(r10)','cmpw r0, r9',f'bne {label}']
    lines += ['stw r9, 28(r10)','li r0, 9','.int 0x7c0004ac','stw r0, 8(r11)']
    return lines


def extend(source, *, retired_guard=False, mem2_end=MEM2_END):
    from tools.build_owned_presentation import lock, unlock, clear_text, phase
    source=source.replace('.int 0x41504f57\n.int 1', '.int 0x41504f57\n.int 2',1)
    anchor='lwz r9, 12(r31)\ncmpwi r9, -1'
    # A staged request cannot overwrite a prior unacknowledged generation.
    guard=pointer('apJoinData')+['lwz r9, 12(r31)','cmpwi r9, 0','beq apJoinFirst',
        'lwz r0, 28(r10)','cmpw r0, r9','beq apJoinFirst',
        'lwz r0, 20(r31)','cmpwi r0, 0','bne apOwnedBadStage',
        'lwz r0, 12(r10)','cmpwi r0, 0','bne apOwnedBadStage','apJoinFirst:']
    source=source.replace(anchor,'\n'.join(guard)+'\n'+anchor,1)
    anchor='stw r9, 12(r31)\nli r0, 0'
    initialize=pointer('apJoinData')+['stw r9, 8(r10)','li r0, 0']
    initialize += [f'stw r0, {offset}(r10)' for offset in (12,16,20,24,28)]
    source=source.replace(anchor,'stw r9, 12(r31)\n'+'\n'.join(initialize)+'\nli r0, 0',1)
    anchor='stw r0, 8(r11)\nb apOwnedLeaveUnlock\napOwnedLeaveAborted:'
    if source.count(anchor)!=1:
        raise ValueError('Owner leave join anchor mismatch')
    source=source.replace(anchor,'stw r0, 8(r11)\n'+'\n'.join(finish('apOwnedLeaveUnlock'))+
        '\nb apOwnedLeaveUnlock\napOwnedLeaveAborted:',1)
    lines=['apJoinData:','.int 0x41504a4e','.int 1']+['.int 0']*6
    for i,(site,original,name,*_) in enumerate(SITES,1):
        label=f'apJoin{i}'
        # Original instruction runs AFTER instrumentation, preserving the
        # constructor result r3 and the slot pointer r11 while inspecting.
        lines += [label+':','stwu r1, -32(r1)','stw r0, 8(r1)','stw r9, 12(r1)',
            'stw r10, 16(r1)','stw r11, 20(r1)','stw r12, 24(r1)',
            '.int 0x7c000026','stw r0, 28(r1)'] + pointer('apOwnedData',11)
        if i==1:
            lines += ['cmpwi r3, 0',f'beq {label}Done']
            for offset,text in ((0x24,'Demo007_1'),(0x70,'APDisplayStandalone')):
                lines += [f'lwz r12, {offset}(r30)','lis r0, 0x0100','cmplw r12, r0',f'blt {label}Done',
                    *below(mem2_end, 'r12', 'r0', f'{label}Done', margin=0x40)]
                for n,byte in enumerate(text.encode()+b'\0'):
                    lines += [f'lbz r0, {n}(r12)',f'cmpwi r0, {byte}',f'bne {label}Done']
        else:
            lines += pointer('apJoinData')+['lwz r0, 12(r10)','cmpw r0, r30',f'bne {label}Done']
            if i==2:
                lines += ['cmpwi r26, 0',f'beq {label}Done']
        lines += lock(11,label+'Busy')
        lines += ['lwz r0, 52(r11)','cmpwi r0, 0',f'bne {label}Unlock']+pointer('apJoinData')
        lines += ['lwz r9, 12(r11)','cmpwi r9, 0',f'beq {label}Unlock',
            'lwz r0, 8(r10)','cmpw r0, r9',f'bne {label}Fail']
        if i==1:
            lines += ['lwz r0, 12(r10)','cmpwi r0, 0',f'bne {label}Fail',
                'lwz r0, 8(r11)','cmpwi r0, 2',f'beq {label}Claim',
                'cmpwi r0, 3',f'bne {label}Fail',label+'Claim:','stw r3, 12(r10)']
        else:
            if retired_guard:
                # The freed executor address can immediately be reused by a
                # delivery/vanilla event. A fully acknowledged generation owns
                # no subsequent callbacks at that address. Preserve its ACK.
                lines += ['lwz r0, 8(r11)', 'cmpwi r0, 9',
                    f'bne {label}Unfinished', 'lwz r0, 28(r10)',
                    'cmpw r0, r9', f'bne {label}Fail', f'b {label}Unlock',
                    label+'Unfinished:']
            lines += ['lwz r0, 12(r10)','cmpw r0, r30',f'bne {label}Unlock',
                'lwz r0, 8(r11)','cmpwi r0, 5',f'beq {label}Active',
                'cmpwi r0, 6',f'bne {label}Fail',label+'Active:']
            for offset in (24,32):
                lines += [f'lwz r0, {offset}(r11)','cmpw r0, r9',f'bne {label}Fail']
            if i==2:
                lines += ['cmpwi r26, 1',f'bne {label}Fail','lwz r0, 0x18c(r30)',
                    'cmpwi r0, 0',f'bne {label}Fail','lwz r0, 16(r10)','cmpwi r0, 0',
                    f'bne {label}Fail','stw r9, 16(r10)']
            elif i==3:
                lines += ['lwz r0, 16(r10)','cmpw r0, r9',f'bne {label}Fail',
                    'lwz r0, 0x18c(r30)','cmpwi r0, 0',f'bne {label}Fail','stw r9, 20(r10)']
            else:
                # No read through r30: object was freed. Original r11 is the slot.
                lines += ['lwz r0, 20(r10)','cmpw r0, r9',f'bne {label}Fail',
                    'lwz r12, 20(r1)','lwz r0, 0(r12)','cmpwi r0, 0',f'bne {label}Fail',
                    'stw r9, 24(r10)']+finish(label+'Unlock')
        lines += [f'b {label}Unlock',label+'Fail:','li r0, 1','stw r0, 52(r11)']
        lines += clear_text()+phase(11,8)+[label+'Unlock:']+unlock(11)+[f'b {label}Done',
            label+'Busy:','li r0, 1','stw r0, 52(r11)',label+'Done:',
            'lwz r0, 28(r1)','.int 0x7c0ff120','lwz r0, 8(r1)','lwz r9, 12(r1)',
            'lwz r10, 16(r1)','lwz r11, 20(r1)','lwz r12, 24(r1)','addi r1, r1, 32',
            f'.int 0x{original:08x}',f'b 0x{site+4:08x}',f'0x{site:08x} = b {label}']
    return source+'\n'+'\n'.join(lines)+'\n'
