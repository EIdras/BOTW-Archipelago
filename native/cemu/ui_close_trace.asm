[BOTW_AP_UICloseTrace_V208]
moduleMatches = 0x6267BFD0

; Diagnostic only. 0x035ff004 dispatches screen 0x0b's close method.
; Preserve arguments, r0, r11, LR, CR and XER. r12 is overwritten by the
; original first instruction, replayed before returning. No forced UI state.
.origin = codecave
apUiTraceData:
.int 0x41505549
.int 1
.int 0
.int 0

apUiTraceClose:
.int 0x9421fff0 ; stwu r1,-16(r1), raw encoding for Cemu assembler compatibility
stw r11, 8(r1)
lis r11, apUiTraceData@ha
addi r11, r11, apUiTraceData@l
mflr r12
stw r12, 12(r11)
lwz r12, 8(r11)
addi r12, r12, 1
stw r12, 8(r11)
lwz r11, 8(r1)
addi r1, r1, 16
lis r12, 0x1048
b 0x035ff008

0x035ff004 = b apUiTraceClose
