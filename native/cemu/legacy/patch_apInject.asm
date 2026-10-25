[BOTW_AP_InjectionTest_V208]
moduleMatches = 0x6267BFD0

; ---------------------------------------------------------------------------
; Archipelago -- give the player an item.
;
; HOOK 1 : 0x031FA9B4, per-frame, in the game's frame function (0x031FA880),
;          after its update callback and its frame timing.
;          original: lwz r12, 0x0(r30), replayed LAST, by apDone, as it loads
;          r12, which the probe uses. FPS++ patches 0x031FA97C, a few instructions
;          earlier in the same function, where this hook used to be.
;
; HOOK 2 : 0x02EB5400, in PauseMenuDataMgr::itemGet, after the mflr.
;          original: stw r0, 0x6c(r1)
;          Hooking the entry (0x02EB53E4) would crash: the bla overwrites LR and
;          the mflr three instructions later would capture our return.
;
; The "this" of PauseMenuDataMgr is not searched statically: hook 2
; captures it from r24 the first time the player picks something up.
; Consequence: an item must have been picked up once per session before
; giving works.
;
; Protocol with the Python client:
;   1. Python writes the actor name into apItemName (64 bytes)
;   2. Python writes the quantity into apGiveValue
;   3. Python sets apGiveReq to 1
;   4. the next frame, the cave calls itemGet and increments apGiveDone
;
; Registers: r11 and r12 only, normally. Around the call to itemGet,
; r0 and r3-r10 are saved IN THE CAVE, not on the stack: Cemu's
; assembler takes neither mfcr nor stwu with a negative displacement.
; ---------------------------------------------------------------------------

; itemGet is at 0x02EB53E4 and the SafeString vtable at 0x10263910. Both
; addresses are loaded as constants with lis+ori in the code below: see the
; comment on bctrl for the reason.
_safeStringVtable = 0x10263910

.origin = codecave

apMagic:
.string "APMBOX01"
.align 4
apVersion:
.int 0x0BADF00E
apTick:
.int 0
apInbox:
.int 0
apOutbox:
.int 0
apLastSeen:
.int 0
apItemGetCount:
.int 0
apLastNamePtr:
.int 0
apLastValue:
.int 0
apPmdmThis:
.int 0
apGiveReq:
.int 0
apGiveValue:
.int 1
apGiveDone:
.int 0
apRuneReq:
.int 0
apRuneCount:
.int 0
apRuneDone:
.int 0
apNotifyReq:
.int 0
apNotifyDone:
.int 0
apHookMask:
.int 0
apHook0:
.int 0
apHook1:
.int 0
apHook2:
.int 0
apHook3:
.int 0
apHook4:
.int 0
apHook5:
.int 0
apHook6:
.int 0
apHook7:
.int 0
apHook8:
.int 0
apPickUpThis:
.int 0
apScreenThis:
.int 0
apDuration:
.int 0
apSaveF1:
.int 0
apListThis:
.int 0
apIterPtr:
.int 0
apIterLeft:
.int 0
apCandidate:
.int 0
apCandidate2:
.int 0

; sead::SafeString = { const char* cstr; void* vtable }
apNameCstr:
.int 0
apNameVtable:
.int 0

; 64-byte buffer where Python writes the actor name
apItemName:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; FREE TEXT buffer, 256 bytes (128 UTF-16BE characters).
; No instruction reads it: it is a writable area whose guest address is
; stable, to hold a string and make the game point to it. Placed AFTER
; apItemName so that no field already mapped in mailbox.py moves.
;
apText:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; --- center message probes (MainScreen) -------------------------------
; Six functions fetch a message in LayoutMsg/MainScreen_00 or handle the
; MainScreen screen. The one looked for fires exactly once when the
; center banner appears -- the same method as for PickUpWin, where nine
; probes pointed at 0x02FFA888.
apMSMask:
.int 0
apMS0:
.int 0
apMS1:
.int 0
apMS2:
.int 0
apMS3:
.int 0
apMS4:
.int 0
apMS5:
.int 0
apMSThis:
.int 0
apMS1This:
.int 0
apMSReq:
.int 0
apMSIndex:
.int 0
apMSState:
.int 0
apMSDone:
.int 0
apMSQueue:
.int 0
apMSSaveQ:
.int 0
apMSRet:
.int 0
apMSFlag:
.int 0
; path counters in 0x02ed1e1c: which way does it really leave?
apMSPass:
.int 0
apMSBail:
.int 0
apMSBailA:
.int 0
apMSMid:
.int 0
apMSDbg8c:
.int 0
apMSDbg154:
.int 0
apMSDbg150:
.int 0
apMSDbgC:
.int 0
; capture of the arguments of the push 0x02ed1f7c(this, a, b)
apPushThis:
.int 0
apPushA:
.int 0
apPushB:
.int 0
apPushN:
.int 0
; values to replay, and the request
apPlayA:
.int 0
apPlayB:
.int 0
apPlayReq:
.int 0
apPlayDone:
.int 0
; a sead::SafeString of ours for the message's parameter
apMsgCstr:
.int 0
apMsgVtable:
.int 0
apPlayRaw:
.int 0

; --- blue tip frame (MessageTipsRunTime_00) ----------------------------
; Eight counting probes on the functions of module 0x02fd3c74-0x02fd5340,
; the one that fetches LayoutMsg/MessageTipsRunTime_00. The same protocol
; as for PickUpWin and MainScreen: the one that fires a handful of times
; while the frame appears is the entry point.
apTipsMask:
.int 0
apTips0:
.int 0
apTips1:
.int 0
apTips2:
.int 0
apTips3:
.int 0
apTips4:
.int 0
apTips5:
.int 0
apTips6:
.int 0
apTips7:
.int 0
apTipsThis:
.int 0
apTipsShowThis:
.int 0
apTipsShowIdx:
.int 0
apTipsReq:
.int 0
apTipsIndex:
.int 0
apTipsDone:
.int 0
apTipsTextReq:
.int 0
apTipsTextLen:
.int 0
apTipsTextDone:
.int 0
; what the GAME passes as text object, read when it displays it
apTipsSpyPtr:
.int 0
apTipsSpyLen:
.int 0
; sead::SafeString on the pane's name, built by the cave
apPaneCstr:
.int 0
apPaneVtable:
.int 0
; our text object { const char16_t* ; length }
apTipsStrPtr:
.int 0
apTipsStrLen:
.int 0

; --- tracer of message label lookups ----------------------------------
; 0x03a38ad0(archive, output, const char* label) is the mandatory
; passage of EVERY message resolution: 35 sites call it. The probe is
; anchored after its `mflr r0`, where r0 still holds the return address
; -- so the call SITE, which tells which system asks for the text.
;
; The buffer is not circular: Python arms a quota (apRingLeft) and a
; pointer, the probe records the first N resolutions then stops. A ring
; would have needed masking, so instructions Cemu's assembler may not
; know -- and a single unknown one makes it reject the whole file.
;
apRingLeft:
.int 0
apRingPtr:
.int 0

; --- dialog window (Message_00 / MessageSp_00) ------------------------
; A chain established by the tracer, then by disassembling what it
; pointed at -- not the other way round:
;
;   0x035ff8fc(_, SafeString* archive, SafeString* label, a, b, flag)
;       opens the window if needed (0x033924c4(0x26,0)) then, when
;       the flag is 0, calls
;   0x035fb5f8(this, archive, label)
;       which resolves the message and stores the pair { text, length } in
;       this+0x1d0.
;
; The first argument of 0x035ff8fc is ignored: the window is taken from
; a global. a and b are not guessed, they are READ on a real call of the
; game and replayed -- which is what saved the push of the
; center message.
apDlgOpenN:
.int 0
apDlgOpen0N:
.int 0
apDlgSetN:
.int 0
apDlgThis:
.int 0
apDlgSeenArc:
.int 0
apDlgSeenLbl:
.int 0
apDlgArg6:
.int 0
apDlgArg7:
.int 0
apDlgArg8:
.int 0
apDlgReq:
.int 0
apDlgDone:
.int 0
apDlgTextReq:
.int 0
apDlgTextDone:
.int 0
apDlgStrPtr:
.int 0
apDlgStrLen:
.int 0
; sead::SafeString { cstr ; vtable } built by the cave
apDlgArcCstr:
.int 0
apDlgArcVtable:
.int 0
apDlgLblCstr:
.int 0
apDlgLblVtable:
.int 0
; buffers where Python writes the archive path and the label, in ASCII
apArcBuf:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
apLblBuf:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
apRing:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; --- text buffer of the dialog window ---------------------------------
; 4096 bytes, that is 2048 UTF-16 units. Apart from apText, which is 256
; bytes and already serves the notification and the center message.
; It must not be sized on the carrier: the arena is not overwritten,
; this+0x1d0 is made to point HERE. The game itself ships a message of
; 481 units (DemoMsg/Demo033_0/talk01), so the window takes far more
; than the 86 units of the chosen carrier. Measured: 309 units pass,
; in three pages of three lines. Cemu sizes the cave on the patch
; (5648 bytes at this stage), so growing the buffer costs nothing.
apDlgBuf:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; --- pickup interception ---------------------------------------------
; itemGet has only ONE exit, and its epilogue is self-contained:
;
;   0x02eb5894  lmw   r18, 0x30(r1)
;   0x02eb5898  lwz   r0, 0x6c(r1)
;   0x02eb589c  mtlr  r0
;   0x02eb58a0  addi  r1, r1, 0x68
;   0x02eb58a4  blr
;
; At the anchor 0x02EB5400 the prologue is over, and the instruction
; replayed is precisely the one that saves LR at 0x6c(r1). Jumping to
; the epilogue therefore makes the function harmless, with a perfectly
; balanced stack and registers: nothing is added to the inventory,
; and the caller sees no difference.
;
; The log serves the FILTER: r0 still holds the return address, so the
; call SITE. Whether it tells a chest from an apple is to be measured.
apIgLeft:
.int 0
apIgPtr:
.int 0
apBlockReq:
.int 0
apBlockDone:
.int 0
; A marker set by the GRANTED items function (0x02b769c4) right before it
; calls itemGet. It filters without comparing addresses: comparing r0
; with a bound would need cmplw or subf, instructions Cemu's assembler
; may not know -- and a single unknown one makes it reject the whole
; file. A flag set by one probe and read by another only uses cmpwi.
;
apGrantMark:
.int 0
; a count of FRAMES left, not a boolean: see the valve in the per-frame
; hook. Since mailbox 0x0BADF00E, this lease only allows the
; Obj_DungeonClearSeal filter below. Chests, Koroks and NPC gifts are
; never blocked by this command.
apBlockGrants:
.int 0
apGrantN:
.int 0
apIgRing:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; save the volatile registers around the call
apS0:
.int 0
apS3:
.int 0
apS4:
.int 0
apS5:
.int 0
apS6:
.int 0
apS7:
.int 0
apS8:
.int 0
apS9:
.int 0
apS10:
.int 0
apSLR:
.int 0
apSCTR:
.int 0

; --- item get window (MessageGet_00) ----------------------------------
; Nineteen counting probes on the functions from 0x02fcf29c to 0x02fd33e0,
; the module that references LayoutMsg/MessageGet_00, MessageGet_00Screen
; and MessageGet_00 -- the three strings relocations lead back to this
; range. The same protocol as PickUpWin, MainScreen and the tip frame:
; the one that fires a handful of times when the window appears is the
; entry point, those that count in hundreds are per-frame.
;
; No bit mask here, unlike the previous benches: with nineteen probes
; `oris` would be needed for bits 16 to 18, and a single instruction
; Cemu's assembler ignores makes it reject the whole file. The counters
; already carry the information -- a non-zero counter IS the bit set.
;
; These fields are appended at the end of the block on purpose: inserting
; in the middle would move everything after it without any visible break.
apGet0:                         ; function 0x02fcf29c
.int 0
apGet1:                         ; function 0x02fcf63c
.int 0
apGet2:                         ; function 0x02fd0314
.int 0
apGet3:                         ; function 0x02fd0ce4
.int 0
apGet4:                         ; function 0x02fd14e8
.int 0
apGet5:                         ; function 0x02fd1534
.int 0
apGet6:                         ; function 0x02fd165c
.int 0
apGet7:                         ; function 0x02fd1ed8
.int 0
apGet8:                         ; function 0x02fd20cc
.int 0
apGet9:                         ; function 0x02fd21cc
.int 0
apGet10:                         ; function 0x02fd22a0
.int 0
apGet11:                         ; function 0x02fd23f4
.int 0
apGet12:                         ; function 0x02fd2510
.int 0
apGet13:                         ; function 0x02fd255c
.int 0
apGet14:                         ; function 0x02fd2b18
.int 0
apGet15:                         ; function 0x02fd2d64
.int 0
apGet16:                         ; function 0x02fd2ff0
.int 0
apGet17:                         ; function 0x02fd3034
.int 0
apGet18:                         ; function 0x02fd33e0
.int 0

; For each probe: where the call comes from, and with which arguments.
; The return address settles the only question left after counting --
; which of these functions is called from OUTSIDE the module. Those
; that call each other are internal steps; the one whose caller is
; elsewhere is the entry point, the one that can be triggered at will.
; r0 does: at the anchor the mflr has already happened, and Cemu's `bla`
; overwrites LR, not r0. r3/r4/r5 give the arguments to replay.
; return address
apGetFrom0:
.int 0
apGetFrom1:
.int 0
apGetFrom2:
.int 0
apGetFrom3:
.int 0
apGetFrom4:
.int 0
apGetFrom5:
.int 0
apGetFrom6:
.int 0
apGetFrom7:
.int 0
apGetFrom8:
.int 0
apGetFrom9:
.int 0
apGetFrom10:
.int 0
apGetFrom11:
.int 0
apGetFrom12:
.int 0
apGetFrom13:
.int 0
apGetFrom14:
.int 0
apGetFrom15:
.int 0
apGetFrom16:
.int 0
apGetFrom17:
.int 0
apGetFrom18:
.int 0
; r3
apGetThis0:
.int 0
apGetThis1:
.int 0
apGetThis2:
.int 0
apGetThis3:
.int 0
apGetThis4:
.int 0
apGetThis5:
.int 0
apGetThis6:
.int 0
apGetThis7:
.int 0
apGetThis8:
.int 0
apGetThis9:
.int 0
apGetThis10:
.int 0
apGetThis11:
.int 0
apGetThis12:
.int 0
apGetThis13:
.int 0
apGetThis14:
.int 0
apGetThis15:
.int 0
apGetThis16:
.int 0
apGetThis17:
.int 0
apGetThis18:
.int 0
; r4
apGetR4_0:
.int 0
apGetR4_1:
.int 0
apGetR4_2:
.int 0
apGetR4_3:
.int 0
apGetR4_4:
.int 0
apGetR4_5:
.int 0
apGetR4_6:
.int 0
apGetR4_7:
.int 0
apGetR4_8:
.int 0
apGetR4_9:
.int 0
apGetR4_10:
.int 0
apGetR4_11:
.int 0
apGetR4_12:
.int 0
apGetR4_13:
.int 0
apGetR4_14:
.int 0
apGetR4_15:
.int 0
apGetR4_16:
.int 0
apGetR4_17:
.int 0
apGetR4_18:
.int 0
; r5
apGetR5_0:
.int 0
apGetR5_1:
.int 0
apGetR5_2:
.int 0
apGetR5_3:
.int 0
apGetR5_4:
.int 0
apGetR5_5:
.int 0
apGetR5_6:
.int 0
apGetR5_7:
.int 0
apGetR5_8:
.int 0
apGetR5_9:
.int 0
apGetR5_10:
.int 0
apGetR5_11:
.int 0
apGetR5_12:
.int 0
apGetR5_13:
.int 0
apGetR5_14:
.int 0
apGetR5_15:
.int 0
apGetR5_16:
.int 0
apGetR5_17:
.int 0
apGetR5_18:
.int 0

; --- call order, and the window's manager class -----------------------
; apGetSeq is a global counter: every probe of both benches increments it
; and stores its value. Two functions called only once are therefore
; ordered against each other, which counters alone do not say -- and to
; replay a "prepare, fill, show" sequence, the order is precisely what
; must be known.
apGetSeq:
.int 0
apGetOrd0:
.int 0
apGetOrd1:
.int 0
apGetOrd2:
.int 0
apGetOrd3:
.int 0
apGetOrd4:
.int 0
apGetOrd5:
.int 0
apGetOrd6:
.int 0
apGetOrd7:
.int 0
apGetOrd8:
.int 0
apGetOrd9:
.int 0
apGetOrd10:
.int 0
apGetOrd11:
.int 0
apGetOrd12:
.int 0
apGetOrd13:
.int 0
apGetOrd14:
.int 0
apGetOrd15:
.int 0
apGetOrd16:
.int 0
apGetOrd17:
.int 0
apGetOrd18:
.int 0

; The 13 functions from 0x03606ad0 to 0x03607560. Counting showed that the
; window's functions are called from this range, and scanning the `bl` of
; .text finds NO direct call there: everything goes through vtables. The
; callers are therefore not found statically, only by measurement.
; counter
apGetWin0:
.int 0
apGetWin1:
.int 0
apGetWin2:
.int 0
apGetWin3:
.int 0
apGetWin4:
.int 0
apGetWin5:
.int 0
apGetWin6:
.int 0
apGetWin7:
.int 0
apGetWin8:
.int 0
apGetWin9:
.int 0
apGetWin10:
.int 0
apGetWin11:
.int 0
apGetWin12:
.int 0
; caller
apGetWinFrom0:
.int 0
apGetWinFrom1:
.int 0
apGetWinFrom2:
.int 0
apGetWinFrom3:
.int 0
apGetWinFrom4:
.int 0
apGetWinFrom5:
.int 0
apGetWinFrom6:
.int 0
apGetWinFrom7:
.int 0
apGetWinFrom8:
.int 0
apGetWinFrom9:
.int 0
apGetWinFrom10:
.int 0
apGetWinFrom11:
.int 0
apGetWinFrom12:
.int 0
; r3
apGetWinThis0:
.int 0
apGetWinThis1:
.int 0
apGetWinThis2:
.int 0
apGetWinThis3:
.int 0
apGetWinThis4:
.int 0
apGetWinThis5:
.int 0
apGetWinThis6:
.int 0
apGetWinThis7:
.int 0
apGetWinThis8:
.int 0
apGetWinThis9:
.int 0
apGetWinThis10:
.int 0
apGetWinThis11:
.int 0
apGetWinThis12:
.int 0
; r4
apGetWinR4_0:
.int 0
apGetWinR4_1:
.int 0
apGetWinR4_2:
.int 0
apGetWinR4_3:
.int 0
apGetWinR4_4:
.int 0
apGetWinR4_5:
.int 0
apGetWinR4_6:
.int 0
apGetWinR4_7:
.int 0
apGetWinR4_8:
.int 0
apGetWinR4_9:
.int 0
apGetWinR4_10:
.int 0
apGetWinR4_11:
.int 0
apGetWinR4_12:
.int 0
; r5
apGetWinR5_0:
.int 0
apGetWinR5_1:
.int 0
apGetWinR5_2:
.int 0
apGetWinR5_3:
.int 0
apGetWinR5_4:
.int 0
apGetWinR5_5:
.int 0
apGetWinR5_6:
.int 0
apGetWinR5_7:
.int 0
apGetWinR5_8:
.int 0
apGetWinR5_9:
.int 0
apGetWinR5_10:
.int 0
apGetWinR5_11:
.int 0
apGetWinR5_12:
.int 0
; rang
apGetWinOrd0:
.int 0
apGetWinOrd1:
.int 0
apGetWinOrd2:
.int 0
apGetWinOrd3:
.int 0
apGetWinOrd4:
.int 0
apGetWinOrd5:
.int 0
apGetWinOrd6:
.int 0
apGetWinOrd7:
.int 0
apGetWinOrd8:
.int 0
apGetWinOrd9:
.int 0
apGetWinOrd10:
.int 0
apGetWinOrd11:
.int 0
apGetWinOrd12:
.int 0

; --- get window driver: 0x03a3ec0c ------------------------------------
; The chronology of both benches points at it: its three call sites
; 0x03a3ede0, 0x03a3ee88 and 0x03a3eeac trigger, in that order,
; 0x02fd0314, 0x03606f48 (which opens the screen) and 0x02fd255c, all on
; the same `this` as the window.
;
; Its prologue builds a SafeString on its own stack from r6 --
; `lis r0, 0x1026` then `addic r0, r0, 0x3910` gives 0x10263910, the same
; vtable as itemGet's -- and stores it at this+0x78. r6 is therefore a
; `const char*`. It is a READING of the disassembly: the probe below
; exists to check it rather than believe it.
apGetDrvN:
.int 0
apGetDrvFrom:
.int 0
apGetDrvThis:
.int 0
apGetDrvA4:
.int 0
apGetDrvA5:
.int 0
apGetDrvA6:
.int 0
apGetDrvA7:
.int 0
apGetDrvA8:
.int 0
apGetDrvA9:
.int 0
apGetDrvReq:
.int 0
apGetDrvDone:
.int 0
; our own string, put in place of r6 on replay (64 bytes)
apGetDrvName:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; --- FILTERED capture of the driver, and the panes' text ---------------
; MEASURED: 0x03a3ec0c is NOT specific to the get window. Its r6 is the
; NAME OF THE SCREEN to open -- read 'MessageGet_00' on a chest, then
; 'PauseMenuInfo_00' when the player confirmed the popup. It is a generic
; screen opener. Putting our text in its place crashed the game, which
; looked for a screen of that name.
;
; So the apGetDrv* fields above hold for the LAST screen opened,
; whatever it is. The apGetWinC* fields below only hold for
; MessageGet_00: the probe apGetProbe1, which only that screen goes
; through, copies the pending capture there. No address comparison --
; the same trick as the granted items marker.
apGetWinOk:
.int 0
apGetWinCThis:
.int 0
apGetWinCA4:
.int 0
apGetWinCA5:
.int 0
apGetWinCA6:
.int 0
apGetWinCA7:
.int 0
apGetWinCA8:
.int 0
apGetWinCA9:
.int 0

; Three probes on the module's calls to the pane text helper. Each one
; reads the two words of the structure passed in r4 -- the same pair
; apTipsSpy read on the tip frame.
apGetTxtN0:
.int 0
apGetTxtR3_0:
.int 0
apGetTxtW0_0:
.int 0
apGetTxtW1_0:
.int 0
apGetTxtN1:
.int 0
apGetTxtR3_1:
.int 0
apGetTxtW0_1:
.int 0
apGetTxtW1_1:
.int 0
apGetTxtN2:
.int 0
apGetTxtR3_2:
.int 0
apGetTxtW0_2:
.int 0
apGetTxtW1_2:
.int 0

; --- get window text: read, then substitute ----------------------------
; MEASURED: probe 2 passes an object { ptr, vtable 0x10244e0c }, not the
; SafeString vtable 0x10263910 of the other two. Its ptr does not read as
; a C string -- first byte zero -- so it is not ASCII. Rather than guess
; the encoding, the probe COPIES 64 bytes here: decoding happens offline,
; where trying is safe.
;
; apGetTxtReq arms the substitution: at the next call, the text pointer
; is replaced by apGetTxtOur. It is a WRITE, not a call -- so without the
; risk that crashed the replay of the screen opener.
apGetTxtSaveR3:
.int 0
apGetTxtReq:
.int 0
apGetTxtDone:
.int 0
apGetTxtB0:
.int 0
apGetTxtB1:
.int 0
apGetTxtB2:
.int 0
apGetTxtB3:
.int 0
apGetTxtB4:
.int 0
apGetTxtB5:
.int 0
apGetTxtB6:
.int 0
apGetTxtB7:
.int 0
apGetTxtB8:
.int 0
apGetTxtB9:
.int 0
apGetTxtB10:
.int 0
apGetTxtB11:
.int 0
apGetTxtB12:
.int 0
apGetTxtB13:
.int 0
apGetTxtB14:
.int 0
apGetTxtB15:
.int 0
; our own text, 128 bytes = 64 UTF-16 units
apGetTxtOur:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; --- common pane text resolver: 0x03082c70 ----------------------------
; It holds 0x03082ccc, the site the message tracer reported. And it is
; what the generic helper 0x030834b0 calls after building the label
; "<actor>_Name" with the format 0x1025dd58 ("%s_Name").
;
; The question this probe settles: does the item name go through here?
; The message tracer showed no <actor>_Name, but it only observes
; the calls to 0x03a38ad0 -- not the entry of 0x03082c70.
;
; Four successive captures once armed, because building the window
; triggers several and the rank of the item name is unknown. No computed
; indexing: four separate blocks, chosen by cmpwi. A single instruction
; unknown to Cemu's assembler would make it reject the whole file.
apResArm:
.int 0
apResN:
.int 0
apResSaveR3:
.int 0
apResA0:
.int 0
apResB0:
.int 0
apResC0:
.int 0
apResL0_0:
.int 0
apResL0_1:
.int 0
apResL0_2:
.int 0
apResL0_3:
.int 0
apResL0_4:
.int 0
apResL0_5:
.int 0
apResL0_6:
.int 0
apResL0_7:
.int 0
apResA1:
.int 0
apResB1:
.int 0
apResC1:
.int 0
apResL1_0:
.int 0
apResL1_1:
.int 0
apResL1_2:
.int 0
apResL1_3:
.int 0
apResL1_4:
.int 0
apResL1_5:
.int 0
apResL1_6:
.int 0
apResL1_7:
.int 0
apResA2:
.int 0
apResB2:
.int 0
apResC2:
.int 0
apResL2_0:
.int 0
apResL2_1:
.int 0
apResL2_2:
.int 0
apResL2_3:
.int 0
apResL2_4:
.int 0
apResL2_5:
.int 0
apResL2_6:
.int 0
apResL2_7:
.int 0
apResA3:
.int 0
apResB3:
.int 0
apResC3:
.int 0
apResL3_0:
.int 0
apResL3_1:
.int 0
apResL3_2:
.int 0
apResL3_3:
.int 0
apResL3_4:
.int 0
apResL3_5:
.int 0
apResL3_6:
.int 0
apResL3_7:
.int 0

; Return address of each resolver capture. At the anchor (0x03082c8c)
; the mflr has already happened and r0 still holds the return address:
; it therefore names the SITE that asks for the resolution. That was the
; missing piece to place the substitution -- the item name's output is at
; 0x0e2008xx and not on the stack, so the call does not come from the site
; read in the disassembly.
apResRet0:
.int 0
apResRet1:
.int 0
apResRet2:
.int 0
apResRet3:
.int 0

; --- item name substitution, without touching the arena ---------------
; MEASURED: 'Item_Ore_E_Name' is resolved by 0x03082c70, asked from
; 0x030835c8. That site is followed at once by the epilogue, so the
; resolver's return value goes up to the caller: at 0x030835c8, r3 IS the
; resolved text.
;
; Replacing r3 with our own object gives our text without writing even
; once into the arena -- so without renaming the item, even briefly, so
; without exposing the inventory to the crash of long names.
;
; The shape of the returned object is not assumed: the first four words
; are copied to be read offline before anything is armed.
apSubN:
.int 0
apSubOut:
.int 0
apSubW0:
.int 0
apSubW1:
.int 0
apSubW2:
.int 0
apSubW3:
.int 0
apSubReq:
.int 0
apSubDone:
.int 0
apSubSaveR4:
.int 0
apSubLen:
.int 0
apSubOutBuf:
.int 0
apSubO0:
.int 0
apSubO1:
.int 0
apSubO2:
.int 0
apSubO3:
.int 0
apSubO4:
.int 0
apSubO5:
.int 0
apSubO6:
.int 0
apSubO7:
.int 0
; our replacement object, its shape to be confirmed by the capture
apSubObj:
.int 0
.int 0
.int 0
.int 0
; our UTF-16BE text, 256 bytes = 128 units
apSubBuf:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; --- the window's description, the same scheme as the name ------------
; 'Item_Ore_E_Desc' is resolved from 0x03083860. Two differences with
; the name's site, both measured:
;
;  1. the original instruction there is `lmw r27, 0x22c(r1)`, which RESTORES r29 --
;     and r29 holds the output buffer. Replaying it first, as usual,
;     would destroy what is looked for. The probe therefore captures
;     BEFORE, and replays last.
;  2. `lmw` is not in our disassembler, and nothing says that Cemu's
;     assembler knows it. It is replayed as five equivalent `lwz`
;     instructions: r27..r31 from 0x22c to 0x23c.
apSubDescN:
.int 0
apSubDescReq:
.int 0
apSubDescDone:
.int 0
apSubDescLen:
.int 0
apSubDescBuf:
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0
.int 0

; --- automatic arming on a GRANTED item --------------------------------
; MEASURED: the title site (0x030835c8) is GENERIC -- it resolves
; <actor>_Name for the whole game. Arming by hand then opening the
; inventory hijacks the name of the item looked at, not the chest's. Seen in the game.
;
; apSubAuto solves it: it is a COUNT of granted items. The probe of
; granted items (0x02b769d4) consumes it and arms the substitution then --
; so right before itemGet, so before the window resolves its text, and
; NEVER while the player browses the inventory.
;
; The client fills the buffers in advance and sets apSubAuto; the cave
; picks the moment. The same division of work as for blocking.
apSubAuto:
.int 0
apSubAutoN:
.int 0

; --- opening the window ourselves: BOTH chained calls ----------------
; MEASURED: three crashes when replaying only the second call. The real
; site makes two, and the first builds the object the second receives:
;
;   0x03a42ccc  lwz r3, 0x24(r27)     a factory, taken from r27
;   0x03a42cd0  lwz r10, 0x0(r3)
;   0x03a42cd4  lwz r0, 0x14(r10)     vtable[0x14]
;   0x03a42ce4  bctrl                 -> r3 = the screen object
;   0x03a42cec  lwz r12, 0xc(r3)
;   0x03a42cf0  lwz r0, 0x4c(r12)     vtable[0x4c] = 0x03a3ec0c
;   0x03a42d10  bctrl                 with r4..r9 taken from r27,r31,r24,r28,r25,r26
;
; Replaying the second alone meant opening a screen without going through
; its factory. The six registers of the real site are therefore captured,
; and both calls are replayed in order.
apOpnN:
.int 0
apOpnThis:
.int 0
apOpn24:
.int 0
apOpn25:
.int 0
apOpn26:
.int 0
apOpn27:
.int 0
apOpn28:
.int 0
apOpn31:
.int 0
apOpnReq:
.int 0
apOpnDone:
.int 0

; FILTERED capture of the opening site. The probe 0x03a42ce8 fires at
; EVERY screen opening -- 40 times in a simple game -- so the six raw
; registers hold for the last screen opened, whatever it is. The same
; mistake as for the driver, fixed the same way: apGetProbe1, which only
; MessageGet_00 goes through, freezes the pending capture.
apOpnOk:
.int 0
apOpnC24:
.int 0
apOpnC25:
.int 0
apOpnC26:
.int 0
apOpnC27:
.int 0
apOpnC28:
.int 0
apOpnC31:
.int 0

; --- which THREAD are we on? ------------------------------------------
; A lead never checked: the per-frame hook and the UI code may not run
; on the same stack. The r1 values read so far ranged from 0x0e200830
; to 0x12afbb58 -- two very distant areas.
; If these are two threads, calling the screen opener from the per-frame
; hook runs it in the wrong place, which would explain four crashes with
; no argument at fault.
apR1Frame:
.int 0
apR1Ui:
.int 0
apR1Name:
.int 0
apR1Opn:
.int 0

; --- bisecting the opening replay -------------------------------------
; Five crashes, the last one later than the others. Rather than retrying
; the whole, it is split: apOpnStep at 1 only calls the factory, at 2
; it chains the opening. And apOpnPhase moves on at each step, to say
; how far it went if the process survives long enough to be read.
;   1 = before the factory   2 = factory returned
;   3 = before the opening   4 = opening returned
apOpnStep:
.int 0
apOpnPhase:
.int 0
apOpnR3:
.int 0

; --- the context object r31, and its content --------------------------
; DECISIVE MEASUREMENT: r31 (0x443d6518) keeps the same ADDRESS from one
; session to the next, but its CONTENT changes. Window open, it reads
; `43 41 c9 3c 44 3d 63 c8`; window closed, `00 00 00 01 00 00 00 00`.
; It is a context object the game resets when closing.
;
; And the bisection confirms it: calling the factory with the window OPEN
; works, window closed crashes. Its content is therefore copied at capture
; time, to restore it before the replay.
;
; An accepted caveat: these words hold heap pointers. Restoring them does
; not bring back what they point to. If the replay still crashes, the
; object is not enough and what fills it must be traced.
apOpnCtxSave:
apOpnCtx0:
.int 0
apOpnCtx1:
.int 0
apOpnCtx2:
.int 0
apOpnCtx3:
.int 0
apOpnCtx4:
.int 0
apOpnCtx5:
.int 0
apOpnCtx6:
.int 0
apOpnCtx7:
.int 0
apOpnCtx8:
.int 0
apOpnCtx9:
.int 0
apOpnCtx10:
.int 0
apOpnCtx11:
.int 0
apOpnCtx12:
.int 0
apOpnCtx13:
.int 0
apOpnCtx14:
.int 0
apOpnCtx15:
.int 0
apOpnCtx16:
.int 0
apOpnCtx17:
.int 0
apOpnCtx18:
.int 0
apOpnCtx19:
.int 0
apOpnCtx20:
.int 0
apOpnCtx21:
.int 0
apOpnCtx22:
.int 0
apOpnCtx23:
.int 0
apOpnCtx24:
.int 0
apOpnCtx25:
.int 0
apOpnCtx26:
.int 0
apOpnCtx27:
.int 0
apOpnCtx28:
.int 0
apOpnCtx29:
.int 0
apOpnCtx30:
.int 0
apOpnCtx31:
.int 0
apOpnCtxR3:
.int 0

; --- the heap ---------------------------------------------------------
; MEASURED: r31 is not a context object, it is a HEAP. Branch 11 of the
; factory does `li r3, 0x1c9c ; li r5, 4 ; bl 0x0308e5a0` leaving r4
; intact -- so r4 IS the heap the 7324-byte screen is allocated on.
; Window closed, that heap is dead: the allocation returns 0, and the
; factory returns 0. That is the whole refusal.
;
; And the allocator handles the null case: 0x0308e514 tests `cmpwi r3, 0`
; and, when null, fetches the CURRENT HEAP through 0x030aa1ac. It is
; therefore enough not to pass our dead heap.
;
; apOpnHeap at 0 = pass a null heap (the current one); else = the captured heap.
apOpnHeap:
.int 0

; --- two ways to get the screen ---------------------------------------
; apOpnMode = 0: the raw factory 0x0305eae8, as the real site calls
;   it. It allocates 7324 bytes on the heap passed in r4 -- and returns 0
;   as soon as that heap is dead, which it is outside an opening. Null heap:
;   the allocator looks for the CURRENT heap (0x0308e514) and does not find
;   one from our thread either. Measured: returns 0 in both cases.
;
; apOpnMode = 1: the trampoline 0x033924c4, the one the dialog box
;   already uses successfully from this very hook, as
;   `0x033924c4(0x26, 0)`. It jumps to *(0x1047e1a4), a registered API
;   that takes care of the heap itself. It is passed our index, 0x0b,
;   and zero. The trampoline is safe: `bclr` when the pointer is null.
apOpnMode:
.int 0

; --- restoring the context object: now OPTIONAL ----------------------
; This block copies 32 words into apOpnC31, which is an ALREADY FREED HEAP.
; Writing into the header of a dead heap never unlocked anything and may
; damage the allocator. It is therefore off by default. Python turns it on
; with --ctx to reproduce earlier measurements.
apOpnCtxOn:
.int 0

; --- call the ENCLOSING FUNCTION, not its middle ---------------------
; MEASURED offline (rpx.py dis 0x03a42b94): r31 is not a local
; variable, it is ARGUMENT 6 -- `mr r31, r8` in the prologue. And the
; function already does without a heap: when r31 and r30 are null, it
; branches to 0x03a42c90 and CREATES one through `bl 0x030a8734`, then resumes.
;
; Replaying from 0x03a42ccc therefore jumps over the heap's creation.
; apOpnMode = 2 calls 0x03a42b94(arg1..arg6) whole:
;   r3 = apOpnC27   r4 = apOpnArg4   r5 = apOpnC28
;   r6 = apOpnC25   r7 = apOpnC26    r8 = apOpnHeap
; With apOpnArg4 = 0 and apOpnHeap = 0, the function takes its creation
; branch. Nothing is dereferenced in the injected code: the function does it all.
apOpnArg4:
.int 0

; --- where does a LIVE HEAP come from? --------------------------------
; The creator 0x030a857c and the allocator 0x0308e514 both run into the
; SAME function: `0x030aa1ac(x)`, which returns the current heap. Its body,
; read offline:
;     r12 = *(0x1046C920) ; r3 = *(r12+0x60) ; bl 0x0434c488 (import RPL)
;     if the return is non-null -> return *(return + 0x70)   <- the THREAD's heap
;     else                       -> return *(argument + 0x4) <- static fallback
; So it is thread-local, and there is a static fallback. The creator
; passes it *(0x1046C8B0).
;
; NOTE: 0x1047c8b0 was once written for it. The code does `lis r3, 0x1047 ;
; lwz r3, -0x3750(r3)`, that is 0x10470000 - 0x3750 = 0x1046C8B0. The
; 0x10000 difference would have read into the void.
;
; This probe answers without risk: it reads both statics, then calls the
; getter -- but only if its two dereferences are safe.
apHeapReq:
.int 0
apHeapN:
.int 0
apHeapRoot:
.int 0
apHeapMgr:
.int 0
apHeapFb:
.int 0
apHeapCur:
.int 0

; --- the prologue of 0x03a42b94: the six arguments, and the caller ----
; Anchored on `stw r0, 0x34(r1)`, where r0 still holds LR and no `mr`
; has destroyed r3..r8 yet. Raw first (the site opens 40 times per game),
; then frozen by apGetProbe1, which only MessageGet_00 goes through.
apOpnProN:
.int 0
apOpnProLr:
.int 0
apOpnProR1:
.int 0
apOpnProA1:
.int 0
apOpnProA2:
.int 0
apOpnProA3:
.int 0
apOpnProA4:
.int 0
apOpnProA5:
.int 0
apOpnProA6:
.int 0
apOpnPrcOk:
.int 0
apOpnPrcLr:
.int 0
apOpnPrcR1:
.int 0
apOpnPrcA1:
.int 0
apOpnPrcA2:
.int 0
apOpnPrcA3:
.int 0
apOpnPrcA4:
.int 0
apOpnPrcA5:
.int 0
apOpnPrcA6:
.int 0

; --- the level ABOVE: 0x030806f0 --------------------------------------
; MEASURED (two traces): replaying 0x03a42b94 reproduces the whole
; CONSTRUCTION group -- each function there goes from 1 to 2 calls -- but
; none of the DISPLAY group (0x02fd0ce4, 0x02fd1534, 0x02fd14e8,
; 0x02fd165c, 0x02fd2b18, 0x02fd20cc). Those six are called from
; 0x036072e0, 0x03607390 and 0x03607414, not from 0x03a42b94.
;
; And 0x03a42b94 is not the top: its caller 0x030806f0 has 40 more
; instructions after the call, among them `0x03a3f36c(screen, 1)`. So one
; level up, with the protocol that just worked: a probe on the prologue,
; a capture frozen by apGetProbe1, then a replay.
;
; Anchor: `stw r0, 0x2c(r1)` at 0x0308070c. The mflr happened at 0x030806f8,
; and the prologue's `mr` copied r3..r7 without destroying them -- r7 is
; only copied at 0x03080710, after the anchor.
apUpN:
.int 0
apUpLr:
.int 0
apUpR1:
.int 0
apUpA1:
.int 0
apUpA2:
.int 0
apUpA3:
.int 0
apUpA4:
.int 0
apUpA5:
.int 0
apUpcOk:
.int 0
apUpcA1:
.int 0
apUpcA2:
.int 0
apUpcA3:
.int 0
apUpcA4:
.int 0
apUpcA5:
.int 0

; --- THE STAGING, read at 0x03a40ebc ----------------------------------
; MEASURED: neither the heap, nor the upper levels, nor the screen's inner
; state, nor the active table at +0x604 make the window appear. The missing
; gesture is right before the call the chronology pointed at:
;
;   0x03a40e9c  vtable[0x214](screen, "open")   ; when mode 1 or 2
;   0x03a40ec4  stb 0, 0x9e(screen)
;   0x03a40ec8  stb 1, 0x96(screen)
;   0x03a40ecc  stb 0, 0x97(screen)
;   0x03a40edc  vtable[0x114](screen)           ; = 0x036072e0
;
; The `0x9e = 0` matches the object's snapshot: it was the only bit of
; +0x9c that differed between shown and built. It had been written without
; calling anything -- the call was missing, not the flag.
;
; vtable[0x114] and vtable[0x214] read in the RPX as 0x036072e0 and
; 0x02fd299c, and the string 0x1035DB30 is "open".
apOpnAnim:
.int 0

; --- THE STAGING IS A VIRTUAL METHOD ----------------------------------
; 0x03a40d20 appears in 94 vtables: not a free function, a slot. On our
; screen (vtable 0x10245298) it is at +0x1a4, and its neighbours are
; exactly the four callers of the display group the chronology said were
; missing:
;
;   +0x1a4  0x03a40d20   the staging
;   +0x1b4  0x03a40f40   -> 0x03607390
;   +0x1c4  0x03a4115c   -> 0x03607414
;   +0x1cc  0x03a411a0   -> 0x036074b8
;
; Signature: 0x03a40d20(screen, mode), a switch on mode 0..4. The "open"
; animation plays only for 1 and 2, and mode 1 has a whole preamble --
; vtable[0x94] then 0x03a31898 on screen->0x18 -- that our four hand-made
; gestures skipped. It is the most serious lead for the crash of
; vtable[0x214] called bare.
;
; apOpnMode = 5 calls screen->vtable[0x1a4](screen, apOpnVArg).
apOpnVArg:
.int 0

; --- THE TOP OF THE CHAIN: 0x02b769c4 ---------------------------------
; The window has been built FROM THE BOTTOM from the start, and each time
; a missing piece of context stopped it. The screen is now in the same state
; as a shown one on every measured field, and it still does not draw:
; three functions never fire, all called OUTSIDE the
; screen manager (0x03a3b8c4, 0x0339c664, 0x036073c4).
;
; So the scale changes. 0x02b769c4 is the function that handles GRANTED
; items -- chest, shrine, Korok, NPC gift -- already identified by the
; pickup filter. Replaying it lets the game do everything itself:
; window, animation, text, waiting for the A button.
;
; Signature: 0x02b769c4(r3, r4). Both are intact at the anchor 0x02b769d4,
; where apGrantSpy already sits -- the `mr r31, r4` is before, `mr r30, r3`
; after, and neither destroys its source.
apGrantR3:
.int 0
apGrantR4:
.int 0
apGrantLr:
.int 0

; --- the STACK structure r4 points to ---------------------------------
; MEASURED: r4 is 0x12b3c4f8, a STACK address. On replay that frame is long
; dead and bytes that no longer mean anything were passed -- the replay
; was not faithful. Going one level up does not help: 0x02b77260 only
; relays the same pointer, which comes from higher up.
;
; But nothing forces keeping the original: 128 bytes are COPIED while the
; frame is alive, and our copy is passed on replay. Python writes the copy's
; address into apGrantBufPtr -- so the injected code needs not compute an
; absolute address, an idiom Cemu's assembler may not accept.
;
apGrantBufPtr:
.int 0

; --- THE BROADCAST: 0x032bc730(dispatcher, itemName) -----------------
; MEASURED: 0x02b769c4 calls itemGet at 0x02b76ac0, then -- on EACH of
; its branches, three times in the function -- does:
;     lwz r3, *(0x1047D6C0)   ; a static
;     mr  r4, r30             ; the item name string
;     bl  0x032bc730
; And 0x032bc730 walks a LIST of subscribers (count at +0x58, array at
; +0x60) calling a virtual method on each. It is an event broadcast:
; "item X was just obtained". The UI likely subscribes to it to open the
; window.
;
; Two arguments, a static and a name -- the cleanest candidate of the
; session. apGrantName passes OUR string instead of the captured one.
apDispN:
.int 0
apDispR3:
.int 0
apDispR4:
.int 0
apDispLr:
.int 0
apGrantName:
.int 0
; The dispatcher is no longer COMPUTED but MEASURED: apDispSpy reads it
; on a real chest, and Python copies it here. A first version derived
; 0x1047D6C0 from `lis 0x1047 / lwz -0x2940` -- the real address is
; 0x1046D6C0, and the 0x10000 difference made the rodata string
; 'WeatherSelector' pass for an object. The game died on it. The same
; trap as the one fixed on 0x1046C8B0: never derive a static address by
; hand when a probe can read it.
apDispArg:
.int 0

; --- THE WHOLE CALL CHAIN, at once ------------------------------------
; The chain was climbed one level per session, and each level revealed a
; missing piece of context: a heap, a driver, a stack. It is the symptom of
; a system where the window is not an object that is opened but the
; display of a STATE the game enters -- Link frozen, controls locked,
; waiting for A. The clearest proof: turning off the display byte of a
; REAL window prevents confirming it, so the game keeps waiting.
;
;
; On PowerPC stack frames are chained: *(r1) gives the previous frame,
; and *(frame + 4) the return address. Unwinding that chain from the item
; attribution gives the WHOLE call chain of the real chest -- up to the
; event system. A single measurement instead of one rung per session.
;
;
; Only r11 and r12 are free in a probe, so the current frame is stored in
; memory between steps rather than kept in a register. Each dereference is
; preceded by a zero test: a malformed stack stops the unwinding instead
; of killing the game.
; --- A GENERIC INVOKER ----------------------------------------------
; The patch used to change once per experiment, and each change costs a
; Cemu restart and a game reload. apOpnMode = 8 calls the address stored
; in apCallAddr with the eight arguments of apCallA1..A8. Python decides
; everything; the cave only jumps. No call experiment needs a restart any
; more.
;
; The only possible guard here is the jump's: an address outside .text
; is refused. The arguments are Python's responsibility -- it can read the
; memory and check before firing.
apCallAddr:
.int 0
apCallA1:
.int 0
apCallA2:
.int 0
apCallA3:
.int 0
apCallA4:
.int 0
apCallA5:
.int 0
apCallA6:
.int 0
apCallA7:
.int 0
apCallA8:
.int 0
apCallRet:
.int 0
apCallN:
.int 0
apLvl0N:
.int 0
apLvl0R3:
.int 0
apLvl0R4:
.int 0
apLvl0R5:
.int 0
apLvl0R6:
.int 0
apLvl0R7:
.int 0
apLvl0Lr:
.int 0
apLvl1N:
.int 0
apLvl1R3:
.int 0
apLvl1R4:
.int 0
apLvl1R5:
.int 0
apLvl1R6:
.int 0
apLvl1R7:
.int 0
apLvl1Lr:
.int 0
apLvl2N:
.int 0
apLvl2R3:
.int 0
apLvl2R4:
.int 0
apLvl2R5:
.int 0
apLvl2R6:
.int 0
apLvl2R7:
.int 0
apLvl2Lr:
.int 0
apLvl3N:
.int 0
apLvl3R3:
.int 0
apLvl3R4:
.int 0
apLvl3R5:
.int 0
apLvl3R6:
.int 0
apLvl3R7:
.int 0
apLvl3Lr:
.int 0
apLvl4N:
.int 0
apLvl4R3:
.int 0
apLvl4R4:
.int 0
apLvl4R5:
.int 0
apLvl4R6:
.int 0
apLvl4R7:
.int 0
apLvl4Lr:
.int 0
apLvl5N:
.int 0
apLvl5R3:
.int 0
apLvl5R4:
.int 0
apLvl5R5:
.int 0
apLvl5R6:
.int 0
apLvl5R7:
.int 0
apLvl5Lr:
.int 0
apLvl6N:
.int 0
apLvl6R3:
.int 0
apLvl6R4:
.int 0
apLvl6R5:
.int 0
apLvl6R6:
.int 0
apLvl6R7:
.int 0
apLvl6Lr:
.int 0
apLvl7N:
.int 0
apLvl7R3:
.int 0
apLvl7R4:
.int 0
apLvl7R5:
.int 0
apLvl7R6:
.int 0
apLvl7R7:
.int 0
apLvl7Lr:
.int 0
apLvl8N:
.int 0
apLvl8R3:
.int 0
apLvl8R4:
.int 0
apLvl8R5:
.int 0
apLvl8R6:
.int 0
apLvl8R7:
.int 0
apLvl8Lr:
.int 0
apLvl10N:
.int 0
apLvl10R3:
.int 0
apLvl10R4:
.int 0
apLvl10R5:
.int 0
apLvl10R6:
.int 0
apLvl10R7:
.int 0
apLvl10Lr:
.int 0
apLvl11N:
.int 0
apLvl11R3:
.int 0
apLvl11R4:
.int 0
apLvl11R5:
.int 0
apLvl11R6:
.int 0
apLvl11R7:
.int 0
apLvl11Lr:
.int 0
apLvl13N:
.int 0
apLvl13R3:
.int 0
apLvl13R4:
.int 0
apLvl13R5:
.int 0
apLvl13R6:
.int 0
apLvl13R7:
.int 0
apLvl13Lr:
.int 0

; --- and the TWELVE levels of the call chain, probed at once ----------
; The stack unwinding gave the whole chain of the real chest. Rather than
; climbing one level per session, the arguments of the twelve levels are
; captured at once. The one whose arguments are ALL persistent (static or
; heap, not stack) will be replayable as is.
; --- AND THE CALL CHAIN OF THE WINDOW ITSELF -------------------------
; A FRAMING MISTAKE, fixed: the stack of the ITEM GRANT was unwound, while
; the WINDOW's is wanted. Opening a chest starts a sequence of actions --
; giving the item is one, showing the window and freezing Link is
; another. The grant's unwinding led to 0x021c0308, which only calls
; back the attribution path already replayed without success.
;
; The same mechanics, anchored on the SCREEN'S CREATION, where apOpnProSpy
; already sits. That chain goes up to what decides to display.
; --- KEEPING THE WINDOW OPEN ------------------------------------------
; MEASURED: called properly, the window opens COMPLETELY -- the
; chronology shows 0x036074b8 for the first time, the fourth transition
; step -- then closes in THREE FRAMES. +0x94 holds bit 0x100
; (close request) from the first sample, the activity byte drops at
; 40 ms, the screen is destroyed at 80 ms.
;
; In the real game the EVENT holds it while waiting for the A button.
; Python cannot stand in: a cross-process memory access costs
; milliseconds, and the loop corrected only 3 times while the screen
; died. It must be done HERE, once per frame.
;
; apHoldN is a FRAME COUNT, not a boolean: if the Python client dies,
; the hold goes out by itself. The same valve as apBlockGrants -- without
; it, a stuck window would stay with no way out for the player.
;
; A fixed value is WRITTEN rather than a bit cleared: clearing would need
; rlwinm or andi, which Cemu's assembler may not accept. 0x200 is the
; value measured on a displayed window.
apHoldN:
.int 0
apHoldQ:
.int 0
apWStkF:
.int 0
apWStkL0:
.int 0
apWStkL1:
.int 0
apWStkL2:
.int 0
apWStkL3:
.int 0
apWStkL4:
.int 0
apWStkL5:
.int 0
apWStkL6:
.int 0
apWStkL7:
.int 0
apWStkL8:
.int 0
apWStkL9:
.int 0
apWStkL10:
.int 0
apWStkL11:
.int 0
apWStkL12:
.int 0
apWStkL13:
.int 0
apStkF:
.int 0
apStkL0:
.int 0
apStkL1:
.int 0
apStkL2:
.int 0
apStkL3:
.int 0
apStkL4:
.int 0
apStkL5:
.int 0
apStkL6:
.int 0
apStkL7:
.int 0
apStkL8:
.int 0
apStkL9:
.int 0
apStkL10:
.int 0
apStkL11:
.int 0
apStkL12:
.int 0
apStkL13:
.int 0
apGrantBuf:
apGrantW0:
.int 0
apGrantW1:
.int 0
apGrantW2:
.int 0
apGrantW3:
.int 0
apGrantW4:
.int 0
apGrantW5:
.int 0
apGrantW6:
.int 0
apGrantW7:
.int 0
apGrantW8:
.int 0
apGrantW9:
.int 0
apGrantW10:
.int 0
apGrantW11:
.int 0
apGrantW12:
.int 0
apGrantW13:
.int 0
apGrantW14:
.int 0
apGrantW15:
.int 0
apGrantW16:
.int 0
apGrantW17:
.int 0
apGrantW18:
.int 0
apGrantW19:
.int 0
apGrantW20:
.int 0
apGrantW21:
.int 0
apGrantW22:
.int 0
apGrantW23:
.int 0
apGrantW24:
.int 0
apGrantW25:
.int 0
apGrantW26:
.int 0
apGrantW27:
.int 0
apGrantW28:
.int 0
apGrantW29:
.int 0
apGrantW30:
.int 0
apGrantW31:
.int 0

; --- and the mode is MEASURED rather than guessed ---------------------
; 0x03a40d20 serves 94 classes, so the probe sees other screens go by. No
; comparison in assembly: Cemu may not accept cmplw, and the project has
; already paid dearly for an assumed instruction. So an 8-entry shift
; register is kept, in lwz/stw only, and Python recognizes our screen
; in it.
apShowN:
.int 0
apShowT0:
.int 0
apShowT1:
.int 0
apShowT2:
.int 0
apShowT3:
.int 0
apShowT4:
.int 0
apShowT5:
.int 0
apShowT6:
.int 0
apShowT7:
.int 0
apShowM0:
.int 0
apShowM1:
.int 0
apShowM2:
.int 0
apShowM3:
.int 0
apShowM4:
.int 0
apShowM5:
.int 0
apShowM6:
.int 0
apShowM7:
.int 0
apShowL0:
.int 0
apShowL1:
.int 0
apShowL2:
.int 0
apShowL3:
.int 0
apShowL4:
.int 0
apShowL5:
.int 0
apShowL6:
.int 0
apShowL7:
.int 0

; --- GENERIC invoker on the per-frame hook --------------------------
; The other invoker (apOpnMode 8) lives in apGetWinProbe6, a function of
; the MessageGet_00 driver, and the patch keeps it behind apOpnOk.
; Measured consequence: cold, NO call goes off, and the request stays
; PENDING, then runs at the next real chest, which then shows our item.
; This block runs from the start, without prerequisite.
; It shares apCallAddr / apCallA1..A8 / apCallRet / apCallN.
apPfReq:
.int 0

; --- static resolution of the channel pointers ------------------------
; apResolveN counts the resolver's passes. It is the GUARD against the
; "field appended at the end of the block" trap: until Cemu is closed and
; reopened, these two words fall on CODE and read without error. A frame
; counter cannot exceed apTick -- the invariant that tells, on the Python
; side, "resolver present" from "stale patch".
apResolveN:
.int 0
; The screen table (manager+0x18), 0 until the UI is ready. It also
; witnesses a live UI: 0x035ff8fc dereferences the screen manager
; without testing it, so nothing may go before.
apScrTable:
.int 0
.align 4

apProbe:
    ; hook 1: its original instruction is replayed at apDone
    lis   r11, apTick@ha

    lwz   r12, apTick@l(r11)
    addi  r12, r12, 1
    stw   r12, apTick@l(r11)
    stw   r1, apR1Frame@l(r11)      ; which stack does this hook run on?

apResolve:
    ; --- RESOLVE the channel pointers, instead of CAPTURING them ---------
    ; Each channel used to wait for a probe to see its object go by: an item
    ; had to be picked up, a center message triggered and a real dialog box
    ; seen AT EVERY game start before anything answered. Yet the four
    ; pointers are all reachable from globals:
    ;
    ;
    ;   PauseMenuDataMgr   *(0x10469978)                    singleton
    ;   PickUpWin          screen table [0x28]
    ;   center message     *(table[0x25] + 0x1b84)
    ;   dialog box         table[0x26]     (created on demand by the game)
    ;
    ; Each value is rewritten EVERY FRAME: a screen destroyed then recreated
    ; (the dialog box always is) therefore never leaves a stale pointer
    ; behind it. But a CAPTURE field is never reset: when the source is 0,
    ; it is skipped. So the resolver can only add, never destroy what the
    ; probes already knew.
    ; apScrTable is our own witness: it is reset to 0 every frame,
    ; otherwise it would outlive the UI and lie.
    ;
    ; Destroys only r12: r11 stays the cave's page throughout, and
    ; apScrTable serves as the working variable between steps.

    lis   r12, 0x1046
    ori   r12, r12, 0x9978
    lwz   r12, 0(r12)               ; *(0x10469978) = PauseMenuDataMgr
    cmpwi r12, 0
    beq   apResolveScr
    stw   r12, apPmdmThis@l(r11)

apResolveScr:
    li    r12, 0
    stw   r12, apScrTable@l(r11)    ; 0 by default: UI not ready
    lis   r12, 0x1047
    ori   r12, r12, 0xe650
    lwz   r12, 0(r12)               ; *(0x1047E650) = screen manager
    cmpwi r12, 0
    beq   apResolveDone
    lwz   r12, 0x14(r12)            ; nombre d'emplacements

    ; --- refuse anything that is not the measured table -------------------
    ; The game itself indexes the table only when the index fits this count;
    ; otherwise it falls back to slot 0. Rather than replaying that fallback --
    ; which would give ANY SCREEN and pass it off as ours -- the 99 slots
    ; read on 1.5.0 EUR are required. Any other value leaves apScrTable at 0:
    ; the tools refuse cleanly.
    cmpwi r12, 0x63
    bne   apResolveDone

    lis   r12, 0x1047
    ori   r12, r12, 0xe650
    lwz   r12, 0(r12)
    lwz   r12, 0x18(r12)            ; the table of the 99 screens
    cmpwi r12, 0
    beq   apResolveDone
    stw   r12, apScrTable@l(r11)

    ; --- item notification: screen 0x28 (PickUpWin) ----------------------
    ; Index established by measurement: the only screen whose +0x1b68 holds
    ; a pool of 7 rows of 0x14c bytes -- the layout the push loop
    ; walks (0x3c = count, 0x44 = array, row+0x149 = rank).
    lwz   r12, 0xa0(r12)            ; 0x28 * 4
    cmpwi r12, 0
    beq   apResolveMs
    stw   r12, apScreenThis@l(r11)
    addi  r12, r12, 0x1b68
    stw   r12, apListThis@l(r11)

apResolveMs:
    ; --- center message: *(screen 0x25 + 0x1b84) --------------------------
    ; Read in the game: 0x02fbcaf8, a method of screen 0x25, does
    ; `lwz r3, 0x1b84(r3)` before jumping into 0x02ed1f7c -- the push.
    ; The object obtained does hold the list at +0x14c and its count at +0x154.
    lwz   r12, apScrTable@l(r11)
    lwz   r12, 0x94(r12)            ; 0x25 * 4
    cmpwi r12, 0
    beq   apResolveDlg
    lwz   r12, 0x1b84(r12)
    cmpwi r12, 0
    beq   apResolveDlg
    stw   r12, apMS1This@l(r11)
    stw   r12, apPushThis@l(r11)

apResolveDlg:
    ; --- dialog box: screen 0x26 ------------------------------------------
    ; The slot is EMPTY most of the time: 0x035ff8fc creates the screen
    ; itself (`li r3, 0x26 ; bl 0x033924c4`) and destroys it on closing.
    ; So the opening cannot depend on this pointer -- it is only kept up to
    ; date for the block that writes the text, in the same frame.
    lwz   r12, apScrTable@l(r11)
    lwz   r12, 0x98(r12)            ; 0x26 * 4
    cmpwi r12, 0
    beq   apResolveDur
    stw   r12, apDlgThis@l(r11)

apResolveDur:
    ; --- notification duration -------------------------------------------
    ; The probe read it on a real pickup (f31 in 0x02ffaaec); cold it was 0,
    ; and a zero duration shows nothing. The constant the game passes to
    ; itself is used instead, 0x1024C1FC = 5.0f.
    lwz   r12, apDuration@l(r11)
    cmpwi r12, 0
    bne   apResolveDone
    lis   r12, 0x1024
    ori   r12, r12, 0xc1fc
    lwz   r12, 0(r12)
    stw   r12, apDuration@l(r11)

apResolveDone:
    lwz   r12, apResolveN@l(r11)
    addi  r12, r12, 1
    stw   r12, apResolveN@l(r11)

    ; --- valve: the blocking of granted items goes out by itself --------
    ; apBlockGrants is a FRAME COUNT, not a boolean. If the Python client
    ; dies with the blocking armed, the field is no longer refreshed and the
    ; game goes back to normal by itself. Without it, chests would stay silent
    ; with nothing to explain it -- and the field survives a save reload, so
    ; the player would have no simple way out.
    lwz   r12, apBlockGrants@l(r11)
    cmpwi r12, 0
    beq   apNoDecay
    addi  r12, r12, -1
    stw   r12, apBlockGrants@l(r11)
apNoDecay:

    ; --- echo mailbox (link test) -----------------------------------------
    lwz   r12, apInbox@l(r11)
    cmpwi r12, 0
    beq   apCheckRune
    stw   r12, apOutbox@l(r11)
    stw   r12, apLastSeen@l(r11)
    li    r12, 0
    stw   r12, apInbox@l(r11)

apCheckRune:
    ; --- calling the game's rune counter ourselves -----------------------
    ; FUN_0307B5B0 queries the five predicates and adds up. Comparing it
    ; before and after a flag write tells whether the game SEES that write live.
    lwz   r12, apRuneReq@l(r11)
    cmpwi r12, 0
    beq   apCheckNotify

    li    r12, 0
    stw   r12, apRuneReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    lis   r12, 0x0307
    ori   r12, r12, 0xb5b0          ; FUN_0307B5B0, rune counter
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    stw   r3, apRuneCount@l(r11)    ; the count comes back in r3

    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apRuneDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apRuneDone@l(r11)

apCheckNotify:
    ; --- ask for the item obtained notification ---------------------------
    ; Calls FUN_02FFA888(PickUpWin screen, SafeString* name), identified by
    ; probing: the only function of the area triggered once per pickup.
    lwz   r12, apNotifyReq@l(r11)
    cmpwi r12, 0
    beq   apCheckPlay           ; not apCheckGive: jumping there
                                ; would skip the block
                                ; of the center message every frame
                                ; when no notification waits

    li    r12, 0
    stw   r12, apNotifyReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    lis   r12, apItemName@ha
    addi  r12, r12, apItemName@l
    stw   r12, apNameCstr@l(r11)
    lis   r12, 0x1026
    ori   r12, r12, 0x3910
    stw   r12, apNameVtable@l(r11)

    ; --- OPEN the screen before filling a row ------------------------------
    ; A missing step, found by resolving the screen statically: the row was
    ; filled (rank 0 set, pool consistent) but NOTHING showed, because screen
    ; 0x28 stayed closed -- activity byte 0xff in manager+0x604. It did not
    ; show while a real pickup had to come first: IT opened the screen.
    ;
    ; The dispatch is not replayed: 0x02FFABFC(screen, _, 0) is precisely the
    ; game function that only calls vtable[0x2c](screen, 3), the opening,
    ; and stops there when its 3rd argument is null.
    lwz   r3, apScreenThis@l(r11)
    cmpwi r3, 0
    beq   apNotifyEnd               ; screen not resolved: try nothing
    li    r4, 0
    li    r5, 0
    lis   r12, 0x02FF
    ori   r12, r12, 0xabfc
    mtctr r12
    bctrl

    lis   r11, apTick@ha            ; the call destroyed r11

    ; --- choose a FREE row in the pool ------------------------------------
    ; That is what the enclosing function does and we did not: the same row
    ; was always reused, hence replacing instead of stacking. Its loop is
    ; redone without calling it, because its first argument is the screen --
    ; a transient object whose captured pointer ends up dangling, which
    ; crashed the game.
    ;   list->0x3c = number of rows
    ;   list->0x44 = array of pointers
    ;   0x02FFA5E0(row) returns 0 when the row is free
    ; The loop state lives in the cave: calling the predicate destroys r3-r12.

    lwz   r12, apListThis@l(r11)
    cmpwi r12, 0
    beq   apNotifyEnd

    lwz   r10, 0x44(r12)
    stw   r10, apIterPtr@l(r11)
    lwz   r10, 0x3c(r12)
    stw   r10, apIterLeft@l(r11)

apFindLoop:
    lis   r11, apTick@ha
    lwz   r12, apIterLeft@l(r11)
    cmpwi r12, 0
    beq   apNotifyEnd               ; no free row: show nothing
    addi  r12, r12, -1
    stw   r12, apIterLeft@l(r11)

    lwz   r12, apIterPtr@l(r11)
    lwz   r3, 0(r12)
    addi  r12, r12, 4
    stw   r12, apIterPtr@l(r11)

    cmpwi r3, 0
    beq   apFindLoop

    stw   r3, apCandidate@l(r11)
    lis   r12, 0x02FF
    ori   r12, r12, 0xa5e0
    mtctr r12
    bctrl

    cmpwi r3, 0
    bne   apFindLoop                ; occupied: next row

    ; --- move the rows already shown down --------------------------------
    ; The caller's second loop, just as essential: without it the existing
    ; entries do not move down one step and the new one overlaps.
    ; The byte at row+0x149 is the rank; it is incremented on every
    ; OCCUPIED row (non-zero predicate).
    lwz   r12, apListThis@l(r11)
    lwz   r10, 0x44(r12)
    stw   r10, apIterPtr@l(r11)
    lwz   r10, 0x3c(r12)
    stw   r10, apIterLeft@l(r11)

apAgeLoop:
    lis   r11, apTick@ha
    lwz   r12, apIterLeft@l(r11)
    cmpwi r12, 0
    beq   apAgeDone
    addi  r12, r12, -1
    stw   r12, apIterLeft@l(r11)

    lwz   r12, apIterPtr@l(r11)
    lwz   r3, 0(r12)
    addi  r12, r12, 4
    stw   r12, apIterPtr@l(r11)

    cmpwi r3, 0
    beq   apAgeLoop

    stw   r3, apCandidate2@l(r11)
    lis   r12, 0x02FF
    ori   r12, r12, 0xa5e0
    mtctr r12
    bctrl

    cmpwi r3, 0
    beq   apAgeLoop                 ; free row: nothing to shift

    lis   r11, apTick@ha
    lwz   r12, apCandidate2@l(r11)
    lbz   r10, 0x149(r12)
    addi  r10, r10, 1
    stb   r10, 0x149(r12)
    b     apAgeLoop

apAgeDone:
    ; --- free row found: prepare, fill, show ------------------------------
    lis   r11, apTick@ha
    stfs  f1, apSaveF1@l(r11)
    lfs   f1, apDuration@l(r11)     ; the duration the game uses itself
    lwz   r3, apCandidate@l(r11)
    lis   r12, 0x02FF
    ori   r12, r12, 0xa5f4
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r3, apCandidate@l(r11)
    lis   r4, apNameCstr@ha
    addi  r4, r4, apNameCstr@l
    lis   r12, 0x02FF
    ori   r12, r12, 0xa888
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r3, apCandidate@l(r11)
    lis   r12, 0x02FF
    ori   r12, r12, 0xaa34
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lfs   f1, apSaveF1@l(r11)

apNotifyEnd:
    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apNotifyDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apNotifyDone@l(r11)

apCheckPlay:
    ; --- replay the game's push -------------------------------------------
    ; 0x02ed1f7c(this, a, b) increments the list counter this+0x154; it is
    ; the step that was missing, and without it 0x02ed1e1c leaves through `ble`
    ; at its entry. The arguments are not guessed: the spy apPushSpy reads
    ; them when the GAME shows a message, and they are replayed as they are.
    lwz   r12, apPlayReq@l(r11)
    cmpwi r12, 0
    beq   apCheckMsg

    lwz   r12, apPushThis@l(r11)
    cmpwi r12, 0
    beq   apCheckMsg               ; never seen: try nothing

    li    r12, 0
    stw   r12, apPlayReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    ; The 3rd argument is a POINTER: 0x02ed1f7c dereferences 0x0(r5) and
    ; 0x4(r5), the layout of a sead::SafeString {cstr, vtable}. It is the
    ; text substituted in the message -- the "Spear"/"Sword" seen at this+0x17c.
    ; Replaying the pointer read on the game points it at a dead stack,
    ; hence the crash. Ours is therefore built, on apText.
    lis   r12, apText@ha
    addi  r12, r12, apText@l
    stw   r12, apMsgCstr@l(r11)
    lis   r12, 0x1026
    ori   r12, r12, 0x3910          ; vtable of sead::SafeString
    stw   r12, apMsgVtable@l(r11)

    lwz   r3, apPushThis@l(r11)
    lwz   r4, apPlayA@l(r11)
    lwz   r12, apPlayRaw@l(r11)
    cmpwi r12, 0
    beq   apPlayOwn
    lwz   r5, apPlayB@l(r11)        ; --raw: replay the game's pointer
    b     apPlayCall
apPlayOwn:
    lis   r5, apMsgCstr@ha
    addi  r5, r5, apMsgCstr@l
apPlayCall:
    lis   r12, 0x02ed
    ori   r12, r12, 0x1f7c
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apPlayDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apPlayDone@l(r11)

apCheckMsg:
    ; --- trigger the center message ---------------------------------------
    ; 0x02ed1e1c(this, arg): a public API that pushes the request then calls
    ; 0x02ed1a68 itself, which fetches the label in MainScreen_00.
    ; 0x02ed1a68 was found by probing (2 calls against 602 for the per-frame
    ; functions); its caller, by looking for what computes this+0x14c.
    lwz   r12, apMSReq@l(r11)
    cmpwi r12, 0
    beq   apCheckTips           ; the NEXT block, not the last: jumping
                                ; straight to apCheckGive would make the whole
                                ; tips block unreachable

    lwz   r12, apMS1This@l(r11)
    cmpwi r12, 0
    beq   apCheckTips               ; never seen: try nothing

    li    r12, 0
    stw   r12, apMSReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    ; --- call the PUBLIC API, not the display function --------------------
    ; 0x02ed1e1c(this, arg) pushes the request through 0x036028e0 then calls
    ; 0x02ed1a68 itself. That was missing: setting index and state by hand
    ; triggered nothing, because the push into the list this+0x14c had not
    ; happened. Found by looking for what computes that list's address:
    ; only two sites, besides the consumer.
    ; r4 is NOT the index: 0x036028e0 only does `cmpwi r4, 0` to choose
    ; between two states (1 or 3) written into this+0x8c. The index comes
    ; from this+0xbc -- the field already known to drive the content.
    lwz   r3, apMS1This@l(r11)
    lwz   r12, apMSIndex@l(r11)
    stw   r12, 0xbc(r3)

    ; --- read what the function will test, IN THE SAME FRAME -------------
    ; Reading these fields from Python gives the state of an earlier frame,
    ; and three deductions made on the disassembly were already contradicted.
    lwz   r12, 0x154(r3)
    stw   r12, apMSDbg154@l(r11)
    lwz   r12, 0x150(r3)
    stw   r12, apMSDbg150@l(r11)
    lwz   r12, 0x8c(r3)
    stw   r12, apMSDbgC@l(r11)

    lwz   r4, apMSFlag@l(r11)
    lis   r12, 0x02ed
    ori   r12, r12, 0x1e1c
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    stw   r3, apMSRet@l(r11)        ; return value, 0 = refused

apMsgRestored:
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apMSDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apMSDone@l(r11)

apCheckTips:
    ; --- show the blue tip frame -----------------------------------------
    ; 0x02fd4848(this, index) fetches the label number `index` in the
    ; 23-entry table at 0x10542f7c, resolves the message in
    ; LayoutMsg/MessageTipsRunTime_00, sets it on the pane T_Text_00 then plays
    ; the appearance animation. The `this` is not searched: the probe
    ; apTipsProbe1 captures it on the per-frame update.
    lwz   r12, apTipsReq@l(r11)
    cmpwi r12, 0
    beq   apCheckTipsText

    lwz   r12, apTipsThis@l(r11)
    cmpwi r12, 0
    beq   apCheckTipsText           ; never seen: try nothing

    li    r12, 0
    stw   r12, apTipsReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    lwz   r3, apTipsThis@l(r11)
    lwz   r4, apTipsIndex@l(r11)
    lis   r12, 0x02fd
    ori   r12, r12, 0x4848
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apTipsDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apTipsDone@l(r11)

apCheckTipsText:
    ; --- write OUR text into the frame ------------------------------------
    ; 0x03082d88(layout, sead::SafeString* paneName, textObject) is the call
    ; 0x02fd4848 itself makes right after resolving the message. Replayed
    ; here with our own text object, it replaces the pane's content without
    ; touching the message arena -- so with no ceiling inherited from the
    ; carrier and nothing to restore.
    ; The text object is eight bytes { const char16_t* ; length }: it is what
    ; 0x03082c70 copies into 0x02fd4848's buffer (0x03a38d9c only transfers
    ; two words). apTipsSpy reads the pair the game uses.
    lwz   r12, apTipsTextReq@l(r11)
    cmpwi r12, 0
    beq   apCheckDlg

    lwz   r12, apTipsThis@l(r11)
    cmpwi r12, 0
    beq   apCheckDlg               ; never seen: try nothing

    li    r12, 0
    stw   r12, apTipsTextReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    ; sead::SafeString on 'T_Text_00' (0x1024609c), the game's own string
    lis   r12, 0x1024
    ori   r12, r12, 0x609c
    stw   r12, apPaneCstr@l(r11)
    lis   r12, 0x1026
    ori   r12, r12, 0x3910
    stw   r12, apPaneVtable@l(r11)

    ; text object: apText, in UTF-16BE, and the length set by Python
    lis   r12, apText@ha
    addi  r12, r12, apText@l
    stw   r12, apTipsStrPtr@l(r11)
    lwz   r12, apTipsTextLen@l(r11)
    stw   r12, apTipsStrLen@l(r11)

    lwz   r3, apTipsThis@l(r11)
    lwz   r3, 0x18(r3)              ; the widget's layout
    lis   r4, apPaneCstr@ha
    addi  r4, r4, apPaneCstr@l
    lis   r5, apTipsStrPtr@ha
    addi  r5, r5, apTipsStrPtr@l
    lis   r12, 0x0308
    ori   r12, r12, 0x2d88
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apTipsTextDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apTipsTextDone@l(r11)

apCheckDlg:
    ; --- open the dialog window on an (archive, label) pair ---------------
    lwz   r12, apDlgReq@l(r11)
    cmpwi r12, 0
    beq   apCheckDlgText

    ; --- the only real prerequisite: that the UI exists ------------------
    ; The lock was apDlgOpen0N ("no real box seen since the start"), and it
    ; protected nothing: the three replayed arguments are forced to zero
    ; anyway, because 0x035ff8fc only reads them on the branch with a
    ; non-zero flag. What is really needed is that *(0x1047E650) exists:
    ; the function dereferences it without testing it.
    ; Screen 0x26 need not exist -- the function creates it itself.
    lwz   r12, apScrTable@l(r11)
    cmpwi r12, 0
    beq   apCheckDlgText            ; UI not ready: try nothing

    li    r12, 0
    stw   r12, apDlgReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    lis   r12, apArcBuf@ha
    addi  r12, r12, apArcBuf@l
    stw   r12, apDlgArcCstr@l(r11)
    lis   r12, 0x1026
    ori   r12, r12, 0x3910
    stw   r12, apDlgArcVtable@l(r11)
    lis   r12, apLblBuf@ha
    addi  r12, r12, apLblBuf@l
    stw   r12, apDlgLblCstr@l(r11)
    lis   r12, 0x1026
    ori   r12, r12, 0x3910
    stw   r12, apDlgLblVtable@l(r11)

    li    r3, 0                     ; ignored by the function
    lis   r4, apDlgArcCstr@ha
    addi  r4, r4, apDlgArcCstr@l
    lis   r5, apDlgLblCstr@ha
    addi  r5, r5, apDlgLblCstr@l
    lwz   r6, apDlgArg6@l(r11)      ; read on a real call
    lwz   r7, apDlgArg7@l(r11)
    lwz   r8, apDlgArg8@l(r11)
    lis   r12, 0x035f
    ori   r12, r12, 0xf8fc
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apDlgDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apDlgDone@l(r11)

apCheckDlgText:
    ; --- put OUR text in place of the one the window just resolved -------
    ; 0x035fb5f8 stores { text, length } in this+0x1d0; ours is written over
    ; it. No call: two writes, in the same frame as the opening since both
    ; blocks follow each other.
    ; The length is in UTF-16 UNITS, terminator excluded -- measured on the
    ; tip frame: a carrier of 101 units, word1 read = 100.
    lwz   r12, apDlgTextReq@l(r11)
    cmpwi r12, 0
    beq   apCheckGetWin             ; the NEXT block, not the last

    lwz   r12, apDlgThis@l(r11)
    cmpwi r12, 0
    beq   apCheckGetWin             ; never seen: try nothing

    li    r12, 0
    stw   r12, apDlgTextReq@l(r11)

    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    lwz   r3, apDlgThis@l(r11)
    lwz   r4, apDlgStrPtr@l(r11)
    stw   r4, 0x1d0(r3)
    lwz   r4, apDlgStrLen@l(r11)
    stw   r4, 0x1d4(r3)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)

    lwz   r12, apDlgTextDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apDlgTextDone@l(r11)

apCheckGetWin:
    ; --- replay the get window with our own text -------------------------
    ; The driver 0x03a3ec0c is called again with the arguments read on a real
    ; trigger, except r6: in place of the game's `const char*`, ours.
    ; The same principle as the dialog box replay -- the staging is not
    ; recreated, the game's is asked again with a substituted text.
    lwz   r12, apGetDrvReq@l(r11)
    cmpwi r12, 0
    beq   apCheckGive

    lwz   r12, apGetWinOk@l(r11)
    cmpwi r12, 0
    beq   apCheckGive               ; MessageGet_00 never seen opening: the
                                    ; arguments to replay are unknown

    li    r12, 0
    stw   r12, apGetDrvReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    ; r6 stays the game's screen name. Putting our text there crashed: this
    ; function opens a screen BY ITS NAME, it shows nothing itself.
    lwz   r3, apGetWinCThis@l(r11)
    lwz   r4, apGetWinCA4@l(r11)
    lwz   r5, apGetWinCA5@l(r11)
    lwz   r6, apGetWinCA6@l(r11)
    lwz   r7, apGetWinCA7@l(r11)
    lwz   r8, apGetWinCA8@l(r11)
    lwz   r9, apGetWinCA9@l(r11)
    lis   r12, 0x03a3
    ori   r12, r12, 0xec0c
    mtctr r12
    bctrl

    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apGetDrvDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetDrvDone@l(r11)

apCheckGive:
    lwz   r12, apGiveReq@l(r11)
    cmpwi r12, 0
    beq   apCheckCall

    lwz   r12, apPmdmThis@l(r11)    ; has the this been captured yet?
    cmpwi r12, 0
    beq   apCheckCall

    li    r12, 0                    ; consume BEFORE calling, so as not to
    stw   r12, apGiveReq@l(r11)     ; loop forever if itemGet crashes

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    ; build the sead::SafeString on the fly
    lis   r12, apItemName@ha
    addi  r12, r12, apItemName@l
    stw   r12, apNameCstr@l(r11)
    lis   r12, 0x1026
    ori   r12, r12, 0x3910          ; vtable of sead::SafeString
    stw   r12, apNameVtable@l(r11)

    lwz   r3, apPmdmThis@l(r11)     ; this
    lis   r4, apNameCstr@ha
    addi  r4, r4, apNameCstr@l      ; const sead::SafeString&
    lwz   r5, apGiveValue@l(r11)    ; quantity
    li    r6, 0                     ; no weapon modifier

    ; --- an indirect call, not "bla" -----------------------------------
    ; bla only has a signed 26-bit displacement, that is +/-32 MB. itemGet is at
    ; 0x02EB53E4, beyond 0x01FFFFFC: the sign bit is set and the address
    ; becomes 0xFEEB53E4. That is exactly what crashed the game.
    ; ori rather than addi for the low half: addi reads it as signed.
    lis   r12, 0x02EB
    ori   r12, r12, 0x53E4          ; itemGet
    mtctr r12
    bctrl

    lis   r11, apTick@ha            ; the call destroyed r11
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apGiveDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apGiveDone@l(r11)

apCheckCall:
    ; --- call anything, from the per-frame hook -------------------------
    ; The same protocol as apOpnMode 8, but without a lock: this hook runs
    ; every frame from the game's start.
    ; CAUTION: the patch documents a thread affinity for REPLAYING the
    ; opening site (stack 0x12b3c510 against 0x0e201270 here) -- four
    ; crashes. It holds for the modes that touch a screen's inside; for a
    ; clean call such as 0x035fe7f4 it is still to be measured.
    lwz   r12, apPfReq@l(r11)
    cmpwi r12, 0
    beq   apDone

    li    r12, 0                    ; consume BEFORE calling, so as not to
    stw   r12, apPfReq@l(r11)       ; loop forever if the call crashes

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    lwz   r12, apCallAddr@l(r11)
    mtctr r12
    lwz   r3, apCallA1@l(r11)
    lwz   r4, apCallA2@l(r11)
    lwz   r5, apCallA3@l(r11)
    lwz   r6, apCallA4@l(r11)
    lwz   r7, apCallA5@l(r11)
    lwz   r8, apCallA6@l(r11)
    lwz   r9, apCallA7@l(r11)
    lwz   r10, apCallA8@l(r11)
    bctrl

    lis   r11, apTick@ha            ; the call destroyed r11
    stw   r3, apCallRet@l(r11)
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apCallN@l(r11)
    addi  r12, r12, 1
    stw   r12, apCallN@l(r11)

apDone:
    lwz   r12, 0x0(r30)         ; --- ORIGINAL hook 1, replayed last ---
    blr

apItemGetSpy:
    stw   r0, 0x6c(r1)          ; --- ORIGINAL hook 2, replayed first ---
                                ; it saves LR for the epilogue:
                                ; replaying it BEFORE jumping there is what
                                ; makes the short circuit safe.

    lis   r11, apTick@ha
    lwz   r12, apItemGetCount@l(r11)
    addi  r12, r12, 1
    stw   r12, apItemGetCount@l(r11)
    stw   r24, apPmdmThis@l(r11)      ; this of PauseMenuDataMgr
    stw   r25, apLastNamePtr@l(r11)   ; SafeString* of the name
    stw   r26, apLastValue@l(r11)     ; quantity

    ; --- log: { call site, name cstr, quantity } -------------------------
    ; r11 is sacrificed to read *(r25) then reloaded: the only way to hold
    ; three values with two working registers, without assuming that r0 is
    ; dead -- an assumption never checked, so never made.
    lwz   r12, apIgLeft@l(r11)
    cmpwi r12, 0
    beq   apIgBlock
    addi  r12, r12, -1
    stw   r12, apIgLeft@l(r11)
    lwz   r12, apIgPtr@l(r11)
    stw   r0, 0x0(r12)                ; return address = call site
    stw   r26, 0x8(r12)               ; quantity
    lwz   r11, 0x0(r25)               ; the name's cstr
    stw   r11, 0x4(r12)
    lis   r11, apTick@ha              ; reload the cave's base
    addi  r12, r12, 12
    stw   r12, apIgPtr@l(r11)

apIgBlock:
    ; --- short circuit: leave without adding anything --------------------
    ; Two independent commands:
    ;   apBlockReq    neutralises the NEXT item, whatever its source
    ;   apBlockGrants neutralises Obj_DungeonClearSeal only, recognized by
    ;                 the marker set by apGrantSpy, then by r25's SafeString.
    lwz   r12, apBlockReq@l(r11)
    cmpwi r12, 0
    bne   apIgDoBlock

    lwz   r12, apBlockGrants@l(r11)
    cmpwi r12, 0
    beq   apIgClearMark
    lwz   r12, apGrantMark@l(r11)
    cmpwi r12, 0
    beq   apIgClearMark

    ; SELECTIVE FILTER, measured at the itemGet site: r25 is the name's
    ; SafeString, and *(r25) its ASCII cstr. A byte-by-byte comparison: Cemu's
    ; assembler accepts lbz/cmpwi, while cmpw/cmplw have not been validated.
    ; A mismatch reloads the cave's base before taking the normal path.
    lwz   r12, 0x0(r25)
    lbz   r11, 0x00(r12)
    cmpwi r11, 0x4f                    ; O
    bne   apIgNotDungeonSeal
    lbz   r11, 0x01(r12)
    cmpwi r11, 0x62                    ; b
    bne   apIgNotDungeonSeal
    lbz   r11, 0x02(r12)
    cmpwi r11, 0x6a                    ; j
    bne   apIgNotDungeonSeal
    lbz   r11, 0x03(r12)
    cmpwi r11, 0x5f                    ; _
    bne   apIgNotDungeonSeal
    lbz   r11, 0x04(r12)
    cmpwi r11, 0x44                    ; D
    bne   apIgNotDungeonSeal
    lbz   r11, 0x05(r12)
    cmpwi r11, 0x75                    ; u
    bne   apIgNotDungeonSeal
    lbz   r11, 0x06(r12)
    cmpwi r11, 0x6e                    ; n
    bne   apIgNotDungeonSeal
    lbz   r11, 0x07(r12)
    cmpwi r11, 0x67                    ; g
    bne   apIgNotDungeonSeal
    lbz   r11, 0x08(r12)
    cmpwi r11, 0x65                    ; e
    bne   apIgNotDungeonSeal
    lbz   r11, 0x09(r12)
    cmpwi r11, 0x6f                    ; o
    bne   apIgNotDungeonSeal
    lbz   r11, 0x0a(r12)
    cmpwi r11, 0x6e                    ; n
    bne   apIgNotDungeonSeal
    lbz   r11, 0x0b(r12)
    cmpwi r11, 0x43                    ; C
    bne   apIgNotDungeonSeal
    lbz   r11, 0x0c(r12)
    cmpwi r11, 0x6c                    ; l
    bne   apIgNotDungeonSeal
    lbz   r11, 0x0d(r12)
    cmpwi r11, 0x65                    ; e
    bne   apIgNotDungeonSeal
    lbz   r11, 0x0e(r12)
    cmpwi r11, 0x61                    ; a
    bne   apIgNotDungeonSeal
    lbz   r11, 0x0f(r12)
    cmpwi r11, 0x72                    ; r
    bne   apIgNotDungeonSeal
    lbz   r11, 0x10(r12)
    cmpwi r11, 0x53                    ; S
    bne   apIgNotDungeonSeal
    lbz   r11, 0x11(r12)
    cmpwi r11, 0x65                    ; e
    bne   apIgNotDungeonSeal
    lbz   r11, 0x12(r12)
    cmpwi r11, 0x61                    ; a
    bne   apIgNotDungeonSeal
    lbz   r11, 0x13(r12)
    cmpwi r11, 0x6c                    ; l
    bne   apIgNotDungeonSeal
    lbz   r11, 0x14(r12)
    cmpwi r11, 0x00                    ; terminator
    bne   apIgNotDungeonSeal
    lis   r11, apTick@ha
    b     apIgDoBlock

apIgNotDungeonSeal:
    lis   r11, apTick@ha
    b     apIgClearMark

apIgDoBlock:

    li    r12, 0                      ; consume BEFORE jumping
    stw   r12, apBlockReq@l(r11)
    lwz   r12, apBlockDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apBlockDone@l(r11)

    li    r12, 0                      ; the marker must not be used again
    stw   r12, apGrantMark@l(r11)

    lis   r12, 0x02eb
    ori   r12, r12, 0x5894            ; itemGet's epilogue
    mtlr  r12
    blr                               ; -> lmw / mtlr / addi r1 / blr

apIgClearMark:
    li    r12, 0                      ; consume the marker even without blocking,
    stw   r12, apGrantMark@l(r11)     ; otherwise it spills onto the next pickup
    blr

; --- capture probe on 0x02FFAAF0, the whole notification function ---
; Placed at 0x02FFAB18, after the stw r0,0x2c(r1) that saves LR: hooking
; earlier would destroy the return address. At this point r3 is still the
; screen, and f31 already holds the float argument (fmr f31,f1 at 0x02FFAB04).
apProbeScreen:
    addi  r29, r3, 0x1b68           ; original
    lis   r11, apTick@ha
    stw   r3, apScreenThis@l(r11)   ; the screen, not a row of the pool
    stw   r29, apListThis@l(r11)    ; screen + 0x1b68: the row pool
    stfs  f31, apDuration@l(r11)    ; the duration the game gives itself
    blr


apMSProbe0:                      ; function 0x02ecbca4
    lwz   r3, 0xc(r27)          ; original
    lis   r11, apTick@ha
    stw   r27, apMSThis@l(r11)   ; the original 'this'
    lwz   r12, apMSMask@l(r11)
    ori   r12, r12, 0x0001
    stw   r12, apMSMask@l(r11)
    lwz   r12, apMS0@l(r11)
    addi  r12, r12, 1
    stw   r12, apMS0@l(r11)
    blr

apMSProbe1:                      ; function 0x02ed1a68
    lwz   r5, 0x154(r28)          ; original
    lis   r11, apTick@ha
    stw   r28, apMS1This@l(r11)  ; a dedicated field: apMSThis is
                                ; overwritten by MS5, which runs
                                ; every frame
    lwz   r12, apMSMask@l(r11)
    ori   r12, r12, 0x0002
    stw   r12, apMSMask@l(r11)
    lwz   r12, apMS1@l(r11)
    addi  r12, r12, 1
    stw   r12, apMS1@l(r11)
    blr

apMSProbe2:                      ; function 0x02f21984
    ; Anchored on the stw that saves LR, and NOT on the next lis:
    ; that one loads r12, which 0x02f2199c reads two instructions
    ; later. The probe uses r12 as a working register, so it
    ; would have destroyed it -- which crashed the game at start.
    stw   r0, 0x5c(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apMSMask@l(r11)
    ori   r12, r12, 0x0004
    stw   r12, apMSMask@l(r11)
    lwz   r12, apMS2@l(r11)
    addi  r12, r12, 1
    stw   r12, apMS2@l(r11)
    blr

apMSProbe3:                      ; function 0x02f8b2bc
    addi  r3, r1, 0x40          ; original
    lis   r11, apTick@ha
    stw   r27, apMSThis@l(r11)   ; the original 'this'
    lwz   r12, apMSMask@l(r11)
    ori   r12, r12, 0x0008
    stw   r12, apMSMask@l(r11)
    lwz   r12, apMS3@l(r11)
    addi  r12, r12, 1
    stw   r12, apMS3@l(r11)
    blr

apMSProbe4:                      ; function 0x02fc0f58
    stfs  f29, 0x1b8(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apMSMask@l(r11)
    ori   r12, r12, 0x0010
    stw   r12, apMSMask@l(r11)
    lwz   r12, apMS4@l(r11)
    addi  r12, r12, 1
    stw   r12, apMS4@l(r11)
    blr

apMSProbe5:                      ; function 0x02fc2dec
    lwz   r8, 0x0(r30)          ; original
    lis   r11, apTick@ha
    stw   r30, apMSThis@l(r11)   ; the original 'this'
    lwz   r12, apMSMask@l(r11)
    ori   r12, r12, 0x0020
    stw   r12, apMSMask@l(r11)
    lwz   r12, apMS5@l(r11)
    addi  r12, r12, 1
    stw   r12, apMS5@l(r11)
    blr

apMSTraceMid:                    ; 0x02ed1e70, after the first three tests
    lwz   r0, 0x8c(r29)        ; original -- r0 is NOT touched afterwards,
                               ; the comparisons that follow depend on it
    lis   r11, apTick@ha
    stw   r0, apMSDbg8c@l(r11) ; the value the function REALLY sees
    lwz   r12, apMSMid@l(r11)
    addi  r12, r12, 1
    stw   r12, apMSMid@l(r11)
    blr

apPushSpy:                       ; 0x02ed1f98, in 0x02ed1f7c
    addi  r27, r24, 0x110      ; original
    lis   r11, apTick@ha
    stw   r24, apPushThis@l(r11)   ; this
    stw   r29, apPushA@l(r11)      ; 2nd argument
    stw   r30, apPushB@l(r11)      ; 3rd argument
    lwz   r12, apPushN@l(r11)
    addi  r12, r12, 1
    stw   r12, apPushN@l(r11)
    blr

apMSTracePass:                   ; 0x02ed1e98, right before bl 0x036028e0
    mr    r3, r29              ; original
    lis   r11, apTick@ha
    lwz   r12, apMSPass@l(r11)
    addi  r12, r12, 1
    stw   r12, apMSPass@l(r11)
    blr

apMSTraceBail:                   ; 0x02ed1e5c, early exit path
    lwz   r0, 0x24(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apMSBail@l(r11)
    addi  r12, r12, 1
    stw   r12, apMSBail@l(r11)
    blr

; --- blue tip frame probes -----------------------------------------
; Module 0x02fd3c74-0x02fd5340, the one that references
; LayoutMsg/MessageTipsRunTime_00. Each probe replays its original
; instruction -- always the `stw r0, N(r1)` that saves LR, where r11 and r12
; are dead -- sets its bit and increments its counter.

apTipsProbe0:                    ; 0x02fd4848, display of a tip
    stw   r0, 0x2c(r1)          ; original
    lis   r11, apTick@ha
    stw   r30, apTipsShowThis@l(r11)   ; this
    stw   r31, apTipsShowIdx@l(r11)    ; the requested index
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0001
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips0@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips0@l(r11)
    blr

apTipsProbe1:                    ; 0x02fd4a1c, per-frame update
    stw   r0, 0x14(r1)          ; original
    lis   r11, apTick@ha
    stw   r31, apTipsThis@l(r11)       ; a dedicated field: THIS is the `this`
                                       ; replayed, the persistent object's
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0002
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips1@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips1@l(r11)
    blr

apTipsProbe2:                    ; 0x02fd3c74, layout construction
    stw   r0, 0x84(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0004
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips2@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips2@l(r11)
    blr

apTipsProbe3:                    ; 0x02fd4bc0
    stw   r0, 0x14(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0008
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips3@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips3@l(r11)
    blr

apTipsProbe4:                    ; 0x02fd4730
    stw   r0, 0x1c(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0010
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips4@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips4@l(r11)
    blr

apTipsProbe5:                    ; 0x02fd45ac
    stw   r0, 0x2c(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0020
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips5@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips5@l(r11)
    blr

apTipsProbe6:                    ; 0x02fd4b6c, anime 'GuideOn'
    stw   r0, 0x14(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0040
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips6@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips6@l(r11)
    blr

apTipsProbe7:                    ; 0x02fd46ec
    stw   r0, 0x14(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apTipsMask@l(r11)
    ori   r12, r12, 0x0080
    stw   r12, apTipsMask@l(r11)
    lwz   r12, apTips7@l(r11)
    addi  r12, r12, 1
    stw   r12, apTips7@l(r11)
    blr

apTipsSpy:                       ; 0x02fd48c8, right before bl 0x03082d88
    ; At this point r5 points to the text object the game just filled.
    ; It is read rather than deducing what its two words hold: that is
    ; exactly the question the replay must settle.
    stw   r0, 0x8(r1)           ; original
    lis   r11, apTick@ha
    lwz   r12, 0x0(r5)
    stw   r12, apTipsSpyPtr@l(r11)
    lwz   r12, 0x4(r5)
    stw   r12, apTipsSpyLen@l(r11)
    blr

0x02fd4864 = bla apTipsProbe0
0x02fd4a30 = bla apTipsProbe1
0x02fd3c88 = bla apTipsProbe2
0x02fd4bd4 = bla apTipsProbe3
0x02fd4750 = bla apTipsProbe4
0x02fd45d0 = bla apTipsProbe5
0x02fd4b7c = bla apTipsProbe6
0x02fd46f8 = bla apTipsProbe7
0x02fd48c8 = bla apTipsSpy

apMsgSpy:                        ; 0x03a38af0, label resolver
    stw   r0, 0x1c(r1)          ; original -- r0 is still the return address
    lis   r11, apTick@ha
    lwz   r12, apRingLeft@l(r11)
    cmpwi r12, 0
    beq   apMsgSpyEnd
    addi  r12, r12, -1
    stw   r12, apRingLeft@l(r11)
    lwz   r12, apRingPtr@l(r11)
    stw   r0, 0x0(r12)          ; where the request comes from
    stw   r5, 0x4(r12)          ; const char* of the requested label
    addi  r12, r12, 8
    stw   r12, apRingPtr@l(r11)
apMsgSpyEnd:
    blr

0x03a38af0 = bla apMsgSpy
apDlgOpen:                       ; 0x035ff918, in 0x035ff8fc
    ; The arguments are read ONLY on a call with a zero flag.
    ; Replaying a call with flag 1 crashed the game: that branch goes into
    ; 0x035fb1b4, which DEREFERENCES the 4th and 5th arguments -- two heap
    ; pointers, dead from the next call. With flag 0 they are never read
    ; (checked: r26 and r27 only appear again at 0x035ffa1c/0x035ffa20).
    stw   r0, 0x34(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apDlgOpenN@l(r11)
    addi  r12, r12, 1
    stw   r12, apDlgOpenN@l(r11)
    cmpwi r28, 0
    bne   apDlgOpenEnd
    stw   r29, apDlgSeenArc@l(r11)  ; SafeString* archive
    stw   r30, apDlgSeenLbl@l(r11)  ; SafeString* label
    stw   r26, apDlgArg6@l(r11)     ; 4th argument
    stw   r27, apDlgArg7@l(r11)     ; 5e
    stw   r28, apDlgArg8@l(r11)     ; 6th, the flag: zero here by construction
    lwz   r12, apDlgOpen0N@l(r11)
    addi  r12, r12, 1
    stw   r12, apDlgOpen0N@l(r11)
apDlgOpenEnd:
    blr

apDlgSet:                        ; 0x035fb60c, in 0x035fb5f8
    stw   r0, 0x34(r1)          ; original
    lis   r11, apTick@ha
    stw   r27, apDlgThis@l(r11)     ; the window: its +0x1d0 is what gets overwritten
    lwz   r12, apDlgSetN@l(r11)
    addi  r12, r12, 1
    stw   r12, apDlgSetN@l(r11)
    blr

0x035ff918 = bla apDlgOpen
0x035fb60c = bla apDlgSet

apLvlSpy0:                    ; 0x02b77278, in 0x02b77260
    stw   r0, 0x14(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apLvl0N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl0N@l(r11)
    stw   r3, apLvl0R3@l(r11)
    stw   r4, apLvl0R4@l(r11)
    stw   r5, apLvl0R5@l(r11)
    stw   r6, apLvl0R6@l(r11)
    stw   r7, apLvl0R7@l(r11)
    stw   r0, apLvl0Lr@l(r11)
    blr

0x02b77278 = bla apLvlSpy0

apLvlSpy1:                    ; 0x021c0318, in 0x021c0308
    stw   r0, 0x1c(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apLvl1N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl1N@l(r11)
    stw   r3, apLvl1R3@l(r11)
    stw   r4, apLvl1R4@l(r11)
    stw   r5, apLvl1R5@l(r11)
    stw   r6, apLvl1R6@l(r11)
    stw   r7, apLvl1R7@l(r11)
    stw   r0, apLvl1Lr@l(r11)
    blr

0x021c0318 = bla apLvlSpy1

apLvlSpy2:                    ; 0x030eaee8, in 0x030eaedc
    stw   r0, 0x14(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apLvl2N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl2N@l(r11)
    stw   r3, apLvl2R3@l(r11)
    stw   r4, apLvl2R4@l(r11)
    stw   r5, apLvl2R5@l(r11)
    stw   r6, apLvl2R6@l(r11)
    stw   r7, apLvl2R7@l(r11)
    stw   r0, apLvl2Lr@l(r11)
    blr

0x030eaee8 = bla apLvlSpy2

apLvlSpy3:                    ; 0x031570c8, in 0x031570b0
    stw   r0, 0xbc(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apLvl3N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl3N@l(r11)
    stw   r3, apLvl3R3@l(r11)
    stw   r4, apLvl3R4@l(r11)
    stw   r5, apLvl3R5@l(r11)
    stw   r6, apLvl3R6@l(r11)
    stw   r7, apLvl3R7@l(r11)
    stw   r0, apLvl3Lr@l(r11)
    blr

0x031570c8 = bla apLvlSpy3

apLvlSpy4:                    ; 0x03158b6c, in 0x03158b58
    stw   r0, 0x2c(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apLvl4N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl4N@l(r11)
    stw   r3, apLvl4R3@l(r11)
    stw   r4, apLvl4R4@l(r11)
    stw   r5, apLvl4R5@l(r11)
    stw   r6, apLvl4R6@l(r11)
    stw   r7, apLvl4R7@l(r11)
    stw   r0, apLvl4Lr@l(r11)
    blr

0x03158b6c = bla apLvlSpy4

apLvlSpy5:                    ; 0x031577b8, in 0x031577a8
    stw   r0, 0x14(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apLvl5N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl5N@l(r11)
    stw   r3, apLvl5R3@l(r11)
    stw   r4, apLvl5R4@l(r11)
    stw   r5, apLvl5R5@l(r11)
    stw   r6, apLvl5R6@l(r11)
    stw   r7, apLvl5R7@l(r11)
    stw   r0, apLvl5Lr@l(r11)
    blr

0x031577b8 = bla apLvlSpy5

apLvlSpy6:                    ; 0x03157888, in 0x03157874
    stw   r0, 0x1c(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apLvl6N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl6N@l(r11)
    stw   r3, apLvl6R3@l(r11)
    stw   r4, apLvl6R4@l(r11)
    stw   r5, apLvl6R5@l(r11)
    stw   r6, apLvl6R6@l(r11)
    stw   r7, apLvl6R7@l(r11)
    stw   r0, apLvl6Lr@l(r11)
    blr

0x03157888 = bla apLvlSpy6

apLvlSpy7:                    ; 0x037b89d0, in 0x037b89c4
    stw   r0, 0x14(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apLvl7N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl7N@l(r11)
    stw   r3, apLvl7R3@l(r11)
    stw   r4, apLvl7R4@l(r11)
    stw   r5, apLvl7R5@l(r11)
    stw   r6, apLvl7R6@l(r11)
    stw   r7, apLvl7R7@l(r11)
    stw   r0, apLvl7Lr@l(r11)
    blr

0x037b89d0 = bla apLvlSpy7

apLvlSpy8:                    ; 0x037b88e4, in 0x037b88c4
    stw   r0, 0x4(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apLvl8N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl8N@l(r11)
    stw   r3, apLvl8R3@l(r11)
    stw   r4, apLvl8R4@l(r11)
    stw   r5, apLvl8R5@l(r11)
    stw   r6, apLvl8R6@l(r11)
    stw   r7, apLvl8R7@l(r11)
    stw   r0, apLvl8Lr@l(r11)
    blr

0x037b88e4 = bla apLvlSpy8

apLvlSpy10:                    ; 0x0315de68, in 0x0315de5c
    stw   r0, 0x14(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apLvl10N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl10N@l(r11)
    stw   r3, apLvl10R3@l(r11)
    stw   r4, apLvl10R4@l(r11)
    stw   r5, apLvl10R5@l(r11)
    stw   r6, apLvl10R6@l(r11)
    stw   r7, apLvl10R7@l(r11)
    stw   r0, apLvl10Lr@l(r11)
    blr

0x0315de68 = bla apLvlSpy10

apLvlSpy11:                    ; 0x037a5098, in 0x037a5080
    stw   r0, 0x2a4(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apLvl11N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl11N@l(r11)
    stw   r3, apLvl11R3@l(r11)
    stw   r4, apLvl11R4@l(r11)
    stw   r5, apLvl11R5@l(r11)
    stw   r6, apLvl11R6@l(r11)
    stw   r7, apLvl11R7@l(r11)
    stw   r0, apLvl11Lr@l(r11)
    blr

0x037a5098 = bla apLvlSpy11

apLvlSpy13:                    ; 0x0378b628, in 0x0378b60c
    stw   r0, 0x1c(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apLvl13N@l(r11)
    addi  r12, r12, 1
    stw   r12, apLvl13N@l(r11)
    stw   r3, apLvl13R3@l(r11)
    stw   r4, apLvl13R4@l(r11)
    stw   r5, apLvl13R5@l(r11)
    stw   r6, apLvl13R6@l(r11)
    stw   r7, apLvl13R7@l(r11)
    stw   r0, apLvl13Lr@l(r11)
    blr

0x0378b628 = bla apLvlSpy13

apDispSpy:                       ; 0x032bc744, prologue of 0x032bc730
    ; The broadcast, at its source. r3 and r4 are intact: the `mr r24, r3` and
    ; `mr r25, r4` are before the anchor and do not destroy their source.
    stw   r0, 0x34(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apDispN@l(r11)
    addi  r12, r12, 1
    stw   r12, apDispN@l(r11)
    stw   r3, apDispR3@l(r11)
    stw   r4, apDispR4@l(r11)
    stw   r0, apDispLr@l(r11)
    blr

0x032bc744 = bla apDispSpy

apGrantSpy:                      ; 0x02b769d4, in 0x02b769c4
    ; The GRANTED items function: shrine reward, chest content, NPC gift.
    ; A pickup from the ground never goes through it -- it calls itemGet
    ; directly at 0x02b77014.
    stw   r0, 0x24(r1)          ; original
    lis   r11, apTick@ha
    li    r12, 1
    stw   r12, apGrantMark@l(r11)
    stw   r3, apGrantR3@l(r11)      ; to be able to REPLAY it
    stw   r4, apGrantR4@l(r11)
    stw   r0, apGrantLr@l(r11)
    ; unwind the chained frames: the whole call chain
    stw   r1, apStkF@l(r11)         ; the current frame
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL0@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL1@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL2@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL3@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL4@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL5@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL6@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL7@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL8@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL9@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL10@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL11@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL12@l(r11)
    lwz   r12, apStkF@l(r11)
    cmpwi r12, 0
    beq   apStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apStkEnd
    stw   r12, apStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apStkL13@l(r11)
apStkEnd:
    lis   r11, apTick@ha
    ; copy the stack structure while it is ALIVE
    lwz   r12, 0x0(r4)
    stw   r12, apGrantW0@l(r11)
    lwz   r12, 0x4(r4)
    stw   r12, apGrantW1@l(r11)
    lwz   r12, 0x8(r4)
    stw   r12, apGrantW2@l(r11)
    lwz   r12, 0xc(r4)
    stw   r12, apGrantW3@l(r11)
    lwz   r12, 0x10(r4)
    stw   r12, apGrantW4@l(r11)
    lwz   r12, 0x14(r4)
    stw   r12, apGrantW5@l(r11)
    lwz   r12, 0x18(r4)
    stw   r12, apGrantW6@l(r11)
    lwz   r12, 0x1c(r4)
    stw   r12, apGrantW7@l(r11)
    lwz   r12, 0x20(r4)
    stw   r12, apGrantW8@l(r11)
    lwz   r12, 0x24(r4)
    stw   r12, apGrantW9@l(r11)
    lwz   r12, 0x28(r4)
    stw   r12, apGrantW10@l(r11)
    lwz   r12, 0x2c(r4)
    stw   r12, apGrantW11@l(r11)
    lwz   r12, 0x30(r4)
    stw   r12, apGrantW12@l(r11)
    lwz   r12, 0x34(r4)
    stw   r12, apGrantW13@l(r11)
    lwz   r12, 0x38(r4)
    stw   r12, apGrantW14@l(r11)
    lwz   r12, 0x3c(r4)
    stw   r12, apGrantW15@l(r11)
    lwz   r12, 0x40(r4)
    stw   r12, apGrantW16@l(r11)
    lwz   r12, 0x44(r4)
    stw   r12, apGrantW17@l(r11)
    lwz   r12, 0x48(r4)
    stw   r12, apGrantW18@l(r11)
    lwz   r12, 0x4c(r4)
    stw   r12, apGrantW19@l(r11)
    lwz   r12, 0x50(r4)
    stw   r12, apGrantW20@l(r11)
    lwz   r12, 0x54(r4)
    stw   r12, apGrantW21@l(r11)
    lwz   r12, 0x58(r4)
    stw   r12, apGrantW22@l(r11)
    lwz   r12, 0x5c(r4)
    stw   r12, apGrantW23@l(r11)
    lwz   r12, 0x60(r4)
    stw   r12, apGrantW24@l(r11)
    lwz   r12, 0x64(r4)
    stw   r12, apGrantW25@l(r11)
    lwz   r12, 0x68(r4)
    stw   r12, apGrantW26@l(r11)
    lwz   r12, 0x6c(r4)
    stw   r12, apGrantW27@l(r11)
    lwz   r12, 0x70(r4)
    stw   r12, apGrantW28@l(r11)
    lwz   r12, 0x74(r4)
    stw   r12, apGrantW29@l(r11)
    lwz   r12, 0x78(r4)
    stw   r12, apGrantW30@l(r11)
    lwz   r12, 0x7c(r4)
    stw   r12, apGrantW31@l(r11)
    lwz   r12, apGrantN@l(r11)
    addi  r12, r12, 1
    stw   r12, apGrantN@l(r11)

    ; --- automatic arming of the text substitution --------------------
    ; This is the GRANTED items path, before itemGet: the only moment when
    ; it is known that the chest's window is about to be built.
    lwz   r12, apSubAuto@l(r11)
    cmpwi r12, 0
    beq   apGrantEnd
    addi  r12, r12, -1
    stw   r12, apSubAuto@l(r11)
    lwz   r12, apSubAutoN@l(r11)
    stw   r12, apSubReq@l(r11)
    stw   r12, apSubDescReq@l(r11)
apGrantEnd:
    blr

0x02b769d4 = bla apGrantSpy

0x031FA9B4 = bla apProbe
0x02EB5400 = bla apItemGetSpy

; --- PickUpWin probes ------------------------------------------------
; Each probe replays the original instruction, sets its bit in
; apHookMask and increments its counter. The anchor sits AFTER the mflr
; of each function: before it, Cemu's bla would destroy its return address.
; Only r11 and r12 are touched -- volatile, so dead in a prologue.

apProbe0:                      ; function 0x02ffa888
    mr    r26, r3          ; original
    lis   r11, apTick@ha
    stw   r3, apPickUpThis@l(r11)   ; the screen's instance, to call it back
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0001
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook0@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook0@l(r11)
    blr

apProbe1:                      ; function 0x02ffb11c
    mr    r24, r3          ; original
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0002
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook1@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook1@l(r11)
    blr

apProbe2:                      ; function 0x02ffb654
    stfd  f29, 0xa8(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0004
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook2@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook2@l(r11)
    blr

apProbe3:                      ; function 0x02ffc8f8
    stw   r0, 0x44(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0008
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook3@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook3@l(r11)
    blr

apProbe4:                      ; function 0x02ffccf0
    mr    r31, r3          ; original
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0010
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook4@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook4@l(r11)
    blr

apProbe5:                      ; function 0x02ffcdc4
    mr    r31, r3          ; original
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0020
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook5@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook5@l(r11)
    blr

apProbe6:                      ; function 0x02ffceac
    mr    r31, r3          ; original
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0040
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook6@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook6@l(r11)
    blr

apProbe7:                      ; function 0x02ffcf80
    mr    r31, r3          ; original
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0080
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook7@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook7@l(r11)
    blr

apProbe8:                      ; function 0x02ffd06c
    mr    r31, r3          ; original
    lis   r11, apTick@ha
    lwz   r12, apHookMask@l(r11)
    ori   r12, r12, 0x0100
    stw   r12, apHookMask@l(r11)
    lwz   r12, apHook8@l(r11)
    addi  r12, r12, 1
    stw   r12, apHook8@l(r11)
    blr
0x02ffa894 = bla apProbe0
0x02ffb128 = bla apProbe1
0x02ffb660 = bla apProbe2
0x02ffc90c = bla apProbe3
0x02ffccfc = bla apProbe4
0x02ffcdd0 = bla apProbe5
0x02ffceb8 = bla apProbe6
0x02ffcf8c = bla apProbe7
0x02ffd078 = bla apProbe8
0x02FFAB18 = bla apProbeScreen
0x02ecbcbc = bla apMSProbe0
0x02ed1a7c = bla apMSProbe1
0x02f21990 = bla apMSProbe2
0x02f8b2d4 = bla apMSProbe3
0x02fc0f80 = bla apMSProbe4
0x02fc2e00 = bla apMSProbe5
0x02ed1e98 = bla apMSTracePass
0x02ed1e5c = bla apMSTraceBail
0x02ed1e70 = bla apMSTraceMid
0x02ed1f98 = bla apPushSpy

; --- item get window probes ------------------------------------------
; Each probe replays the `stw r0, N(r1)` that just saved LR: at this point
; r0 is dead (its value is already on the stack) and r11/r12 are volatile,
; so dead in a prologue. Checked on the 40 hooks.

apGetProbe0:                    ; 0x02fcf2a4, function 0x02fcf29c
    stw   r0, 0x94(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet0@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet0@l(r11)
    stw   r0, apGetFrom0@l(r11)
    stw   r3, apGetThis0@l(r11)
    stw   r4, apGetR4_0@l(r11)
    stw   r5, apGetR5_0@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd0@l(r11)
    blr

apGetProbe1:                    ; 0x02fcf64c, function 0x02fcf63c
    stw   r0, 0x64(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet1@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet1@l(r11)
    stw   r0, apGetFrom1@l(r11)
    stw   r3, apGetThis1@l(r11)
    stw   r4, apGetR4_1@l(r11)
    stw   r5, apGetR5_1@l(r11)
    ; This probe is only passed when MessageGet_00 opens: the driver's pending
    ; capture is therefore THIS screen's. It is frozen.
    lwz   r12, apGetDrvThis@l(r11)
    stw   r12, apGetWinCThis@l(r11)
    lwz   r12, apGetDrvA4@l(r11)
    stw   r12, apGetWinCA4@l(r11)
    lwz   r12, apGetDrvA5@l(r11)
    stw   r12, apGetWinCA5@l(r11)
    lwz   r12, apGetDrvA6@l(r11)
    stw   r12, apGetWinCA6@l(r11)
    lwz   r12, apGetDrvA7@l(r11)
    stw   r12, apGetWinCA7@l(r11)
    lwz   r12, apGetDrvA8@l(r11)
    stw   r12, apGetWinCA8@l(r11)
    lwz   r12, apGetDrvA9@l(r11)
    stw   r12, apGetWinCA9@l(r11)
    lwz   r12, apGetWinOk@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWinOk@l(r11)
    ; and the six registers of the opening site, for the same reason
    lwz   r12, apOpn24@l(r11)
    stw   r12, apOpnC24@l(r11)
    lwz   r12, apOpn25@l(r11)
    stw   r12, apOpnC25@l(r11)
    lwz   r12, apOpn26@l(r11)
    stw   r12, apOpnC26@l(r11)
    lwz   r12, apOpn27@l(r11)
    stw   r12, apOpnC27@l(r11)
    lwz   r12, apOpn28@l(r11)
    stw   r12, apOpnC28@l(r11)
    lwz   r12, apOpn31@l(r11)
    stw   r12, apOpnC31@l(r11)
    lwz   r12, apOpnOk@l(r11)
    addi  r12, r12, 1
    stw   r12, apOpnOk@l(r11)

    ; and the six ARGUMENTS of the prologue, for the same reason: the prologue
    ; runs at every screen opening, only this probe knows it is ours
    lwz   r12, apOpnProLr@l(r11)
    stw   r12, apOpnPrcLr@l(r11)
    lwz   r12, apOpnProR1@l(r11)
    stw   r12, apOpnPrcR1@l(r11)
    lwz   r12, apOpnProA1@l(r11)
    stw   r12, apOpnPrcA1@l(r11)
    lwz   r12, apOpnProA2@l(r11)
    stw   r12, apOpnPrcA2@l(r11)
    lwz   r12, apOpnProA3@l(r11)
    stw   r12, apOpnPrcA3@l(r11)
    lwz   r12, apOpnProA4@l(r11)
    stw   r12, apOpnPrcA4@l(r11)
    lwz   r12, apOpnProA5@l(r11)
    stw   r12, apOpnPrcA5@l(r11)
    lwz   r12, apOpnProA6@l(r11)
    stw   r12, apOpnPrcA6@l(r11)
    lwz   r12, apOpnPrcOk@l(r11)
    addi  r12, r12, 1
    stw   r12, apOpnPrcOk@l(r11)

    ; and the five arguments of the level above, for the same reason
    lwz   r12, apUpA1@l(r11)
    stw   r12, apUpcA1@l(r11)
    lwz   r12, apUpA2@l(r11)
    stw   r12, apUpcA2@l(r11)
    lwz   r12, apUpA3@l(r11)
    stw   r12, apUpcA3@l(r11)
    lwz   r12, apUpA4@l(r11)
    stw   r12, apUpcA4@l(r11)
    lwz   r12, apUpA5@l(r11)
    stw   r12, apUpcA5@l(r11)
    lwz   r12, apUpcOk@l(r11)
    addi  r12, r12, 1
    stw   r12, apUpcOk@l(r11)

    ; copy the context object while it is ALIVE
    stw   r3, apOpnCtxR3@l(r11)
    lwz   r3, apOpn31@l(r11)
    lwz   r12, 0x0(r3)
    stw   r12, apOpnCtx0@l(r11)
    lwz   r12, 0x4(r3)
    stw   r12, apOpnCtx1@l(r11)
    lwz   r12, 0x8(r3)
    stw   r12, apOpnCtx2@l(r11)
    lwz   r12, 0xc(r3)
    stw   r12, apOpnCtx3@l(r11)
    lwz   r12, 0x10(r3)
    stw   r12, apOpnCtx4@l(r11)
    lwz   r12, 0x14(r3)
    stw   r12, apOpnCtx5@l(r11)
    lwz   r12, 0x18(r3)
    stw   r12, apOpnCtx6@l(r11)
    lwz   r12, 0x1c(r3)
    stw   r12, apOpnCtx7@l(r11)
    lwz   r12, 0x20(r3)
    stw   r12, apOpnCtx8@l(r11)
    lwz   r12, 0x24(r3)
    stw   r12, apOpnCtx9@l(r11)
    lwz   r12, 0x28(r3)
    stw   r12, apOpnCtx10@l(r11)
    lwz   r12, 0x2c(r3)
    stw   r12, apOpnCtx11@l(r11)
    lwz   r12, 0x30(r3)
    stw   r12, apOpnCtx12@l(r11)
    lwz   r12, 0x34(r3)
    stw   r12, apOpnCtx13@l(r11)
    lwz   r12, 0x38(r3)
    stw   r12, apOpnCtx14@l(r11)
    lwz   r12, 0x3c(r3)
    stw   r12, apOpnCtx15@l(r11)
    lwz   r12, 0x40(r3)
    stw   r12, apOpnCtx16@l(r11)
    lwz   r12, 0x44(r3)
    stw   r12, apOpnCtx17@l(r11)
    lwz   r12, 0x48(r3)
    stw   r12, apOpnCtx18@l(r11)
    lwz   r12, 0x4c(r3)
    stw   r12, apOpnCtx19@l(r11)
    lwz   r12, 0x50(r3)
    stw   r12, apOpnCtx20@l(r11)
    lwz   r12, 0x54(r3)
    stw   r12, apOpnCtx21@l(r11)
    lwz   r12, 0x58(r3)
    stw   r12, apOpnCtx22@l(r11)
    lwz   r12, 0x5c(r3)
    stw   r12, apOpnCtx23@l(r11)
    lwz   r12, 0x60(r3)
    stw   r12, apOpnCtx24@l(r11)
    lwz   r12, 0x64(r3)
    stw   r12, apOpnCtx25@l(r11)
    lwz   r12, 0x68(r3)
    stw   r12, apOpnCtx26@l(r11)
    lwz   r12, 0x6c(r3)
    stw   r12, apOpnCtx27@l(r11)
    lwz   r12, 0x70(r3)
    stw   r12, apOpnCtx28@l(r11)
    lwz   r12, 0x74(r3)
    stw   r12, apOpnCtx29@l(r11)
    lwz   r12, 0x78(r3)
    stw   r12, apOpnCtx30@l(r11)
    lwz   r12, 0x7c(r3)
    stw   r12, apOpnCtx31@l(r11)
    lwz   r3, apOpnCtxR3@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd1@l(r11)
    blr

apGetProbe2:                    ; 0x02fd0330, function 0x02fd0314
    stw   r0, 0x44(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet2@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet2@l(r11)
    stw   r0, apGetFrom2@l(r11)
    stw   r3, apGetThis2@l(r11)
    stw   r4, apGetR4_2@l(r11)
    stw   r5, apGetR5_2@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd2@l(r11)
    blr

apGetProbe3:                    ; 0x02fd0cfc, function 0x02fd0ce4
    stw   r0, 0x19c(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet3@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet3@l(r11)
    stw   r0, apGetFrom3@l(r11)
    stw   r3, apGetThis3@l(r11)
    stw   r4, apGetR4_3@l(r11)
    stw   r5, apGetR5_3@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd3@l(r11)
    blr

apGetProbe4:                    ; 0x02fd14f8, function 0x02fd14e8
    stw   r0, 0x14(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet4@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet4@l(r11)
    stw   r0, apGetFrom4@l(r11)
    stw   r3, apGetThis4@l(r11)
    stw   r4, apGetR4_4@l(r11)
    stw   r5, apGetR5_4@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd4@l(r11)
    blr

apGetProbe5:                    ; 0x02fd1544, function 0x02fd1534
    stw   r0, 0x14(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet5@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet5@l(r11)
    stw   r0, apGetFrom5@l(r11)
    stw   r3, apGetThis5@l(r11)
    stw   r4, apGetR4_5@l(r11)
    stw   r5, apGetR5_5@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd5@l(r11)
    blr

apGetProbe6:                    ; 0x02fd166c, function 0x02fd165c
    stw   r0, 0x24(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet6@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet6@l(r11)
    stw   r0, apGetFrom6@l(r11)
    stw   r3, apGetThis6@l(r11)
    stw   r4, apGetR4_6@l(r11)
    stw   r5, apGetR5_6@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd6@l(r11)
    blr

apGetProbe7:                    ; 0x02fd1ee4, function 0x02fd1ed8
    stw   r0, 0x14(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet7@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet7@l(r11)
    stw   r0, apGetFrom7@l(r11)
    stw   r3, apGetThis7@l(r11)
    stw   r4, apGetR4_7@l(r11)
    stw   r5, apGetR5_7@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd7@l(r11)
    blr

apGetProbe8:                    ; 0x02fd20e0, function 0x02fd20cc
    stw   r0, 0x24(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet8@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet8@l(r11)
    stw   r0, apGetFrom8@l(r11)
    stw   r3, apGetThis8@l(r11)
    stw   r4, apGetR4_8@l(r11)
    stw   r5, apGetR5_8@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd8@l(r11)
    blr

apGetProbe9:                    ; 0x02fd21e0, function 0x02fd21cc
    stw   r0, 0x24(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet9@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet9@l(r11)
    stw   r0, apGetFrom9@l(r11)
    stw   r3, apGetThis9@l(r11)
    stw   r4, apGetR4_9@l(r11)
    stw   r5, apGetR5_9@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd9@l(r11)
    blr

apGetProbe10:                    ; 0x02fd22b4, function 0x02fd22a0
    stw   r0, 0x24(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet10@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet10@l(r11)
    stw   r0, apGetFrom10@l(r11)
    stw   r3, apGetThis10@l(r11)
    stw   r4, apGetR4_10@l(r11)
    stw   r5, apGetR5_10@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd10@l(r11)
    blr

apGetProbe11:                    ; 0x02fd2408, function 0x02fd23f4
    stw   r0, 0x1c(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet11@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet11@l(r11)
    stw   r0, apGetFrom11@l(r11)
    stw   r3, apGetThis11@l(r11)
    stw   r4, apGetR4_11@l(r11)
    stw   r5, apGetR5_11@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd11@l(r11)
    blr

apGetProbe12:                    ; 0x02fd2524, function 0x02fd2510
    stw   r0, 0x14(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet12@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet12@l(r11)
    stw   r0, apGetFrom12@l(r11)
    stw   r3, apGetThis12@l(r11)
    stw   r4, apGetR4_12@l(r11)
    stw   r5, apGetR5_12@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd12@l(r11)
    blr

apGetProbe13:                    ; 0x02fd2570, function 0x02fd255c
    stw   r0, 0x84(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet13@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet13@l(r11)
    stw   r0, apGetFrom13@l(r11)
    stw   r3, apGetThis13@l(r11)
    stw   r4, apGetR4_13@l(r11)
    stw   r5, apGetR5_13@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd13@l(r11)
    blr

apGetProbe14:                    ; 0x02fd2b34, function 0x02fd2b18
    stw   r0, 0x124(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet14@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet14@l(r11)
    stw   r0, apGetFrom14@l(r11)
    stw   r3, apGetThis14@l(r11)
    stw   r4, apGetR4_14@l(r11)
    stw   r5, apGetR5_14@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd14@l(r11)
    blr

apGetProbe15:                    ; 0x02fd2d74, function 0x02fd2d64
    stw   r0, 0x14(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet15@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet15@l(r11)
    stw   r0, apGetFrom15@l(r11)
    stw   r3, apGetThis15@l(r11)
    stw   r4, apGetR4_15@l(r11)
    stw   r5, apGetR5_15@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd15@l(r11)
    blr

apGetProbe16:                    ; 0x02fd2ffc, function 0x02fd2ff0
    stw   r0, 0x14(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet16@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet16@l(r11)
    stw   r0, apGetFrom16@l(r11)
    stw   r3, apGetThis16@l(r11)
    stw   r4, apGetR4_16@l(r11)
    stw   r5, apGetR5_16@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd16@l(r11)
    blr

apGetProbe17:                    ; 0x02fd3048, function 0x02fd3034
    stw   r0, 0x13c(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet17@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet17@l(r11)
    stw   r0, apGetFrom17@l(r11)
    stw   r3, apGetThis17@l(r11)
    stw   r4, apGetR4_17@l(r11)
    stw   r5, apGetR5_17@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd17@l(r11)
    blr

apGetProbe18:                    ; 0x02fd33f0, function 0x02fd33e0
    stw   r0, 0x14(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGet18@l(r11)
    addi  r12, r12, 1
    stw   r12, apGet18@l(r11)
    stw   r0, apGetFrom18@l(r11)
    stw   r3, apGetThis18@l(r11)
    stw   r4, apGetR4_18@l(r11)
    stw   r5, apGetR5_18@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetOrd18@l(r11)
    blr

0x02fcf2a4 = bla apGetProbe0
0x02fcf64c = bla apGetProbe1
0x02fd0330 = bla apGetProbe2
0x02fd0cfc = bla apGetProbe3
0x02fd14f8 = bla apGetProbe4
0x02fd1544 = bla apGetProbe5
0x02fd166c = bla apGetProbe6
0x02fd1ee4 = bla apGetProbe7
0x02fd20e0 = bla apGetProbe8
0x02fd21e0 = bla apGetProbe9
0x02fd22b4 = bla apGetProbe10
0x02fd2408 = bla apGetProbe11
0x02fd2524 = bla apGetProbe12
0x02fd2570 = bla apGetProbe13
0x02fd2b34 = bla apGetProbe14
0x02fd2d74 = bla apGetProbe15
0x02fd2ffc = bla apGetProbe16
0x02fd3048 = bla apGetProbe17
0x02fd33f0 = bla apGetProbe18

; --- probes of the get window's manager class ------------------------

apGetWinProbe0:                 ; 0x03606ae8, function 0x03606ad0
    stw   r0, 0x3c(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGetWin0@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin0@l(r11)
    stw   r0, apGetWinFrom0@l(r11)
    stw   r3, apGetWinThis0@l(r11)
    stw   r4, apGetWinR4_0@l(r11)
    stw   r5, apGetWinR5_0@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd0@l(r11)
    blr

apGetWinProbe1:                 ; 0x03606c74, function 0x03606c5c
    stw   r0, 0x3c(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGetWin1@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin1@l(r11)
    stw   r0, apGetWinFrom1@l(r11)
    stw   r3, apGetWinThis1@l(r11)
    stw   r4, apGetWinR4_1@l(r11)
    stw   r5, apGetWinR5_1@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd1@l(r11)
    blr

apGetWinProbe2:                 ; 0x03606e2c, function 0x03606e18
    stw   r0, 0x34(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGetWin2@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin2@l(r11)
    stw   r0, apGetWinFrom2@l(r11)
    stw   r3, apGetWinThis2@l(r11)
    stw   r4, apGetWinR4_2@l(r11)
    stw   r5, apGetWinR5_2@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd2@l(r11)
    blr

apGetWinProbe3:                 ; 0x03606ee8, function 0x03606ed4
    stw   r0, 0x1c(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGetWin3@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin3@l(r11)
    stw   r0, apGetWinFrom3@l(r11)
    stw   r3, apGetWinThis3@l(r11)
    stw   r4, apGetWinR4_3@l(r11)
    stw   r5, apGetWinR5_3@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd3@l(r11)
    blr

apGetWinProbe4:                 ; 0x03606f58, function 0x03606f48
    stw   r0, 0x14(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGetWin4@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin4@l(r11)
    stw   r0, apGetWinFrom4@l(r11)
    stw   r3, apGetWinThis4@l(r11)
    stw   r4, apGetWinR4_4@l(r11)
    stw   r5, apGetWinR5_4@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd4@l(r11)
    blr

apGetWinProbe5:                 ; 0x036070a8, function 0x03607080
    stw   r0, 0x54(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGetWin5@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin5@l(r11)
    stw   r0, apGetWinFrom5@l(r11)
    stw   r3, apGetWinThis5@l(r11)
    stw   r4, apGetWinR4_5@l(r11)
    stw   r5, apGetWinR5_5@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd5@l(r11)
    blr

apGetWinProbe6:                 ; 0x03607220, function 0x03607210
    stw   r0, 0x14(r1)         ; original
    lis   r11, apTick@ha
    stw   r1, apR1Ui@l(r11)         ; stack of the UI manager
    lwz   r12, apGetWin6@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin6@l(r11)
    stw   r0, apGetWinFrom6@l(r11)
    stw   r3, apGetWinThis6@l(r11)
    stw   r4, apGetWinR4_6@l(r11)
    stw   r5, apGetWinR5_6@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd6@l(r11)

    ; --- keep the get window open ---------------------------------------
    ; Each link is checked before being followed. When the slot is empty,
    ; NOTHING is touched -- least of all the activity byte: setting it on an
    ; index with no screen would make the driver follow a dead pointer at the
    ; next frame. A Python version of this hold did exactly that.
    lwz   r12, apHoldN@l(r11)
    cmpwi r12, 0
    beq   apHoldEnd
    addi  r12, r12, -1
    stw   r12, apHoldN@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    lis   r12, 0x1047
    ori   r12, r12, 0xe650
    lwz   r3, 0x0(r12)
    cmpwi r3, 0
    beq   apHoldPop
    lwz   r4, 0x18(r3)
    cmpwi r4, 0
    beq   apHoldPop
    lwz   r4, 0x2c(r4)              ; slot 0x0b
    cmpwi r4, 0
    beq   apHoldPop
    ; MEASURED: the first version wrote 0x200 into +0x94 AND 0 into the
    ; activity byte EVERY FRAME, unconditionally. The screen held -- but the
    ; game froze then crashed: the other bits the state machine sets during
    ; the animation were overwritten sixty times a second. Only the exact
    ; value read as a close request is corrected now, and nothing else.
    ;
    lwz   r12, 0x94(r4)
    cmpwi r12, 0x300
    bne   apHoldPop
    li    r12, 0x200
    stw   r12, 0x94(r4)
apHoldPop:
    lis   r11, apTick@ha
    lwz   r3, apS3@l(r11)
    lwz   r4, apS4@l(r11)
apHoldEnd:

    ; --- where does a LIVE HEAP come from? probe of the current heap getter
    ; The heap creator AND the allocator both run into 0x030aa1ac. It is
    ; therefore queried directly, from THIS thread -- the UI's, the only one
    ; of the right stack family. Every dereference is guarded: the getter
    ; follows *(0x1046C920) then +0x60 without testing, and returns *(arg + 0x4)
    ; as a fallback, so it refuses when either one is null.
    lwz   r12, apHeapReq@l(r11)
    cmpwi r12, 0
    beq   apHeapEnd

    li    r12, 0
    stw   r12, apHeapReq@l(r11)
    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    lwz   r12, apHeapN@l(r11)
    addi  r12, r12, 1
    stw   r12, apHeapN@l(r11)

    ; the two statics the getter uses
    lis   r12, 0x1046
    ori   r12, r12, 0xc8b0
    lwz   r3, 0x0(r12)              ; *(0x1046C8B0): the creator's argument
    stw   r3, apHeapRoot@l(r11)
    lis   r12, 0x1046
    ori   r12, r12, 0xc920
    lwz   r12, 0x0(r12)             ; *(0x1046C920): where the thread comes from
    stw   r12, apHeapMgr@l(r11)

    ; the getter's static fallback, *(root + 0x4)
    cmpwi r3, 0
    beq   apHeapDone
    lwz   r12, 0x4(r3)
    stw   r12, apHeapFb@l(r11)

    ; the call itself, only when both of the getter's dereferences are safe
    lis   r12, 0x1046
    ori   r12, r12, 0xc920
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apHeapDone
    lis   r12, 0x030a
    ori   r12, r12, 0xa1ac
    mtctr r12
    bctrl
    lis   r11, apTick@ha
    stw   r3, apHeapCur@l(r11)

apHeapDone:
    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)
apHeapEnd:

    ; --- replay the window's opening, HERE and nowhere else ------------
    ; MEASURED: the real opening site runs on stack 0x12b3c510, while the
    ; per-frame hook runs on 0x0e201270 -- two threads. Four crashes
    ; followed a replay from the wrong one. This function runs every frame
    ; on stack 0x12afc088, the same family as the real site. That is where
    ; the call must come from.
    lwz   r12, apOpnReq@l(r11)
    cmpwi r12, 0
    beq   apGetWinProbe6End

    lwz   r12, apOpnOk@l(r11)
    cmpwi r12, 0
    beq   apGetWinProbe6End         ; MessageGet_00 never seen: try nothing

    li    r12, 0
    stw   r12, apOpnReq@l(r11)

    stw   r0, apS0@l(r11)
    stw   r3, apS3@l(r11)
    stw   r4, apS4@l(r11)
    stw   r5, apS5@l(r11)
    stw   r6, apS6@l(r11)
    stw   r7, apS7@l(r11)
    stw   r8, apS8@l(r11)
    stw   r9, apS9@l(r11)
    stw   r10, apS10@l(r11)
    mflr  r12
    stw   r12, apSLR@l(r11)
    mfctr r12
    stw   r12, apSCTR@l(r11)

    ; 0) restore the context object -- OFF BY DEFAULT.
    ; apOpnC31 is an already freed heap. Copying 32 words into it never
    ; unlocked anything, and writing into the header of a dead heap may
    ; damage the allocator. Python turns it on with --ctx to redo the
    ; earlier measurements.
    lwz   r12, apOpnCtxOn@l(r11)
    cmpwi r12, 0
    beq   apOpnNoCtx
    lwz   r3, apOpnC31@l(r11)
    lwz   r12, apOpnCtx0@l(r11)
    stw   r12, 0x0(r3)
    lwz   r12, apOpnCtx1@l(r11)
    stw   r12, 0x4(r3)
    lwz   r12, apOpnCtx2@l(r11)
    stw   r12, 0x8(r3)
    lwz   r12, apOpnCtx3@l(r11)
    stw   r12, 0xc(r3)
    lwz   r12, apOpnCtx4@l(r11)
    stw   r12, 0x10(r3)
    lwz   r12, apOpnCtx5@l(r11)
    stw   r12, 0x14(r3)
    lwz   r12, apOpnCtx6@l(r11)
    stw   r12, 0x18(r3)
    lwz   r12, apOpnCtx7@l(r11)
    stw   r12, 0x1c(r3)
    lwz   r12, apOpnCtx8@l(r11)
    stw   r12, 0x20(r3)
    lwz   r12, apOpnCtx9@l(r11)
    stw   r12, 0x24(r3)
    lwz   r12, apOpnCtx10@l(r11)
    stw   r12, 0x28(r3)
    lwz   r12, apOpnCtx11@l(r11)
    stw   r12, 0x2c(r3)
    lwz   r12, apOpnCtx12@l(r11)
    stw   r12, 0x30(r3)
    lwz   r12, apOpnCtx13@l(r11)
    stw   r12, 0x34(r3)
    lwz   r12, apOpnCtx14@l(r11)
    stw   r12, 0x38(r3)
    lwz   r12, apOpnCtx15@l(r11)
    stw   r12, 0x3c(r3)
    lwz   r12, apOpnCtx16@l(r11)
    stw   r12, 0x40(r3)
    lwz   r12, apOpnCtx17@l(r11)
    stw   r12, 0x44(r3)
    lwz   r12, apOpnCtx18@l(r11)
    stw   r12, 0x48(r3)
    lwz   r12, apOpnCtx19@l(r11)
    stw   r12, 0x4c(r3)
    lwz   r12, apOpnCtx20@l(r11)
    stw   r12, 0x50(r3)
    lwz   r12, apOpnCtx21@l(r11)
    stw   r12, 0x54(r3)
    lwz   r12, apOpnCtx22@l(r11)
    stw   r12, 0x58(r3)
    lwz   r12, apOpnCtx23@l(r11)
    stw   r12, 0x5c(r3)
    lwz   r12, apOpnCtx24@l(r11)
    stw   r12, 0x60(r3)
    lwz   r12, apOpnCtx25@l(r11)
    stw   r12, 0x64(r3)
    lwz   r12, apOpnCtx26@l(r11)
    stw   r12, 0x68(r3)
    lwz   r12, apOpnCtx27@l(r11)
    stw   r12, 0x6c(r3)
    lwz   r12, apOpnCtx28@l(r11)
    stw   r12, 0x70(r3)
    lwz   r12, apOpnCtx29@l(r11)
    stw   r12, 0x74(r3)
    lwz   r12, apOpnCtx30@l(r11)
    stw   r12, 0x78(r3)
    lwz   r12, apOpnCtx31@l(r11)
    stw   r12, 0x7c(r3)
apOpnNoCtx:

    ; 1) get the screen
    li    r12, 1
    stw   r12, apOpnPhase@l(r11)

    lwz   r12, apOpnMode@l(r11)
    cmpwi r12, 8
    beq   apOpnCall
    cmpwi r12, 7
    beq   apOpnDisp
    cmpwi r12, 6
    beq   apOpnGrant
    cmpwi r12, 5
    beq   apOpnVCall
    cmpwi r12, 4
    beq   apOpnShow
    cmpwi r12, 3
    beq   apOpnUp
    cmpwi r12, 2
    beq   apOpnWhole
    cmpwi r12, 1
    bne   apOpnFabrique

    ; --- the trampoline, as the dialog box does -------------------------
    lwz   r3, apOpnC28@l(r11)   ; the index, 0x0b
    li    r4, 0
    lis   r12, 0x0339
    ori   r12, r12, 0x24c4
    mtctr r12
    bctrl
    b     apOpnGot

apOpnCall:
    ; --- THE GENERIC INVOKER --------------------------------------------
    ; Eight arguments, an address, no assumption. Python checks what it
    ; passes; only the jump itself is guarded here.
    lwz   r12, apCallAddr@l(r11)
    cmpwi r12, 0
    beq   apOpnShowNo
    mtctr r12
    lwz   r3, apCallA1@l(r11)
    lwz   r4, apCallA2@l(r11)
    lwz   r5, apCallA3@l(r11)
    lwz   r6, apCallA4@l(r11)
    lwz   r7, apCallA5@l(r11)
    lwz   r8, apCallA6@l(r11)
    lwz   r9, apCallA7@l(r11)
    lwz   r10, apCallA8@l(r11)
    bctrl
    lis   r11, apTick@ha
    stw   r3, apCallRet@l(r11)
    lwz   r12, apCallN@l(r11)
    addi  r12, r12, 1
    stw   r12, apCallN@l(r11)
    li    r12, 14
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnDisp:
    ; --- THE BROADCAST: 0x032bc730(*(0x1047D6C0), name) ------------------
    ; The static is read again here and checked; the name comes from
    ; apGrantName, which Python sets (the capture by default, or our own string).
    lwz   r4, apGrantName@l(r11)
    cmpwi r4, 0
    beq   apOpnShowNo
    lwz   r3, apDispArg@l(r11)      ; MEASURED, not computed
    cmpwi r3, 0
    beq   apOpnShowNo
    lis   r12, 0x032b
    ori   r12, r12, 0xc730
    mtctr r12
    bctrl
    lis   r11, apTick@ha
    stw   r3, apOpnR3@l(r11)
    li    r12, 13
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnGrant:
    ; --- THE TOP: 0x02b769c4(r3, r4), the granted item -----------------
    ; No dereference here: both captured arguments are passed again, the
    ; function does the rest. It is refused only when the capture is empty.
    lwz   r3, apGrantR3@l(r11)
    cmpwi r3, 0
    beq   apOpnShowNo
    ; our copy, not the dead stack pointer
    lwz   r4, apGrantBufPtr@l(r11)
    cmpwi r4, 0
    beq   apOpnShowNo
    lis   r12, 0x02b7
    ori   r12, r12, 0x69c4
    mtctr r12
    bctrl
    lis   r11, apTick@ha
    stw   r3, apOpnR3@l(r11)
    li    r12, 12
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnVCall:
    ; --- THE ENCLOSING FUNCTION of the staging --------------------------
    ; screen->vtable[0x1a4](screen, mode) = 0x03a40d20. The move that
    ; unlocked things twice: calling the enclosing function rather than
    ; reproducing its inside. Each link checked; phase 11 when it came back.
    lwz   r9, apOpnVArg@l(r11)
    lis   r12, 0x1047
    ori   r12, r12, 0xe650
    lwz   r8, 0x0(r12)
    cmpwi r8, 0
    beq   apOpnShowNo
    lwz   r8, 0x18(r8)
    cmpwi r8, 0
    beq   apOpnShowNo
    lwz   r8, 0x2c(r8)              ; slot 0x0b
    cmpwi r8, 0
    beq   apOpnShowNo
    lwz   r12, 0xc(r8)
    cmpwi r12, 0
    beq   apOpnShowNo
    lwz   r0, 0x1a4(r12)
    cmpwi r0, 0
    beq   apOpnShowNo
    mtctr r0
    mr    r3, r8
    mr    r4, r9
    bctrl
    lis   r11, apTick@ha
    li    r12, 11
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnShow:
    ; --- SHOW a screen already built ------------------------------------
    ; Replays the four gestures of 0x03a40ebc on the screen stored in slot 0x0b.
    ; Each link is checked before being followed: the manager, the table, the
    ; slot, the vtable, then each of the two slots. A null link leaves
    ; apOpnPhase at 10 instead of closing Cemu.
    lwz   r9, apOpnAnim@l(r11)      ; keep the flag before losing r11
    lis   r12, 0x1047
    ori   r12, r12, 0xe650
    lwz   r8, 0x0(r12)              ; the manager
    cmpwi r8, 0
    beq   apOpnShowNo
    lwz   r8, 0x18(r8)              ; its screen table
    cmpwi r8, 0
    beq   apOpnShowNo
    lwz   r8, 0x2c(r8)              ; slot 0x0b -- 0x0b * 4
    cmpwi r8, 0
    beq   apOpnShowNo
    lwz   r12, 0xc(r8)              ; the screen's vtable
    cmpwi r12, 0
    beq   apOpnShowNo

    ; 1) the animation: vtable[0x214](screen, "open")
    cmpwi r9, 0
    beq   apOpnShowNoAnim
    lwz   r0, 0x214(r12)
    cmpwi r0, 0
    beq   apOpnShowNoAnim
    mtctr r0
    mr    r3, r8
    lis   r4, 0x1035
    ori   r4, r4, 0xdb30            ; the string "open"
    bctrl
apOpnShowNoAnim:

    ; 2) the three bytes
    li    r10, 0
    stb   r10, 0x9e(r8)
    stb   r10, 0x97(r8)
    li    r10, 1
    stb   r10, 0x96(r8)

    ; 3) the entry: vtable[0x114](screen) = 0x036072e0
    lwz   r12, 0xc(r8)
    cmpwi r12, 0
    beq   apOpnShowNo
    lwz   r0, 0x114(r12)
    cmpwi r0, 0
    beq   apOpnShowNo
    mtctr r0
    mr    r3, r8
    bctrl

    lis   r11, apTick@ha
    li    r12, 9
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnShowNo:
    lis   r11, apTick@ha
    li    r12, 10
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnUp:
    ; --- THE LEVEL ABOVE, 0x030806f0(a1..a5) ---------------------------
    ; It calls 0x03a42b94 itself, then runs the staging our replay skipped.
    ; The five arguments come from the capture frozen on MessageGet_00.
    ; No dereference here.
    lwz   r3, apUpcA1@l(r11)
    lwz   r4, apUpcA2@l(r11)
    lwz   r5, apUpcA3@l(r11)
    lwz   r6, apUpcA4@l(r11)
    lwz   r7, apUpcA5@l(r11)
    lis   r12, 0x0308
    ori   r12, r12, 0x06f0
    mtctr r12
    bctrl
    lis   r11, apTick@ha
    stw   r3, apOpnR3@l(r11)
    li    r12, 8
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnWhole:
    ; --- the ENCLOSING FUNCTION, the one that can create a heap ---------
    ; 0x03a42b94(r3..r8). r31 is argument 6 there and r30 argument 2; when
    ; both are null it branches to 0x03a42c90 and creates its heap. Replaying
    ; from 0x03a42ccc jumped precisely over that creation.
    ; No dereference here: the function does everything, its return is left alone.
    lwz   r3, apOpnC27@l(r11)
    lwz   r4, apOpnArg4@l(r11)
    lwz   r5, apOpnC28@l(r11)
    lwz   r6, apOpnC25@l(r11)
    lwz   r7, apOpnC26@l(r11)
    lwz   r8, apOpnHeap@l(r11)
    lis   r12, 0x03a4
    ori   r12, r12, 0x2b94
    mtctr r12
    bctrl
    lis   r11, apTick@ha
    stw   r3, apOpnR3@l(r11)
    li    r12, 7
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnFabrique:
    ; --- the raw factory, (*(*(r27+0x24)))[0x14](that same object, r31, r28)
    lwz   r3, apOpnC27@l(r11)
    lwz   r3, 0x24(r3)
    lwz   r10, 0x0(r3)
    lwz   r0, 0x14(r10)
    mtctr r0
    ; apOpnHeap is now a RAW ADDRESS, not a flag: 0 = null heap (the
    ; allocator will look for the current one), otherwise the heap to try --
    ; the captured one, the static root, the thread's. Python sets the
    ; value, so several are tried without restarting Cemu.
    lwz   r4, apOpnHeap@l(r11)
    lwz   r5, apOpnC28@l(r11)
    bctrl

apOpnGot:
    lis   r11, apTick@ha
    li    r12, 2
    stw   r12, apOpnPhase@l(r11)
    stw   r3, apOpnR3@l(r11)        ; what the factory returned

    ; DO NOT DEREFERENCE WITHOUT CHECKING. If the factory refuses -- a screen
    ; already open, an incomplete context -- it returns 0, and `lwz r12, 0xc(r3)`
    ; right after dereferences zero. The same fault as the first version of
    ; apSubSpy, which crashed when a save loaded. Here it stops cleanly:
    ; apOpnPhase stays at 2, apOpnR3 is 0, and the diagnosis says so
    ; instead of killing the game.
    cmpwi r3, 0
    beq   apOpnAfter

    ; stop there when only the factory is bisected
    lwz   r12, apOpnStep@l(r11)
    cmpwi r12, 1
    beq   apOpnAfter

    ; 2) the opening: (*(r3+0xc))[0x4c](r3, r27, r31, r24, r28, r25, r26)
    ; Cemu CLOSES when the game crashes: nothing can be read afterwards.
    ; Each link is therefore checked before being followed, and a null link
    ; leaves apOpnPhase at a value that names it -- 5 for the vtable, 6 for
    ; entry 0x4c. A refusal becomes readable instead of fatal.
    lwz   r12, 0xc(r3)
    cmpwi r12, 0
    beq   apOpnNoVtable
    lwz   r0, 0x4c(r12)
    cmpwi r0, 0
    beq   apOpnNoSlot

    li    r12, 3
    stw   r12, apOpnPhase@l(r11)
    lwz   r12, 0xc(r3)
    lwz   r0, 0x4c(r12)
    mtctr r0
    lwz   r9, apOpnC26@l(r11)
    lwz   r8, apOpnC25@l(r11)
    lwz   r7, apOpnC28@l(r11)
    lwz   r6, apOpnC24@l(r11)
    lwz   r5, apOpnC31@l(r11)
    lwz   r4, apOpnC27@l(r11)
    bctrl

    lis   r11, apTick@ha
    li    r12, 4
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnNoVtable:
    li    r12, 5
    stw   r12, apOpnPhase@l(r11)
    b     apOpnAfter

apOpnNoSlot:
    li    r12, 6
    stw   r12, apOpnPhase@l(r11)

apOpnAfter:
    lis   r11, apTick@ha
    lwz   r12, apSCTR@l(r11)
    mtctr r12
    lwz   r12, apSLR@l(r11)
    mtlr  r12
    lwz   r10, apS10@l(r11)
    lwz   r9, apS9@l(r11)
    lwz   r8, apS8@l(r11)
    lwz   r7, apS7@l(r11)
    lwz   r6, apS6@l(r11)
    lwz   r5, apS5@l(r11)
    lwz   r4, apS4@l(r11)
    lwz   r3, apS3@l(r11)
    lwz   r0, apS0@l(r11)

    lwz   r12, apOpnDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apOpnDone@l(r11)

apGetWinProbe6End:
    blr

apGetWinProbe7:                 ; 0x03607284, function 0x03607274
    stw   r0, 0x14(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGetWin7@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin7@l(r11)
    stw   r0, apGetWinFrom7@l(r11)
    stw   r3, apGetWinThis7@l(r11)
    stw   r4, apGetWinR4_7@l(r11)
    stw   r5, apGetWinR5_7@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd7@l(r11)
    blr

apGetWinProbe8:                 ; 0x036072f4, function 0x036072e0
    stw   r0, 0x14(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGetWin8@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin8@l(r11)
    stw   r0, apGetWinFrom8@l(r11)
    stw   r3, apGetWinThis8@l(r11)
    stw   r4, apGetWinR4_8@l(r11)
    stw   r5, apGetWinR5_8@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd8@l(r11)
    blr

apGetWinProbe9:                 ; 0x036073a0, function 0x03607390
    stw   r0, 0x14(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGetWin9@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin9@l(r11)
    stw   r0, apGetWinFrom9@l(r11)
    stw   r3, apGetWinThis9@l(r11)
    stw   r4, apGetWinR4_9@l(r11)
    stw   r5, apGetWinR5_9@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd9@l(r11)
    blr

apGetWinProbe10:                 ; 0x03607424, function 0x03607414
    stw   r0, 0x14(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGetWin10@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin10@l(r11)
    stw   r0, apGetWinFrom10@l(r11)
    stw   r3, apGetWinThis10@l(r11)
    stw   r4, apGetWinR4_10@l(r11)
    stw   r5, apGetWinR5_10@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd10@l(r11)
    blr

apGetWinProbe11:                 ; 0x036074cc, function 0x036074b8
    stw   r0, 0x1c(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGetWin11@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin11@l(r11)
    stw   r0, apGetWinFrom11@l(r11)
    stw   r3, apGetWinThis11@l(r11)
    stw   r4, apGetWinR4_11@l(r11)
    stw   r5, apGetWinR5_11@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd11@l(r11)
    blr

apGetWinProbe12:                 ; 0x03607578, function 0x03607560
    stw   r0, 0x1c(r1)         ; original
    lis   r11, apTick@ha
    lwz   r12, apGetWin12@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetWin12@l(r11)
    stw   r0, apGetWinFrom12@l(r11)
    stw   r3, apGetWinThis12@l(r11)
    stw   r4, apGetWinR4_12@l(r11)
    stw   r5, apGetWinR5_12@l(r11)
    lwz   r12, apGetSeq@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetSeq@l(r11)
    stw   r12, apGetWinOrd12@l(r11)
    blr

0x03606ae8 = bla apGetWinProbe0
0x03606c74 = bla apGetWinProbe1
0x03606e2c = bla apGetWinProbe2
0x03606ee8 = bla apGetWinProbe3
0x03606f58 = bla apGetWinProbe4
0x036070a8 = bla apGetWinProbe5
0x03607220 = bla apGetWinProbe6
0x03607284 = bla apGetWinProbe7
0x036072f4 = bla apGetWinProbe8
0x036073a0 = bla apGetWinProbe9
0x03607424 = bla apGetWinProbe10
0x036074cc = bla apGetWinProbe11
0x03607578 = bla apGetWinProbe12

apGetDrvSpy:                     ; 0x03a3ec2c, the window's driver
    ; At the anchor the mflr has already happened and r3 was copied into r30
    ; without being destroyed: the seven arguments are all still alive.
    stw   r0, 0x84(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apGetDrvN@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetDrvN@l(r11)
    stw   r0, apGetDrvFrom@l(r11)
    stw   r3, apGetDrvThis@l(r11)
    stw   r4, apGetDrvA4@l(r11)
    stw   r5, apGetDrvA5@l(r11)
    stw   r6, apGetDrvA6@l(r11)
    stw   r7, apGetDrvA7@l(r11)
    stw   r8, apGetDrvA8@l(r11)
    stw   r9, apGetDrvA9@l(r11)
    blr

0x03a3ec2c = bla apGetDrvSpy

; --- probes of the get window's pane text ---------------------------

apGetTxtSpy0:                   ; 0x02fd01ac, before bl 0x03082c70, in 0x02fcf63c
    stw   r10, 0x8(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apGetTxtN0@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetTxtN0@l(r11)
    stw   r3, apGetTxtR3_0@l(r11)
    lwz   r12, 0x0(r4)
    stw   r12, apGetTxtW0_0@l(r11)
    lwz   r12, 0x4(r4)
    stw   r12, apGetTxtW1_0@l(r11)
    blr

apGetTxtSpy1:                   ; 0x02fd01cc, before bl 0x03082d88, in 0x02fcf63c
    stw   r11, 0x8(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apGetTxtN1@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetTxtN1@l(r11)
    stw   r3, apGetTxtR3_1@l(r11)
    lwz   r12, 0x0(r4)
    stw   r12, apGetTxtW0_1@l(r11)
    lwz   r12, 0x4(r4)
    stw   r12, apGetTxtW1_1@l(r11)
    blr

apGetTxtSpy2:                   ; 0x02fd0db8, before bl 0x03083154, in 0x02fd0ce4
    stw   r8, 0x28(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apGetTxtN2@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetTxtN2@l(r11)
    stw   r3, apGetTxtR3_2@l(r11)
    lwz   r12, 0x0(r4)
    stw   r12, apGetTxtW0_2@l(r11)
    lwz   r12, 0x4(r4)
    stw   r12, apGetTxtW1_2@l(r11)

    ; --- copy 64 bytes of the text pointed to ---------------------------
    ; r3 is still alive (it holds the argument of the following bl), so it
    ; is saved in a DEDICATED field rather than in apS3, which the per-frame
    ; call blocks already use.
    stw   r3, apGetTxtSaveR3@l(r11)
    lwz   r3, 0x0(r4)
    lwz   r12, 0x0(r3)
    stw   r12, apGetTxtB0@l(r11)
    lwz   r12, 0x4(r3)
    stw   r12, apGetTxtB1@l(r11)
    lwz   r12, 0x8(r3)
    stw   r12, apGetTxtB2@l(r11)
    lwz   r12, 0xc(r3)
    stw   r12, apGetTxtB3@l(r11)
    lwz   r12, 0x10(r3)
    stw   r12, apGetTxtB4@l(r11)
    lwz   r12, 0x14(r3)
    stw   r12, apGetTxtB5@l(r11)
    lwz   r12, 0x18(r3)
    stw   r12, apGetTxtB6@l(r11)
    lwz   r12, 0x1c(r3)
    stw   r12, apGetTxtB7@l(r11)
    lwz   r12, 0x20(r3)
    stw   r12, apGetTxtB8@l(r11)
    lwz   r12, 0x24(r3)
    stw   r12, apGetTxtB9@l(r11)
    lwz   r12, 0x28(r3)
    stw   r12, apGetTxtB10@l(r11)
    lwz   r12, 0x2c(r3)
    stw   r12, apGetTxtB11@l(r11)
    lwz   r12, 0x30(r3)
    stw   r12, apGetTxtB12@l(r11)
    lwz   r12, 0x34(r3)
    stw   r12, apGetTxtB13@l(r11)
    lwz   r12, 0x38(r3)
    stw   r12, apGetTxtB14@l(r11)
    lwz   r12, 0x3c(r3)
    stw   r12, apGetTxtB15@l(r11)
    lwz   r3, apGetTxtSaveR3@l(r11)

    ; --- substitute our text, when asked ----------------------------------
    lwz   r12, apGetTxtReq@l(r11)
    cmpwi r12, 0
    beq   apGetTxtSpy2End
    li    r12, 0
    stw   r12, apGetTxtReq@l(r11)      ; one shot, not a mode: a dead client
                                       ; does not leave the window hijacked
    lis   r12, apGetTxtOur@ha
    addi  r12, r12, apGetTxtOur@l
    stw   r12, 0x0(r4)
    lwz   r12, apGetTxtDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apGetTxtDone@l(r11)
apGetTxtSpy2End:
    blr

0x02fd01ac = bla apGetTxtSpy0
0x02fd01cc = bla apGetTxtSpy1
0x02fd0db8 = bla apGetTxtSpy2

apResSpy:                        ; 0x03082c8c, entry of 0x03082c70
    ; r3/r4/r5 are still the arguments: r3 is only copied at 0x03082c90.
    ; r4 is the label's SafeString -- its first word is the const char*.
    stw   r0, 0x24(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apResN@l(r11)
    addi  r12, r12, 1
    stw   r12, apResN@l(r11)
    lwz   r12, apResArm@l(r11)
    cmpwi r12, 0
    beq   apResEnd
    cmpwi r12, 4
    beq   apResSlot0
    cmpwi r12, 3
    beq   apResSlot1
    cmpwi r12, 2
    beq   apResSlot2
    cmpwi r12, 1
    beq   apResSlot3
    b     apResEnd
apResSlot0:
    stw   r0, apResRet0@l(r11)
    stw   r3, apResA0@l(r11)
    stw   r4, apResB0@l(r11)
    stw   r5, apResC0@l(r11)
    stw   r3, apResSaveR3@l(r11)
    lwz   r3, 0x0(r4)
    lwz   r12, 0x0(r3)
    stw   r12, apResL0_0@l(r11)
    lwz   r12, 0x4(r3)
    stw   r12, apResL0_1@l(r11)
    lwz   r12, 0x8(r3)
    stw   r12, apResL0_2@l(r11)
    lwz   r12, 0xc(r3)
    stw   r12, apResL0_3@l(r11)
    lwz   r12, 0x10(r3)
    stw   r12, apResL0_4@l(r11)
    lwz   r12, 0x14(r3)
    stw   r12, apResL0_5@l(r11)
    lwz   r12, 0x18(r3)
    stw   r12, apResL0_6@l(r11)
    lwz   r12, 0x1c(r3)
    stw   r12, apResL0_7@l(r11)
    lwz   r3, apResSaveR3@l(r11)
    lwz   r12, apResArm@l(r11)
    addi  r12, r12, -1
    stw   r12, apResArm@l(r11)
    b     apResEnd
apResSlot1:
    stw   r0, apResRet1@l(r11)
    stw   r3, apResA1@l(r11)
    stw   r4, apResB1@l(r11)
    stw   r5, apResC1@l(r11)
    stw   r3, apResSaveR3@l(r11)
    lwz   r3, 0x0(r4)
    lwz   r12, 0x0(r3)
    stw   r12, apResL1_0@l(r11)
    lwz   r12, 0x4(r3)
    stw   r12, apResL1_1@l(r11)
    lwz   r12, 0x8(r3)
    stw   r12, apResL1_2@l(r11)
    lwz   r12, 0xc(r3)
    stw   r12, apResL1_3@l(r11)
    lwz   r12, 0x10(r3)
    stw   r12, apResL1_4@l(r11)
    lwz   r12, 0x14(r3)
    stw   r12, apResL1_5@l(r11)
    lwz   r12, 0x18(r3)
    stw   r12, apResL1_6@l(r11)
    lwz   r12, 0x1c(r3)
    stw   r12, apResL1_7@l(r11)
    lwz   r3, apResSaveR3@l(r11)
    lwz   r12, apResArm@l(r11)
    addi  r12, r12, -1
    stw   r12, apResArm@l(r11)
    b     apResEnd
apResSlot2:
    stw   r0, apResRet2@l(r11)
    stw   r3, apResA2@l(r11)
    stw   r4, apResB2@l(r11)
    stw   r5, apResC2@l(r11)
    stw   r3, apResSaveR3@l(r11)
    lwz   r3, 0x0(r4)
    lwz   r12, 0x0(r3)
    stw   r12, apResL2_0@l(r11)
    lwz   r12, 0x4(r3)
    stw   r12, apResL2_1@l(r11)
    lwz   r12, 0x8(r3)
    stw   r12, apResL2_2@l(r11)
    lwz   r12, 0xc(r3)
    stw   r12, apResL2_3@l(r11)
    lwz   r12, 0x10(r3)
    stw   r12, apResL2_4@l(r11)
    lwz   r12, 0x14(r3)
    stw   r12, apResL2_5@l(r11)
    lwz   r12, 0x18(r3)
    stw   r12, apResL2_6@l(r11)
    lwz   r12, 0x1c(r3)
    stw   r12, apResL2_7@l(r11)
    lwz   r3, apResSaveR3@l(r11)
    lwz   r12, apResArm@l(r11)
    addi  r12, r12, -1
    stw   r12, apResArm@l(r11)
    b     apResEnd
apResSlot3:
    stw   r0, apResRet3@l(r11)
    stw   r3, apResA3@l(r11)
    stw   r4, apResB3@l(r11)
    stw   r5, apResC3@l(r11)
    stw   r3, apResSaveR3@l(r11)
    lwz   r3, 0x0(r4)
    lwz   r12, 0x0(r3)
    stw   r12, apResL3_0@l(r11)
    lwz   r12, 0x4(r3)
    stw   r12, apResL3_1@l(r11)
    lwz   r12, 0x8(r3)
    stw   r12, apResL3_2@l(r11)
    lwz   r12, 0xc(r3)
    stw   r12, apResL3_3@l(r11)
    lwz   r12, 0x10(r3)
    stw   r12, apResL3_4@l(r11)
    lwz   r12, 0x14(r3)
    stw   r12, apResL3_5@l(r11)
    lwz   r12, 0x18(r3)
    stw   r12, apResL3_6@l(r11)
    lwz   r12, 0x1c(r3)
    stw   r12, apResL3_7@l(r11)
    lwz   r3, apResSaveR3@l(r11)
    lwz   r12, apResArm@l(r11)
    addi  r12, r12, -1
    stw   r12, apResArm@l(r11)
    b     apResEnd
apResEnd:
    blr

0x03082c8c = bla apResSpy

apSubSpy:                        ; 0x030835c8, right after bl 0x03082c70
    ; r3 is the resolver's return value: the text of <actor>_Name.
    lwz   r28, 0x278(r1)        ; original
    lis   r11, apTick@ha
    stw   r1, apR1Name@l(r11)       ; the stack where the window builds its text
    lwz   r12, apSubN@l(r11)
    addi  r12, r12, 1
    stw   r12, apSubN@l(r11)
    stw   r3, apSubOut@l(r11)

    ; MEASURED: on return, r3 is 0. So the resolver does not RETURN the
    ; text -- it writes it into the buffer the caller passes in r3, that is
    ; 0x60(r1) here (read: output = 0x0e200890, and r1 = 0x0e200830).
    ;
    ; So the STACK is read, not r3. It is safe by construction: r1 is always
    ; a valid stack pointer, where r3 could be null -- which crashed the
    ; game when a save loaded.
    ; MEASURED: 0x60(r1) holds a string with inner storage whose data starts
    ; with "Acto" -- it is the ARCHIVE PATH, not the output. The three
    ; arguments are therefore (archive, label, output) and not
    ; (output, label, archive) as the disassembly had been read.
    lwz   r12, 0x60(r1)
    stw   r12, apSubW0@l(r11)
    lwz   r12, 0x64(r1)
    stw   r12, apSubW1@l(r11)
    lwz   r12, 0x68(r1)
    stw   r12, apSubW2@l(r11)
    lwz   r12, 0x6c(r1)
    stw   r12, apSubW3@l(r11)

    ; The real output is r5, and r5 is volatile -- destroyed by the call. But
    ; it comes from r29, non-volatile, whose restore only happens at
    ; 0x030835cc: one instruction AFTER our anchor. r29 therefore still holds
    ; it. And dereferencing it is safe: being here means the resolver just
    ; wrote into it.
    stw   r4, apSubSaveR4@l(r11)
    mr    r4, r29
    stw   r4, apSubOutBuf@l(r11)
    lwz   r12, 0x0(r4)
    stw   r12, apSubO0@l(r11)
    lwz   r12, 0x4(r4)
    stw   r12, apSubO1@l(r11)
    lwz   r12, 0x8(r4)
    stw   r12, apSubO2@l(r11)
    lwz   r12, 0xc(r4)
    stw   r12, apSubO3@l(r11)
    lwz   r12, 0x10(r4)
    stw   r12, apSubO4@l(r11)
    lwz   r12, 0x14(r4)
    stw   r12, apSubO5@l(r11)
    lwz   r12, 0x18(r4)
    stw   r12, apSubO6@l(r11)
    lwz   r12, 0x1c(r4)
    stw   r12, apSubO7@l(r11)
    lwz   r4, apSubSaveR4@l(r11)

    ; --- substitution, when asked -----------------------------------------
    ; MEASURED: the output is the pair { const char16_t*, length in units },
    ; read as { 0x21c541ec, 17 } for a 17-unit name -- 18 units in the MSBT,
    ; terminator excluded. The same pair as the dialog box.
    ;
    ; apSubReq is a COUNT, not a boolean: the window resolves _Name twice,
    ; and a dead client stops renewing it. Two writes, no call: that is
    ; what makes this path safe where replaying the screen opener
    ; crashed.
    lwz   r12, apSubReq@l(r11)
    cmpwi r12, 0
    beq   apSubEnd
    addi  r12, r12, -1
    stw   r12, apSubReq@l(r11)

    stw   r4, apSubSaveR4@l(r11)
    mr    r4, r29
    lis   r12, apSubBuf@ha
    addi  r12, r12, apSubBuf@l
    stw   r12, 0x0(r4)
    lwz   r12, apSubLen@l(r11)
    stw   r12, 0x4(r4)
    lwz   r4, apSubSaveR4@l(r11)

    lwz   r12, apSubDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apSubDone@l(r11)
apSubEnd:
    blr

0x030835c8 = bla apSubSpy

apSubDescSpy:                    ; 0x03083860, right after bl 0x03082c70
    ; MIND THE ORDER: here the original instruction restores r29, so all
    ; the work happens BEFORE, and the replayed one comes last.
    lis   r11, apTick@ha
    lwz   r12, apSubDescN@l(r11)
    addi  r12, r12, 1
    stw   r12, apSubDescN@l(r11)

    lwz   r12, apSubDescReq@l(r11)
    cmpwi r12, 0
    beq   apSubDescOrig
    addi  r12, r12, -1
    stw   r12, apSubDescReq@l(r11)
    lis   r12, apSubDescBuf@ha
    addi  r12, r12, apSubDescBuf@l
    stw   r12, 0x0(r29)
    lwz   r12, apSubDescLen@l(r11)
    stw   r12, 0x4(r29)
    lwz   r12, apSubDescDone@l(r11)
    addi  r12, r12, 1
    stw   r12, apSubDescDone@l(r11)

apSubDescOrig:
    ; ORIGINAL: lmw r27, 0x22c(r1), replayed as five loads
    lwz   r27, 0x22c(r1)
    lwz   r28, 0x230(r1)
    lwz   r29, 0x234(r1)
    lwz   r30, 0x238(r1)
    lwz   r31, 0x23c(r1)
    blr

0x03083860 = bla apSubDescSpy

apShowSpy:                       ; 0x03a40d38, prologue of 0x03a40d20
    ; The staging, at its source. Anchored on the `stw r0, 0x1c(r1)` that
    ; saves LR: r0 still holds the caller, and neither r3 nor r4 has been
    ; destroyed -- the `mr r29, r3` is at 0x03a40d3c, after the anchor.
    ;   r3 = the screen    r4 = the MODE, 0 to 4
    stw   r0, 0x1c(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apShowN@l(r11)
    addi  r12, r12, 1
    stw   r12, apShowN@l(r11)
    lwz   r12, apShowT6@l(r11)
    stw   r12, apShowT7@l(r11)
    lwz   r12, apShowM6@l(r11)
    stw   r12, apShowM7@l(r11)
    lwz   r12, apShowL6@l(r11)
    stw   r12, apShowL7@l(r11)
    lwz   r12, apShowT5@l(r11)
    stw   r12, apShowT6@l(r11)
    lwz   r12, apShowM5@l(r11)
    stw   r12, apShowM6@l(r11)
    lwz   r12, apShowL5@l(r11)
    stw   r12, apShowL6@l(r11)
    lwz   r12, apShowT4@l(r11)
    stw   r12, apShowT5@l(r11)
    lwz   r12, apShowM4@l(r11)
    stw   r12, apShowM5@l(r11)
    lwz   r12, apShowL4@l(r11)
    stw   r12, apShowL5@l(r11)
    lwz   r12, apShowT3@l(r11)
    stw   r12, apShowT4@l(r11)
    lwz   r12, apShowM3@l(r11)
    stw   r12, apShowM4@l(r11)
    lwz   r12, apShowL3@l(r11)
    stw   r12, apShowL4@l(r11)
    lwz   r12, apShowT2@l(r11)
    stw   r12, apShowT3@l(r11)
    lwz   r12, apShowM2@l(r11)
    stw   r12, apShowM3@l(r11)
    lwz   r12, apShowL2@l(r11)
    stw   r12, apShowL3@l(r11)
    lwz   r12, apShowT1@l(r11)
    stw   r12, apShowT2@l(r11)
    lwz   r12, apShowM1@l(r11)
    stw   r12, apShowM2@l(r11)
    lwz   r12, apShowL1@l(r11)
    stw   r12, apShowL2@l(r11)
    lwz   r12, apShowT0@l(r11)
    stw   r12, apShowT1@l(r11)
    lwz   r12, apShowM0@l(r11)
    stw   r12, apShowM1@l(r11)
    lwz   r12, apShowL0@l(r11)
    stw   r12, apShowL1@l(r11)
    stw   r3, apShowT0@l(r11)
    stw   r4, apShowM0@l(r11)
    stw   r0, apShowL0@l(r11)
    blr

0x03a40d38 = bla apShowSpy

apUpSpy:                         ; 0x0308070c, prologue of 0x030806f0
    ; The level above 0x03a42b94: once the screen is built, it does the
    ; rest of the staging. Five arguments.
    stw   r0, 0x2c(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apUpN@l(r11)
    addi  r12, r12, 1
    stw   r12, apUpN@l(r11)
    stw   r0, apUpLr@l(r11)
    stw   r1, apUpR1@l(r11)
    stw   r3, apUpA1@l(r11)
    stw   r4, apUpA2@l(r11)
    stw   r5, apUpA3@l(r11)
    stw   r6, apUpA4@l(r11)
    stw   r7, apUpA5@l(r11)
    blr

0x0308070c = bla apUpSpy

apOpnProSpy:                     ; 0x03a42bb8, prologue of 0x03a42b94
    ; Anchored on the `stw r0, 0x34(r1)` that saves LR: r0 still holds the
    ; return address, and the prologue's six `mr` COPIED r3..r8 without
    ; destroying them. The six arguments are therefore all alive here --
    ; the only point of the body where that holds.
    ;   r3 -> r27 (manager)        r4 -> r30      r5 -> r28 (index)
    ;   r6 -> r25                  r7 -> r26      r8 -> r31 (THE HEAP)
    stw   r0, 0x34(r1)          ; original
    lis   r11, apTick@ha
    lwz   r12, apOpnProN@l(r11)
    addi  r12, r12, 1
    stw   r12, apOpnProN@l(r11)
    stw   r0, apOpnProLr@l(r11)
    stw   r1, apOpnProR1@l(r11)
    stw   r3, apOpnProA1@l(r11)
    stw   r4, apOpnProA2@l(r11)
    stw   r5, apOpnProA3@l(r11)
    stw   r6, apOpnProA4@l(r11)
    stw   r7, apOpnProA5@l(r11)
    stw   r8, apOpnProA6@l(r11)
    ; unwind the stack HERE: the chain that leads to the display
    stw   r1, apWStkF@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL0@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL1@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL2@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL3@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL4@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL5@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL6@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL7@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL8@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL9@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL10@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL11@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL12@l(r11)
    lwz   r12, apWStkF@l(r11)
    cmpwi r12, 0
    beq   apWStkEnd
    lwz   r12, 0x0(r12)
    cmpwi r12, 0
    beq   apWStkEnd
    stw   r12, apWStkF@l(r11)
    lwz   r12, 0x4(r12)
    stw   r12, apWStkL13@l(r11)
apWStkEnd:
    blr

0x03a42bb8 = bla apOpnProSpy

apOpnSpy:                        ; 0x03a42ce8, right after the factory
    ; r3 is the screen object the factory just returned; r24-r28 and r31
    ; hold the arguments the second call will receive.
    mr    r29, r3               ; original
    lis   r11, apTick@ha
    stw   r1, apR1Opn@l(r11)        ; stack of the REAL opening site
    lwz   r12, apOpnN@l(r11)
    addi  r12, r12, 1
    stw   r12, apOpnN@l(r11)
    stw   r3, apOpnThis@l(r11)
    stw   r24, apOpn24@l(r11)
    stw   r25, apOpn25@l(r11)
    stw   r26, apOpn26@l(r11)
    stw   r27, apOpn27@l(r11)
    stw   r28, apOpn28@l(r11)
    stw   r31, apOpn31@l(r11)
    blr

0x03a42ce8 = bla apOpnSpy
