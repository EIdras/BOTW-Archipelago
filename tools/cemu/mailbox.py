"""Talk to the code injected into BOTW through its code cave.

    python tools/cemu/mailbox.py            # state: tick, inbox, outbox
    python tools/cemu/mailbox.py 1234       # send 1234 and wait for the echo

Cemu keeps a copy of the patch TEXT in host memory, so the signature appears
several times. The real cave is the one where the version constant follows
the signature: in Cemu's copies these are 64-bit host pointers.
"""
import pathlib
import os
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winmem import Process

MAGIC = b"APMBOX01\x00"
VERSION = 0x0BADF00E
HOOK_GUEST = 0x031FA97C          # guest address where our bla must be
DEFAULT_LOG = pathlib.Path.home() / "AppData/Roaming/Cemu/log.txt"
LOG = None   # explicit override; otherwise BOTW_CEMU_LOG, read at call time


def log_path():
    """Cemu log to resolve the cave from.

    Read at call time, not at import: this module is imported indirectly (via
    rpx) long before a harness sets BOTW_CEMU_LOG, and a path frozen at
    import silently pointed at the original Cemu profile's log, whose stale
    codecave addresses made the guest base unresolvable.
    """
    if LOG is not None:
        return pathlib.Path(LOG)
    return pathlib.Path(os.environ.get("BOTW_CEMU_LOG", str(DEFAULT_LOG)))


def cemu_pid():
    selected = os.environ.get("BOTW_CEMU_PID")
    if selected is not None:
        if not selected.isdigit() or int(selected) <= 0:
            raise ValueError("BOTW_CEMU_PID must be a positive process ID")
        return int(selected)
    import subprocess
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "(Get-Process Cemu -ErrorAction SilentlyContinue | Select-Object -First 1).Id"],
        capture_output=True, text=True).stdout.strip()
    return int(out) if out.isdigit() else None


def be(b):
    return int.from_bytes(b, "big")


def find_cave(p):
    """Host address of the cave's version field, or None.

    `.align 4` after a 9-byte string pads by 3, so the version field is not at a
    multiple of 4 from the end of MAGIC. Every byte offset is scanned rather
    than guessing the padding.
    """
    CHUNK = 32 << 20
    for base, size in p.regions(min_size=1 << 12):
        off = 0
        while off < size:
            n = min(CHUNK, size - off)
            buf = p.read(base + off, n)
            if buf:
                i = buf.find(MAGIC)
                while i != -1:
                    tail = buf[i + len(MAGIC): i + len(MAGIC) + 20]
                    for pad in range(0, 16):
                        if len(tail) >= pad + 4 and be(tail[pad:pad + 4]) == VERSION:
                            return base + off + i + len(MAGIC) + pad
                    i = buf.find(MAGIC, i + 1)
            off += (n - len(MAGIC)) if n == CHUNK else n
    return None


def cave_guest_candidates():
    """Guest addresses Cemu reported for our code cave, newest first."""
    log = log_path()
    if not log.exists():
        return []
    out = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if "BOTW_AP_InjectionTest" in line and "Codecave:" in line:
            m = re.search(r"Codecave: ([0-9A-Fa-f]+)-", line)
            if m:
                out.append(int(m.group(1), 16))
    return list(reversed(out))


PROBE_GUEST = 0x02EB53E4        # entry of PauseMenuDataMgr::itemGet
PROBE_WORD = 0x9421FF98         # stwu r1, -0x68(r1), as it is in the RPX
# The first 28 bytes of itemGet in the RPX (our hook takes the next word,
# 0x02EB5400): a common prologue word alone can match a wrong base.
PROBE_BYTES = bytes.fromhex("9421ff98be4100307c0802a67c781b787c9923787cba2b787cdb3378")
CODECAVE_START = 0x01800000     # Cemu's first graphic-pack code cave
CODECAVE_SPAN = 0x00100000


def guest_base(p, cave_host):
    """Map guest addresses to host ones: host = guest + base.

    The base is checked on an instruction of the RPX that no pack patches, and
    not on our own hook: another graphic pack may take the same address
    (FPS++ patches 0x031FA97C), and checking our hook would then fail the
    whole resolution although the base is right.
    """
    # 04/10: the log read may be another profile's, and another pack's code
    # cave (a test aid) moves ours: Cemu places them from CODECAVE_START, each
    # aligned on 0x100, so every such address is tried after the log's.
    scan = range(CODECAVE_START, CODECAVE_START + CODECAVE_SPAN, 0x100)
    for g in [*cave_guest_candidates(), *scan]:
        base = cave_host - g
        raw = p.read(base + PROBE_GUEST, len(PROBE_BYTES))
        if raw == PROBE_BYTES:
            return base, g, None
    return None, None, None


def hook_owner(p, base):
    """Is our per-frame hook still in place, or did another pack take it?"""
    raw = p.read(base + HOOK_GUEST, 4)
    if not raw or len(raw) < 4:
        return None
    v = be(raw)
    if (v >> 26) != 18 or not ((v >> 1) & 1) or not (v & 1):
        return "no hook"
    return v & 0x03FFFFFC


def hook_is_ours(p, base, cave_g, owner):
    """Does the per-frame hook really jump to OUR probe?

    An address range is not enough, and the first version proved it: it
    accepted `cave_g + 0x400`, while the cave's code starts after ~5.4 KB of
    data. Our own probe was therefore reported as stolen at every run of
    `mailbox.py`.

    The deciding test is the probe's signature: it replays the original
    instruction, then loads the cave's page with `lis r11, cave_g >> 16` to
    increment the tick. Another pack has no reason to write that very
    constant.
    """
    if not isinstance(owner, int):
        return False
    raw = p.read(base + owner + 4, 4)
    if not raw or len(raw) < 4:
        return False
    return be(raw) == 0x3D600000 | ((cave_g >> 16) & 0xFFFF)


class CaveUnavailable(RuntimeError):
    """Cemu missing, patch inactive, or guest/host base unresolvable."""


def open_cave(*, writable=True):
    """Open the cave: returns (Process, Cave). Close it with the Process.

        from mailbox import open_cave
        p, c = open_cave()
        with p:
            ...

    Every tool used to repeat this boilerplate. The Archipelago client does
    not need to know it: it needs a Cave object, not the signature search.

    """
    pid = cemu_pid()
    if not pid:
        raise CaveUnavailable("Cemu is not running")
    p = Process(pid, writable=writable)
    try:
        addr = find_cave(p)
        if addr is None:
            raise CaveUnavailable(
                "code cave not found: is the graphic pack enabled? "
                "(python tools/cemu/mailbox.py to diagnose)")
        base, _, _ = guest_base(p, addr - 12)
        if base is None:
            raise CaveUnavailable(
                "guest/host base unresolvable: restart the game")
        return p, Cave(p, addr, base)
    except Exception:
        p.__exit__(None, None, None)
        raise


class Cave:
    """Map of the code cave's fields, all relative to the version field.

    The order must stay in step with the data block at the top of
    patch_apInject.asm. An offset error raises nothing: it silently writes
    into the wrong field.
    """

    def __init__(self, p, version_addr, base=None):
        self.p = p
        self.base = base
        self.tick = version_addr + 4
        self.inbox = version_addr + 8
        self.outbox = version_addr + 12
        self.lastseen = version_addr + 16
        self.itemget = version_addr + 20
        self.name_ptr = version_addr + 24
        self.value = version_addr + 28
        self.pmdm_this = version_addr + 32
        self.give_req = version_addr + 36
        self.give_value = version_addr + 40
        self.give_done = version_addr + 44
        self.rune_req = version_addr + 48
        self.rune_count = version_addr + 52
        self.rune_done = version_addr + 56
        self.notify_req = version_addr + 60
        self.notify_done = version_addr + 64
        self.hook_mask = version_addr + 68
        self.hook_counts = version_addr + 72      # 9 consecutive counters
        self.pickup_this = version_addr + 108
        self.screen_this = version_addr + 112     # the PickUpWin screen
        self.duration = version_addr + 116        # float captured on the fly
        self.save_f1 = version_addr + 120
        self.list_this = version_addr + 124       # screen + 0x1b68: row pool
        self.name_buf = version_addr + 152
        self.text_buf = version_addr + 216       # 256 bytes of free text
        self.ms_mask = version_addr + 472        # probes of the center message
        self.ms_counts = version_addr + 476      # 6 consecutive counters
        self.ms_this = version_addr + 500
        self.ms1_this = version_addr + 504   # 'this' of the candidate
        self.ms_req = version_addr + 508
        self.ms_index = version_addr + 512
        self.ms_state = version_addr + 516
        self.ms_done = version_addr + 520
        self.ms_queue = version_addr + 524   # guard this+0x150
        self.ms_saveq = version_addr + 528
        self.ms_ret = version_addr + 532     # the API's return, 0 = refused
        self.ms_flag = version_addr + 536    # r4: a boolean, not an index
        self.ms_pass = version_addr + 540    # reaches the push
        self.ms_bail = version_addr + 544    # early exit
        self.ms_mid = version_addr + 552     # after the first 3 tests
        self.ms_dbg8c = version_addr + 556   # 0x8c as the function sees it
        self.ms_dbg154 = version_addr + 560  # read by the cave, in the
        self.ms_dbg150 = version_addr + 564  # same frame as the call
        self.ms_dbgc = version_addr + 568
        self.push_this = version_addr + 572  # arguments read on the push
        self.push_a = version_addr + 576
        self.push_b = version_addr + 580
        self.push_n = version_addr + 584
        self.play_a = version_addr + 588    # values to replay
        self.play_b = version_addr + 592
        self.play_req = version_addr + 596
        self.play_done = version_addr + 600
        self.msg_cstr = version_addr + 604   # a SafeString of ours
        self.play_raw = version_addr + 612   # 1 = replay the game's pointer
        # --- blue tip frame (MessageTipsRunTime_00) ---
        self.tips_mask = version_addr + 616
        self.tips_counts = version_addr + 620     # 8 consecutive counters
        self.tips_this = version_addr + 652       # widget, seen per frame
        self.tips_show_this = version_addr + 656  # this seen at the real display
        self.tips_show_idx = version_addr + 660   # index requested by the game
        self.tips_req = version_addr + 664
        self.tips_index = version_addr + 668
        self.tips_done = version_addr + 672
        self.tips_text_req = version_addr + 676
        self.tips_text_len = version_addr + 680
        self.tips_text_done = version_addr + 684
        self.tips_spy_ptr = version_addr + 688    # the game's text object: word 0
        self.tips_spy_len = version_addr + 692    # and word 1
        self.pane_cstr = version_addr + 696
        self.tips_str_ptr = version_addr + 704
        # --- tracer of message resolutions (0x03a38ad0) ---
        self.ring_left = version_addr + 712   # quota left
        self.ring_ptr = version_addr + 716    # where to write, a GUEST address
        # --- dialog window (Message_00 / MessageSp_00) ---
        self.dlg_open_n = version_addr + 720   # calls seen of 0x035ff8fc
        self.dlg_open0_n = version_addr + 724  # ... of which with a NUL flag
        self.dlg_set_n = version_addr + 728    # calls seen of 0x035fb5f8
        self.dlg_this = version_addr + 732     # the window; its +0x1d0 holds
        self.dlg_seen_arc = version_addr + 736 # the text { ptr, length }
        self.dlg_seen_lbl = version_addr + 740
        self.dlg_arg6 = version_addr + 744     # arguments read on a real
        self.dlg_arg7 = version_addr + 748     # call, to be replayed
        self.dlg_arg8 = version_addr + 752
        self.dlg_req = version_addr + 756
        self.dlg_done = version_addr + 760
        self.dlg_text_req = version_addr + 764
        self.dlg_text_done = version_addr + 768
        self.dlg_str_ptr = version_addr + 772
        self.dlg_str_len = version_addr + 776
        self.arc_buf = version_addr + 796      # 64 bytes, ASCII
        self.lbl_buf = version_addr + 860      # 32 bytes, ASCII
        self.ring = version_addr + 892         # 48 entries { site, label }
        self.ring_n = 48
        self.dlg_buf = version_addr + 1276     # 4096 bytes = 2048 units
        self.dlg_buf_size = 4096
        # --- pickup interception (itemGet) ---
        self.ig_left = version_addr + 5372     # the log's quota
        self.ig_ptr = version_addr + 5376      # where to write, a GUEST address
        self.block_req = version_addr + 5380   # 1 = neutralise the next one
        self.block_done = version_addr + 5384
        self.grant_mark = version_addr + 5388  # 1 = GRANTED item in progress
        self.block_grants = version_addr + 5392  # neutralise every granted item

        # Probe bench of the item get window (MessageGet_00): 19 contiguous
        # counters, one per function from 0x02fcf29c to 0x02fd33e0. Appended
        # at the END of the block so that no existing field moves.
        self.get0 = version_addr + 5828
        self.get_n = 19
        self.get_from0 = version_addr + 5904   # return address
        self.get_this0 = version_addr + 5980   # r3
        self.get_r4_0 = version_addr + 6056    # r4
        self.get_r5_0 = version_addr + 6132    # r5
        self.get_seq = version_addr + 6208     # shared order counter
        self.get_ord0 = version_addr + 6212    # rank, bench 1

        # Bench 2: the manager class, 13 functions from 0x03606ad0 to
        # 0x03607560. That is where the window's callable API lives.
        self.get_win0 = version_addr + 6288
        self.get_win_n = 13
        self.get_win_from0 = version_addr + 6340
        self.get_win_this0 = version_addr + 6392
        self.get_win_r4_0 = version_addr + 6444
        self.get_win_r5_0 = version_addr + 6496
        self.get_win_ord0 = version_addr + 6548

        # The driver 0x03a3ec0c: its seven arguments captured on a real
        # trigger, and the replay with our own string in place of r6.

        self.get_drv_n = version_addr + 6600
        self.get_drv_from = version_addr + 6604
        self.get_drv_this = version_addr + 6608
        self.get_drv_a4 = version_addr + 6612
        self.get_drv_a5 = version_addr + 6616
        self.get_drv_a6 = version_addr + 6620
        self.get_drv_a7 = version_addr + 6624
        self.get_drv_a8 = version_addr + 6628
        self.get_drv_a9 = version_addr + 6632
        self.get_drv_req = version_addr + 6636
        self.get_drv_done = version_addr + 6640
        self.get_drv_name = version_addr + 6644   # 64 bytes

        # FILTERED capture: only for MessageGet_00, frozen by the probe
        # apGetProbe1 that only this screen goes through. The get_drv_* fields
        # above hold for the last screen opened, whatever it is.
        self.get_win_ok = version_addr + 6708
        self.get_win_cthis = version_addr + 6712
        self.get_win_ca4 = version_addr + 6716
        self.get_win_ca5 = version_addr + 6720
        self.get_win_ca6 = version_addr + 6724
        self.get_win_ca7 = version_addr + 6728
        self.get_win_ca8 = version_addr + 6732
        self.get_win_ca9 = version_addr + 6736

        # Three probes of the panes' text: { count, r3, word0, word1 }.
        self.get_txt_n0 = version_addr + 6740
        self.get_txt_n = 3
        self.get_txt_req = version_addr + 6792
        self.get_txt_done = version_addr + 6796
        self.get_txt_b0 = version_addr + 6800    # 64 bytes copied
        self.get_txt_our = version_addr + 6864   # 128 bytes = 64 units

        # Probe of the entry of the common resolver 0x03082c70. Four successive
        # captures once armed, 44 bytes each:
        # { r3, r4, r5, 32 bytes of the label pointed to by *(r4) }.
        self.res_arm = version_addr + 6992
        self.res_n = version_addr + 6996
        self.res_a0 = version_addr + 7004
        self.res_slots = 4
        self.res_stride = 44
        self.res_ret0 = version_addr + 7180    # return address, per slot

        # Substitution of the item name at 0x030835c8, where r3 is the resolved text.
        self.sub_n = version_addr + 7196
        self.sub_out = version_addr + 7200
        self.sub_w0 = version_addr + 7204      # 4 words of the returned object
        self.sub_req = version_addr + 7220
        self.sub_done = version_addr + 7224
        self.sub_out_buf = version_addr + 7236  # r29: the REAL output
        self.sub_o0 = version_addr + 7240       # 8 words of that output
        self.sub_len = version_addr + 7232      # our object, 4 words
        self.sub_buf = version_addr + 7288      # our text, 256 bytes

        # The same mechanism for the description, site 0x03083860.
        self.sub_desc_n = version_addr + 7544
        self.sub_desc_req = version_addr + 7548
        self.sub_desc_done = version_addr + 7552
        self.sub_desc_len = version_addr + 7556
        self.sub_desc_buf = version_addr + 7560   # 512 bytes = 256 units
        self.sub_auto = version_addr + 8072      # count of granted items
        self.sub_auto_n = version_addr + 8076    # resolutions per item

        # Opening the window ourselves: the six registers of the real site, and
        # the replay of BOTH chained calls (factory, then open).
        self.opn_n = version_addr + 8080
        self.opn_this = version_addr + 8084
        self.opn24 = version_addr + 8088
        self.opn25 = version_addr + 8092
        self.opn26 = version_addr + 8096
        self.opn27 = version_addr + 8100
        self.opn28 = version_addr + 8104
        self.opn31 = version_addr + 8108
        self.opn_req = version_addr + 8112
        self.opn_done = version_addr + 8116
        # Filtered capture: only for MessageGet_00. The raw probe fires
        # at every screen opening, 40 times per game.
        self.opn_ok = version_addr + 8120
        self.opn_c24 = version_addr + 8124
        self.opn_c25 = version_addr + 8128
        self.opn_c26 = version_addr + 8132
        self.opn_c27 = version_addr + 8136
        self.opn_c28 = version_addr + 8140
        self.opn_c31 = version_addr + 8144
        # r1 read at three places, to tell whether there are several stacks.
        self.r1_frame = version_addr + 8148
        self.r1_ui = version_addr + 8152
        self.r1_name = version_addr + 8156
        self.r1_opn = version_addr + 8160
        self.opn_step = version_addr + 8164   # 1 = factory only, 2 = everything
        self.opn_phase = version_addr + 8168  # how far the replay went
        self.opn_r3 = version_addr + 8172     # what the factory returned
        self.opn_heap = version_addr + 8308   # 0 = current heap (recommended)
        self.opn_mode = version_addr + 8312   # 0 = factory, 1 = trampoline, 2 = enclosing
        self.opn_ctx_on = version_addr + 8316  # 0 = do NOT copy the dead heap
        self.opn_arg4 = version_addr + 8320    # r30, argument 2 of 0x03a42b94
        # Where a live heap comes from: probe of the getter 0x030aa1ac.
        self.heap_req = version_addr + 8324
        self.heap_n = version_addr + 8328
        self.heap_root = version_addr + 8332   # *(0x1046C8B0)
        self.heap_mgr = version_addr + 8336    # *(0x1046C920)
        self.heap_fb = version_addr + 8340     # *(root + 4), static fallback
        self.heap_cur = version_addr + 8344    # what 0x030aa1ac returned
        # The prologue of 0x03a42b94: six arguments + the caller.
        self.opn_pro_n = version_addr + 8348
        self.opn_pro_lr = version_addr + 8352
        self.opn_pro_r1 = version_addr + 8356
        self.opn_pro_a1 = version_addr + 8360
        self.opn_pro_a2 = version_addr + 8364
        self.opn_pro_a3 = version_addr + 8368
        self.opn_pro_a4 = version_addr + 8372
        self.opn_pro_a5 = version_addr + 8376
        self.opn_pro_a6 = version_addr + 8380
        self.opn_prc_ok = version_addr + 8384
        self.opn_prc_lr = version_addr + 8388
        self.opn_prc_r1 = version_addr + 8392
        self.opn_prc_a1 = version_addr + 8396
        self.opn_prc_a2 = version_addr + 8400
        self.opn_prc_a3 = version_addr + 8404
        self.opn_prc_a4 = version_addr + 8408
        self.opn_prc_a5 = version_addr + 8412
        self.opn_prc_a6 = version_addr + 8416
        # The level above: 0x030806f0, which calls 0x03a42b94 and then
        # runs the staging.
        self.up_n = version_addr + 8420
        self.up_lr = version_addr + 8424
        self.up_r1 = version_addr + 8428
        self.up_a1 = version_addr + 8432
        self.up_a2 = version_addr + 8436
        self.up_a3 = version_addr + 8440
        self.up_a4 = version_addr + 8444
        self.up_a5 = version_addr + 8448
        self.upc_ok = version_addr + 8452
        self.upc_a1 = version_addr + 8456
        self.upc_a2 = version_addr + 8460
        self.upc_a3 = version_addr + 8464
        self.upc_a4 = version_addr + 8468
        self.upc_a5 = version_addr + 8472
        self.opn_anim = version_addr + 8476   # play the "open" animation
        self.opn_varg = version_addr + 8480   # the mode passed to vtable[0x1a4]
        # Shift register of the staging 0x03a40d20(screen, mode).
        # The top of the chain: 0x02b769c4(r3, r4), the granted item.
        self.grant_r3 = version_addr + 8484
        self.grant_r4 = version_addr + 8488
        self.grant_lr = version_addr + 8492
        # The copy of the stack structure 0x02b769c4 receives in r4.
        self.grant_buf_ptr = version_addr + 8496
        # The broadcast 0x032bc730(dispatcher, itemName).
        self.disp_n = version_addr + 8500
        self.disp_r3 = version_addr + 8504
        self.disp_r4 = version_addr + 8508
        self.disp_lr = version_addr + 8512
        self.grant_name = version_addr + 8516
        self.disp_arg = version_addr + 8520      # the dispatcher, MEASURED
        # The generic invoker: Python stores an address and eight arguments,
        # the cave jumps. No call experiment needs a patch change any more.

        self.call_addr = version_addr + 8524
        self.call_a1 = version_addr + 8528       # 8 consecutive arguments
        self.call_ret = version_addr + 8560
        self.call_n = version_addr + 8564
        # The SAME invoker, on the per-frame hook: that one runs from the
        # game's start, without prerequisite. The other lives in the
        # MessageGet_00 driver and stays silent until the real window has
        # been seen -- leaving the request pending, which then went off at
        # the next real chest. Shares apCallAddr / apCallA1..A8.
        self.pf_req = version_addr + 9260
        # The resolver of channel pointers, on the same per-frame hook: it
        # rewrites pmdm_this / screen_this / list_this / ms1_this /
        # push_this / dlg_this every frame from the game's globals, instead
        # of waiting for a probe to see them go by.
        self.resolve_n = version_addr + 9264     # passes -- a safeguard
        self.scr_table = version_addr + 9268     # screen table, 0 = no UI
        # Rune selection requested from the game (apCheckSel), at the end of
        # the block. Missing from older patches: sel_ready() checks it.
        self.sel_magic = version_addr + 9272
        self.sel_req = version_addr + 9276
        self.sel_type = version_addr + 9280
        self.sel_done = version_addr + 9284
        self.sel_result = version_addr + 9288
        # The tower maps (tools/build_tower_maps_native.py), after them: the
        # tower index the next map opening takes when no tower is near.
        self.map_magic = version_addr + 9292
        self.map_tower = version_addr + 9296
        # The Downpour trap's weather (tools/build_weather_native.py), after
        # apTowerName ("APTower_", 9 bytes, aligned to 12).
        self.weather_magic = version_addr + 9312
        self.weather_type = version_addr + 9316
        self.weather_frames = version_addr + 9320
        self.weather_passes = version_addr + 9324
        # The twelve levels of the call chain, probed at once.
        # Each level: N, r3, r4, r5, r6, r7, Lr -- 7 words.
        self.lvl0 = version_addr + 8568
        self.lvl_mots = 7
        self.lvl_ids = (0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 13)
        # The whole call chain, unwound from the grant's frame.
        # The call chain of the WINDOW, unwound on the screen's creation.
        # That is the one wanted: unwinding the item grant led to the
        # attribution, not to the display.
        # Keeping the window up, once per frame in the cave.
        # A frame count, not a boolean: a dead client lets the game go back
        # to normal on its own.
        self.hold_n = version_addr + 8904
        self.hold_q = version_addr + 8908        # 0 = leave +0x44 alone
        self.wstk_f = version_addr + 8912
        self.wstk_l0 = version_addr + 8916
        self.stk_f = version_addr + 8972
        self.stk_l0 = version_addr + 8976        # 14 return addresses
        self.stk_n = 14
        self.grant_buf = version_addr + 9032     # 32 words
        self.show_n = version_addr + 9160
        self.show_t0 = version_addr + 9164
        self.show_m0 = version_addr + 9196
        self.show_l0 = version_addr + 9228
        self.grant_n = version_addr + 5396     # passes through 0x02b769c4
        self.ig_ring = version_addr + 5400     # 32 entries of 12 bytes
        self.ig_ring_n = 32

    def ig_arm(self, n=None):
        """Arm the pickup log."""
        n = min(n or self.ig_ring_n, self.ig_ring_n)
        self.p.write(self.ig_ring, bytes(self.ig_ring_n * 12))
        self.p.write(self.ig_ptr, self.guest(self.ig_ring).to_bytes(4, "big"))
        self.p.write(self.ig_left, n.to_bytes(4, "big"))
        return n

    def ig_read(self):
        """[(call site, name cstr, quantity)] recorded so far."""
        left = be(self.p.read(self.ig_left, 4))
        used = self.ig_ring_n - left
        raw = self.p.read(self.ig_ring, used * 12) if used else b""
        return [(be(raw[i * 12:i * 12 + 4]),
                 be(raw[i * 12 + 4:i * 12 + 8]),
                 be(raw[i * 12 + 8:i * 12 + 12]))
                for i in range(used)]

    def ring_arm(self, n=None):
        """Arm the tracer: it records the next n resolutions.

        The pointer is a guest address -- the injected code writes to it,
        not us.
        """
        n = min(n or self.ring_n, self.ring_n)
        self.p.write(self.ring, bytes(self.ring_n * 8))
        self.p.write(self.ring_ptr, self.guest(self.ring).to_bytes(4, "big"))
        self.p.write(self.ring_left, n.to_bytes(4, "big"))
        return n

    def ring_read(self):
        """[(call site, guest address of the label)] recorded so far.

        `ring_left` alone does not tell how many entries are written: after
        the game starts it is 0, exactly as when the quota is used up, and
        `ring_n - 0` then made 48 empty rows pass for 48 resolutions. The
        write pointer decides: the injected code never sets it by itself,
        only `ring_arm` does.
        """
        if not be(self.p.read(self.ring_ptr, 4)):
            return []
        left = be(self.p.read(self.ring_left, 4))
        used = self.ring_n - left
        raw = self.p.read(self.ring, used * 8) if used else b""
        rows = [(be(raw[i * 8:i * 8 + 4]), be(raw[i * 8 + 4:i * 8 + 8]))
                for i in range(used)]
        while rows and rows[-1] == (0, 0):
            rows.pop()
        return rows

    def cstr(self, guest_addr, n=64):
        """Read a C string at a guest address.

        Decoded with "backslashreplace", not "replace": the Windows console
        is cp1252 and cannot write the U+FFFD that "replace" produces. The
        message log crashed on the first non-ASCII label -- right after
        printing the useful lines.
        """
        if not guest_addr or self.base is None:
            return None
        raw = self.p.read(guest_addr + self.base, n)
        if not raw:
            return None
        return raw.split(b"\x00")[0].decode("ascii", "backslashreplace")

    def get_probes(self):
        """Counters of the 19 probes of the item get window."""
        raw = self.p.read(self.get0, self.get_n * 4)
        return [be(raw[i * 4:i * 4 + 4]) for i in range(self.get_n)]

    def get_reset(self):
        """Reset the bench, right before triggering."""
        self.p.write(self.get0, bytes(self.get_n * 4))
        for base in (self.get_from0, self.get_this0,
                     self.get_r4_0, self.get_r5_0, self.get_ord0):
            self.p.write(base, bytes(self.get_n * 4))
        self.p.write(self.get_seq, bytes(4))
        for base in (self.get_win0, self.get_win_from0, self.get_win_this0,
                     self.get_win_r4_0, self.get_win_r5_0,
                     self.get_win_ord0):
            self.p.write(base, bytes(self.get_win_n * 4))

    def sub_sample(self):
        """(count, output, [4 words of the returned object or None]).

        The four words come from 0x60(r1), the output buffer the caller
        passes to the resolver -- not from *(r3), which is 0 on return and
        crashed the game.
        """
        n = be(self.p.read(self.sub_n, 4))
        out = be(self.p.read(self.sub_out, 4))
        raw = self.p.read(self.sub_w0, 16)
        words = ([be(raw[i * 4:i * 4 + 4]) for i in range(4)]
                if raw and len(raw) == 16 else None)
        raw2 = self.p.read(self.sub_o0, 32)
        output = ([be(raw2[i * 4:i * 4 + 4]) for i in range(8)]
                  if raw2 and len(raw2) == 32 else None)
        return n, out, words, be(self.p.read(self.sub_out_buf, 4)), output

    def open_item_window(self, title=None, description=None, step=2):
        """Open the item get window, without an item.

        Replays BOTH calls of the real site: the factory that makes the screen
        object, then slot 0x4c of its vtable, which opens it. Replaying only
        the second -- what `getwin.py --open` did -- crashed the game three
        times out of three.

        Prerequisite: the real window seen once since the game started, so
        that the site's six registers are captured.
        """
        if not be(self.p.read(self.opn_ok, 4)):
            raise RuntimeError("MessageGet_00 has not been seen opening since "
                               "the start: open a real chest once")
        self.p.write(self.opn_step, step.to_bytes(4, "big"))
        if title is not None:
            self.sub_write(title, 2)
        if description is not None:
            self.sub_write_desc(description, 2)
        self.p.write(self.opn_phase, bytes(4))
        self.p.write(self.opn_req, (1).to_bytes(4, "big"))

    def heap_probe(self):
        """Ask for the probe of the current heap, on the UI thread.

        Gives (n, root, mgr, fb, cur) afterwards. The probe runs at the next
        frame in apGetWinProbe6 -- the only instrumented point that runs on
        the right stack family.
        """
        self.p.write(self.heap_req, (1).to_bytes(4, "big"))

    def heap_state(self):
        return tuple(be(self.p.read(a, 4)) for a in
                     (self.heap_n, self.heap_root, self.heap_mgr,
                      self.heap_fb, self.heap_cur))

    def levels(self):
        """[(level, calls, [r3..r7], lr)] for the twelve probed levels."""
        out = []
        for k, level in enumerate(self.lvl_ids):
            b = self.lvl0 + k * self.lvl_mots * 4
            words = [be(self.p.read(b + i * 4, 4))
                     for i in range(self.lvl_mots)]
            out.append((level, words[0], words[1:6], words[6]))
        return out

    def call(self, addr, *args):
        """Call anything from the UI thread. Up to 8 arguments.

        No check here: the caller reads the memory and makes sure what it
        passes holds. The cave only keeps the jump.
        """
        self.p.write(self.call_addr, addr.to_bytes(4, "big"))
        for i in range(8):
            v = args[i] if i < len(args) else 0
            self.p.write(self.call_a1 + i * 4, (v & 0xFFFFFFFF).to_bytes(4, "big"))
        self.p.write(self.opn_mode, (8).to_bytes(4, "big"))
        self.p.write(self.opn_phase, bytes(4))
        self.p.write(self.opn_req, (1).to_bytes(4, "big"))

    def pf_ready(self):
        """Does the loaded patch know apPfReq?

        GUARD against a stale patch: a field appended at the end of the
        block falls on CODE until Cemu is restarted, and reads without error.
        The field is a flag: it can only be 0 or 1. Any other value means
        the patch in memory is stale.
        """
        return be(self.p.read(self.pf_req, 4)) in (0, 1)

    def resolve_ready(self):
        """Does the loaded patch know the pointer resolver?

        SAME GUARD as `pf_ready`, with the invariant already used in
        `getprobe.py`: a counter incremented once per frame cannot exceed the
        number of frames elapsed. On a stale patch the field falls on code and
        reads without error -- but it then holds an instruction word, far
        above the tick.

        Gives (ready, resolve_n, tick) so that the caller can SAY it.
        """
        n = be(self.p.read(self.resolve_n, 4))
        tick = be(self.p.read(self.tick, 4))
        return (0 < n <= tick), n, tick

    def ui_ready(self):
        """Is the game's UI built? (screen table resolved)

        It is the only prerequisite left, and it is not ours: the display
        functions dereference the screen manager without testing it. It is
        met as soon as a save is loaded.
        """
        ok, _, _ = self.resolve_ready()
        return ok and be(self.p.read(self.scr_table, 4)) != 0

    def channels(self):
        """State of the four display channels, to say it at start-up.

        {name: (pointer, ready)}. The Archipelago client must print it: a
        silent channel without an explanation is the first cause of errors.
        """
        fields = (("give / itemGet", self.pmdm_this),
                  ("notification", self.list_this),
                  ("center message", self.ms1_this),
                  ("dialog box", self.scr_table))
        out = {}
        for name, addr in fields:
            v = be(self.p.read(addr, 4))
            out[name] = (v, v != 0)
        return out

    def call_pf(self, addr, *args):
        """Same as `call`, but from the PER-FRAME hook.

        No prerequisite: this hook runs from the game's start, where `call`
        sleeps until MessageGet_00 has been seen. Same protocol, same
        argument fields, same counter `call_n`.

        Caveat: the patch documents a thread affinity for REPLAYING the
        opening site -- stack 0x12b3c510 there, 0x0e201270 here, four crashes
        as a result. It held for the modes that handle a screen's inside; for
        a clean call it is still to be measured.
        """
        if not self.pf_ready():
            raise RuntimeError(
                "apPfReq reads an impossible value: the loaded patch is "
                "STALE. Close and reopen Cemu (reloading a save is not "
                "enough).")
        self.p.write(self.call_addr, addr.to_bytes(4, "big"))
        for i in range(8):
            v = args[i] if i < len(args) else 0
            self.p.write(self.call_a1 + i * 4, (v & 0xFFFFFFFF).to_bytes(4, "big"))
        self.p.write(self.pf_req, (1).to_bytes(4, "big"))

    def call_stack(self, window=False):
        """Return addresses: the item grant chain, or the WINDOW's."""
        base = self.wstk_l0 if window else self.stk_l0
        return [be(self.p.read(base + i * 4, 4))
                for i in range(self.stk_n)]

    def show_ring(self):
        """The last 8 calls of 0x03a40d20: (screen, mode, caller).

        The probe does not filter -- 0x03a40d20 serves 94 classes -- so ours
        is recognized here. Entry 0 = the most recent.
        """
        n = be(self.p.read(self.show_n, 4))
        out = []
        for i in range(8):
            out.append((be(self.p.read(self.show_t0 + i * 4, 4)),
                        be(self.p.read(self.show_m0 + i * 4, 4)),
                        be(self.p.read(self.show_l0 + i * 4, 4))))
        return n, out

    def upper_args(self):
        """The five arguments of 0x030806f0 for MessageGet_00, and the caller."""
        fields = (self.upc_ok, self.up_lr, self.upc_a1, self.upc_a2,
                  self.upc_a3, self.upc_a4, self.upc_a5)
        ok, lr, *args = [be(self.p.read(a, 4)) for a in fields]
        return ok, lr, args

    def open_prologue(self):
        """The six arguments of 0x03a42b94 for MessageGet_00, and the caller.

        Capture frozen by apGetProbe1: it only holds when the report is
        non-zero; otherwise the real window has not been seen opening.
        """
        fields = (self.opn_prc_ok, self.opn_prc_lr, self.opn_prc_r1,
                  self.opn_prc_a1, self.opn_prc_a2, self.opn_prc_a3,
                  self.opn_prc_a4, self.opn_prc_a5, self.opn_prc_a6)
        ok, lr, r1, *args = [be(self.p.read(a, 4)) for a in fields]
        return ok, lr, r1, args

    def open_state(self):
        """(raw captures, replays, filtered MessageGet_00 captures)."""
        return (be(self.p.read(self.opn_n, 4)),
                be(self.p.read(self.opn_done, 4)),
                be(self.p.read(self.opn_ok, 4)))

    def arm_next_grant(self, title, description=None, n=2):
        """Substitute the text of the NEXT granted item -- chest, Korok,
        shrine, NPC gift.

        This is the form an Archipelago client uses. It differs from
        `show_item_text` on the one point that matters: the CAVE picks the
        moment, on the probe of granted items, not us.

        Why it matters: the site that resolves the name is generic -- the
        inventory uses it too. Arming by hand, then opening the pouch,
        hijacks the name of the item looked at (measured in the game). Here
        the substitution is armed only at the moment of a granted item, so
        never while browsing.
        """
        self.sub_write(title, 0)
        if description is not None:
            self.sub_write_desc(description, 0)
        self.p.write(self.sub_auto_n, n.to_bytes(4, "big"))
        self.p.write(self.sub_auto, (1).to_bytes(4, "big"))

    def show_item_text(self, title, description=None, n=2):
        """Prototype: publish text for n resolutions, without request identity.

        The legacy hook is global. EventFlow callers must verify the Item_AP
        gates before using this primitive. A quota does not expire on its own
        if the companion disappears. This is not a production delivery API.
        """
        # Validate both strings before publishing either quota. This prevents
        # an invalid description from leaving the title armed on its own.
        self._sub_payload(title, 256, n)
        if description is not None:
            self._sub_payload(description, 512, n)
        self.sub_write(title, n)
        if description is not None:
            self.sub_write_desc(description, n)

    def sub_write_desc(self, s, n=2):
        """The same for the description, site 0x03083860."""
        data, length, quota = self._sub_payload(s, 512, n)
        self.p.write(self.sub_desc_buf, data)
        self.p.write(self.sub_desc_len, length)
        self.p.write(self.sub_desc_req, quota)

    @staticmethod
    def _sub_payload(s, size, n):
        if not isinstance(n, int) or isinstance(n, bool) or not 0 <= n <= 0xFFFFFFFF:
            raise ValueError("quota must be an unsigned 32-bit integer")
        if "\0" in s:
            raise ValueError("embedded NUL in presentation text")
        data = s.encode("utf-16-be")
        units = len(data) // 2
        if len(data) + 2 > size:
            raise ValueError(f"{units} units: the buffer holds {size // 2 - 1}")
        return data + bytes(size - len(data)), units.to_bytes(4, "big"), n.to_bytes(4, "big")

    def sub_disarm(self):
        """Disarm everything: the next window is normal again."""
        self.p.write(self.sub_req, bytes(4))
        self.p.write(self.sub_desc_req, bytes(4))
        self.p.write(self.sub_auto, bytes(4))

    def sub_state(self):
        """(title_armed, title_set, desc_armed, desc_set, auto)."""
        return (be(self.p.read(self.sub_req, 4)),
                be(self.p.read(self.sub_done, 4)),
                be(self.p.read(self.sub_desc_req, 4)),
                be(self.p.read(self.sub_desc_done, 4)),
                be(self.p.read(self.sub_auto, 4)))

    def sub_write(self, s, n=2):
        """Store our text, and arm the substitution for n resolutions.

        The resolver's output is the pair { const char16_t*, length in
        units }, measured { 0x21c541ec, 17 } for a 17-unit name. The length
        EXCLUDES the terminator, as everywhere else in this game.

        n defaults to 2: building the window resolves _Name twice, and
        substituting only one of the two would let the real name show
        again.
        """
        data, length, quota = self._sub_payload(s, 256, n)
        self.p.write(self.sub_buf, data)
        self.p.write(self.sub_len, length)
        self.p.write(self.sub_req, quota)

    def res_arm_now(self, n=None):
        """Arm the capture of the next n resolutions (4 at most)."""
        n = min(n or self.res_slots, self.res_slots)
        self.p.write(self.res_a0, bytes(self.res_slots * self.res_stride))
        self.p.write(self.res_n, bytes(4))
        self.p.write(self.res_arm, n.to_bytes(4, "big"))
        return n

    def res_read(self):
        """[(r3, r4, r5, label)] of the captures made."""
        raw = self.p.read(self.res_a0, self.res_slots * self.res_stride)
        rets = self.p.read(self.res_ret0, self.res_slots * 4)
        out = []
        for i in range(self.res_slots):
            b = raw[i * self.res_stride:(i + 1) * self.res_stride]
            r3, r4, r5 = (be(b[j * 4:j * 4 + 4]) for j in range(3))
            if not r4:
                continue
            lbl = b[12:44].split(bytes(1))[0].decode("ascii",
                                                    "backslashreplace")
            out.append((r3, r4, r5, lbl, be(rets[i * 4:i * 4 + 4])))
        return out

    def get_txt_sample(self):
        """The 64 bytes of the text, copied by the probe at the time of the call.

        Copied into the cave rather than read again at the captured address:
        the game reuses its buffer, and reading it some frames later no
        longer shows what the window received.
        """
        return self.p.read(self.get_txt_b0, 64)

    def write_get_text(self, s):
        """Store our UTF-16BE text and arm the substitution (once)."""
        data = s.encode("utf-16-be")
        if len(data) + 2 > 128:
            raise ValueError(f"{len(s)} units: the buffer holds 63")
        self.p.write(self.get_txt_our, data + bytes(128 - len(data)))
        self.p.write(self.get_txt_req, (1).to_bytes(4, "big"))

    def get_texts(self):
        """[(count, r3, word0, word1)] for the 3 pane text probes."""
        raw = self.p.read(self.get_txt_n0, self.get_txt_n * 16)
        return [tuple(be(raw[i * 16 + j * 4:i * 16 + j * 4 + 4])
                      for j in range(4)) for i in range(self.get_txt_n)]

    def _cols(self, n, *bases):
        cols = []
        for base in bases:
            raw = self.p.read(base, n * 4)
            cols.append([be(raw[i * 4:i * 4 + 4]) for i in range(n)])
        return list(zip(*cols))

    def get_calls(self):
        """[(count, caller, r3, r4, r5, rank)] for bench 1."""
        return self._cols(self.get_n, self.get0, self.get_from0,
                          self.get_this0, self.get_r4_0, self.get_r5_0,
                          self.get_ord0)

    def get_win_calls(self):
        """[(count, caller, r3, r4, r5, rank)] for bench 2."""
        return self._cols(self.get_win_n, self.get_win0, self.get_win_from0,
                          self.get_win_this0, self.get_win_r4_0,
                          self.get_win_r5_0, self.get_win_ord0)

    def tips_probes(self, n=8):
        """Mask and counters of the tip frame probes."""
        mask = be(self.p.read(self.tips_mask, 4))
        raw = self.p.read(self.tips_counts, n * 4)
        return mask, [be(raw[i * 4:i * 4 + 4]) for i in range(n)]

    def tips_reset(self, n=8):
        self.p.write(self.tips_mask, bytes(4))
        self.p.write(self.tips_counts, bytes(n * 4))

    def ms_probes(self, n=6):
        """Mask and counters of the MainScreen probes."""
        mask = be(self.p.read(self.ms_mask, 4))
        raw = self.p.read(self.ms_counts, n * 4)
        return mask, [be(raw[i * 4:i * 4 + 4]) for i in range(n)]

    def ms_reset(self, n=6):
        self.p.write(self.ms_mask, b"\x00" * 4)
        self.p.write(self.ms_counts, b"\x00" * (n * 4))

    def guest(self, host_addr):
        """Guest address of a host address."""
        if self.base is None:
            raise RuntimeError("guest/host base unknown")
        return host_addr - self.base

    def write_text(self, s, encoding="utf-16-be"):
        """Store a string in apText and return its GUEST address.

        The buffer lives in the cave: its address does not move during the
        session, unlike heap objects. That is what lets the game point to it
        durably.
        """
        data = s.encode(encoding)
        term = b"\x00\x00" if "16" in encoding else b"\x00"
        if len(data) + len(term) > 256:
            raise ValueError("text too long for the 256-byte buffer")
        self.p.write(self.text_buf, data + term + b"\x00" * (256 - len(data) - len(term)))
        return self.guest(self.text_buf)

    def write_dlg_text(self, s):
        """Store UTF-16BE text in the dialog window's buffer.

        Returns (guest address, length in UTF-16 units). The length EXCLUDES
        the terminator: measured on the tip frame, holding 101 units for a
        length read as 100.
        """
        data = s.encode("utf-16-be")
        if len(data) + 2 > self.dlg_buf_size:
            raise ValueError(
                f"{len(s)} units: the buffer holds "
                f"{self.dlg_buf_size // 2 - 1}")
        self.p.write(self.dlg_buf,
                     data + bytes(self.dlg_buf_size - len(data)))
        return self.guest(self.dlg_buf), len(s)

    def probes(self, n=9):
        """Mask and counters of the PickUpWin probes."""
        mask = be(self.p.read(self.hook_mask, 4))
        raw = self.p.read(self.hook_counts, n * 4)
        return mask, [be(raw[i * 4:i * 4 + 4]) for i in range(n)]

    def reset_probes(self, n=9):
        self.p.write(self.hook_mask, b"\x00" * 4)
        self.p.write(self.hook_counts, b"\x00" * (n * 4))

    def read(self):
        raw = self.p.read(self.tick, 64)
        if not raw or len(raw) < 64:
            # Cemu went away meanwhile: say it clearly rather than leave a
            # TypeError on None a few lines below.
            raise RuntimeError(
                "Cemu no longer answers (process closed, or game crashed).")
        return dict(tick=be(raw[0:4]), inbox=be(raw[4:8]),
                    outbox=be(raw[8:12]), lastseen=be(raw[12:16]),
                    itemget=be(raw[16:20]), name_ptr=be(raw[20:24]),
                    value=be(raw[24:28]), pmdm_this=be(raw[28:32]),
                    give_req=be(raw[32:36]), give_value=be(raw[36:40]),
                    give_done=be(raw[40:44]), rune_req=be(raw[44:48]),
                    rune_count=be(raw[48:52]), rune_done=be(raw[52:56]),
                    notify_req=be(raw[56:60]), notify_done=be(raw[60:64]))

    def ready(self):
        """Can the notification path REALLY display?

        The injected code increments apNotifyDone even when apListThis is 0
        and it therefore can do nothing: notify() then returned True with
        nothing shown, and whole measurements were taken as valid on that
        basis. The only usable proof is that the row pool is known -- it now
        is WITHOUT a prior pickup: the resolver takes it from screen 0x28
        (PickUpWin) + 0x1b68 every frame.
        """
        return be(self.p.read(self.list_this, 4)) != 0

    def get_duration(self):
        import struct
        return struct.unpack(">f", self.p.read(self.duration, 4))[0]

    def notify(self, actor_name, timeout=3.0, duration=None):
        """Ask the game to show its item obtained banner.

        `duration` replaces the value the game uses (5.0). It is written right
        before the request, because the probe rewrites that field at every
        real pickup: setting it once and for all would not hold.
        """
        import struct
        if not self.ready():
            return False
        raw = actor_name.encode("ascii")
        if len(raw) > 62:
            raise ValueError("name too long for the 64-byte buffer")
        self.p.write(self.name_buf, raw + b"\x00" * (64 - len(raw)))
        if duration is not None:
            self.p.write(self.duration, struct.pack(">f", float(duration)))
        before = self.read()["notify_done"]
        self.p.write(self.notify_req, (1).to_bytes(4, "big"))
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.05)
            if self.read()["notify_done"] != before:
                return True
        return False

    SEL_MAGIC = 0x52534C31  # "RSL1", written by tools/build_rune_selection_sync.py

    def sel_ready(self):
        """Can the loaded patch request a rune selection?

        Same trap as `pf_ready`: on a patch without apCheckSel, these fields
        fall on code and read without error. The magic word decides.
        """
        return be(self.p.read(self.sel_magic, 4)) == self.SEL_MAGIC

    MAP_MAGIC = 0x4D4F5031  # "MOP1", written by tools/build_tower_maps_native.py

    def map_ready(self):
        """Has the loaded patch the map opening's fallback? (the magic word, as sel_ready)"""
        return be(self.p.read(self.map_magic, 4)) == self.MAP_MAGIC

    def set_map_tower(self, index):
        """The tower index (0..14) the next map opening without a tower near its
        actor takes, spent by the game; -1: none. False on a patch without it."""
        if not self.map_ready():
            return False
        return bool(self.p.write(self.map_tower, (int(index) & 0xFFFFFFFF).to_bytes(4, "big")))

    WEATHER_MAGIC = 0x57544831  # "WTH1", written by tools/build_weather_native.py

    def weather_ready(self):
        """Has the loaded patch the weather hold? (the magic word, as map_ready)"""
        return be(self.p.read(self.weather_magic, 4)) == self.WEATHER_MAGIC

    WEATHER_CEILING = 3          # the hook's passes at most, per frame of the world asked

    def force_weather(self, kind, frames):
        """Hold the weather `kind` (0..8) for `frames` frames of the world, and at
        most WEATHER_CEILING times as many passes of the hook; 0 frames gives the
        game its weather back. The type and the ceiling first, then the frames: the
        hook never holds a type not yet written. False on a patch without the hold."""
        if not self.weather_ready():
            return False
        frames = max(int(frames), 0)
        return bool(self.p.write(self.weather_type, (int(kind) & 0xFFFFFFFF).to_bytes(4, "big"))
                    and self.p.write(self.weather_passes,
                                     (frames * self.WEATHER_CEILING).to_bytes(4, "big"))
                    and self.p.write(self.weather_frames, frames.to_bytes(4, "big")))

    def weather_left(self):
        """The world's frames the weather hold still lasts; None on a patch without it."""
        if not self.weather_ready():
            return None
        raw = self.p.read(self.weather_frames, 4)
        return be(raw) if raw and len(raw) == 4 else None

    def request_rune_selection(self, rune_type, timeout=1.0):
        """Have the game call 0x02A2D6D4(*(0x10463798), type).

        Returns True if the call happened, False if the cave refused it (type
        outside the delivered runes, selection object missing), None without
        an answer in time: the request may still go at the next frame. The
        request is only RECORDED: the game's per-frame update applies it
        afterwards (see botw_client/rune_selection.py).
        """
        if not self.sel_ready():
            raise CaveUnavailable(
                "patch without rune selection: CLOSE AND REOPEN CEMU")
        before = be(self.p.read(self.sel_done, 4))
        self.p.write(self.sel_type, int(rune_type).to_bytes(4, "big"))
        self.p.write(self.sel_req, (1).to_bytes(4, "big"))
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.02)
            if be(self.p.read(self.sel_done, 4)) != before:
                return be(self.p.read(self.sel_result, 4)) == 1
        return None

    def count_runes(self, timeout=3.0):
        """Have the game call its own rune counter, and read it."""
        before = self.read()["rune_done"]
        self.p.write(self.rune_req, (1).to_bytes(4, "big"))
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(0.05)
            s = self.read()
            if s["rune_done"] != before:
                return s["rune_count"]
        return None

    def send(self, value):
        return self.p.write(self.inbox, int(value).to_bytes(4, "big"))

    def give(self, actor_name, quantity=1):
        """Ask the injected code to call itemGet."""
        raw = actor_name.encode("ascii")
        if len(raw) > 62:
            raise ValueError("name too long for the 64-byte buffer")
        self.p.write(self.name_buf, raw + b"\x00" * (64 - len(raw)))
        self.p.write(self.give_value, int(quantity).to_bytes(4, "big"))
        return self.p.write(self.give_req, (1).to_bytes(4, "big"))

    def last_item_name(self, name_ptr):
        """Follow the SafeString* captured by the itemGet hook to the string.

        A sead::SafeString here is 8 bytes: {const char* cstr; void* vtable}.
        The actor name is therefore two indirections from the captured pointer.
        """
        if not name_ptr or self.base is None:
            return None
        # the cave lives around 0x01800000, the game's heap at 0x10000000+:
        # accept both, otherwise a name given by ourselves is unreadable
        if not (0x01000000 <= name_ptr < 0x50000000):
            return None
        raw = self.p.read(self.base + name_ptr, 4)
        if not raw:
            return None
        cstr = be(raw)
        if not (0x01000000 <= cstr < 0x50000000):
            return None
        buf = self.p.read(self.base + cstr, 64)
        if not buf:
            return None
        s = buf.split(b"\x00")[0]
        try:
            return s.decode("ascii")
        except UnicodeDecodeError:
            return None


def diagnose():
    """Say WHY the cave is missing instead of listing generic causes.

    Cemu rejects an entire patch file on the first assembler error, so one
    unsupported mnemonic silently removes every hook. That only shows up in the
    log, which is why it is surfaced here rather than left to be found by hand.
    """
    log = log_path()
    if not log.exists():
        print(f"  Cemu log not found ({log})")
        return
    lines = log.read_text(encoding="utf-8", errors="replace").splitlines()

    errs, applied = [], []
    for i, line in enumerate(lines):
        if "BOTW_Archipelago" in line or "BOTW_AP_InjectionTest" in line:
            if "Applying patch group" in line:
                applied.append(line.strip())
            else:
                errs.extend(x.strip() for x in lines[i:i + 3])

    if errs:
        print("  ASSEMBLY ERROR -- Cemu rejected the whole file:")
        for e in errs[:6]:
            print("   ", e)
        print("")
        print("  Fix the faulty instruction, then restart Cemu.")
    elif applied:
        print("  The patch was applied:")
        for a in applied[-2:]:
            print("   ", a)
        print("")
        print("  But the signature is still not found: Cemu may still be")
        print("  running an earlier session. Restart the game.")
    else:
        print("  No trace of the pack in the log.")
        print("  - is it checked in Options > Graphic Packs?")
        print("  - has Cemu been restarted since?")


def main():
    value = int(sys.argv[1]) if len(sys.argv) > 1 else None
    pid = cemu_pid()
    if not pid:
        sys.exit("Cemu is not running")

    with Process(pid, writable=value is not None) as p:
        a = find_cave(p)
        if a is None:
            print("cave not found.")
            print("")
            diagnose()
            return

        base, cave_g, _ = guest_base(p, a - 12)
        c = Cave(p, a, base)
        s = c.read()
        print(f"cave found (version at {a:#014x})")
        if base is not None:
            print(f"  guest cave     = {cave_g:#010x}")
            print(f"  guest->host    = {base:#014x}   (host = guest + base)")
            owner = hook_owner(p, base)
            if owner is None or owner == "no hook":
                print(f"  !! no hook at {HOOK_GUEST:#010x}")
            elif not hook_is_ours(p, base, cave_g, owner):
                print(f"  !! HOOK TAKEN: {HOOK_GUEST:#010x} jumps to {owner:#010x},")
                print("     outside our cave. Another graphic pack patches the same")
                print("     address -- FPS++ does. Disable it: without this hook,")
                print("     the mailbox no longer works.")
        else:
            print("  guest/host base not found")
        print(f"  tick     = {s['tick']}      <- proof of life (per frame)")
        print(f"  inbox    = {s['inbox']}")
        print(f"  outbox   = {s['outbox']}")
        print(f"  lastseen = {s['lastseen']}")
        print("")
        print(f"  itemGet called {s['itemget']} times")
        if s["itemget"]:
            name = c.last_item_name(s["name_ptr"])
            print(f"  last item      = {name if name else '(unreadable name)'}"
                  f"   quantity = {s['value']}")
            print(f"  raw name_ptr   = {s['name_ptr']:#010x}")

        if s["tick"] == 0:
            print("")
            print("  tick at 0: the hook was never reached.")

        # --- the channels' state, SAID rather than left to guess ----------------
        # The error message of a refusing tool is soon forgotten; seeing it
        # here, at every diagnosis, costs one line.
        print("")
        ok, rn, tick = c.resolve_ready()
        if not ok:
            print(f"  pointer resolver: MISSING from the loaded patch "
                  f"(apResolveN={rn}, tick={tick})")
            print("  -> CLOSE AND REOPEN CEMU. Reloading a save is not "
                  "enough.")
        else:
            print(f"  pointer resolver: {rn} passes   screen table = "
                  f"{be(p.read(c.scr_table, 4)):#010x}")
            for name, (ptr, ready) in c.channels().items():
                print(f"    {name:<20} {ptr:#010x}  "
                      f"{'ready' if ready else 'NOT RESOLVED -> will refuse'}")

        if value is None:
            print("")
            print("run again to see tick grow, or pass a value as an argument")
            print("to test the round trip.")
            return

        print("")
        print(f"sending {value} to inbox ...")
        if not c.send(value):
            sys.exit("write refused")
        for _ in range(50):
            time.sleep(0.1)
            s = c.read()
            if s["inbox"] == 0 and s["outbox"] == value:
                print(f"ECHO RECEIVED: outbox={s['outbox']}, inbox reset to {s['inbox']}")
                print("")
                print("The injected code read our message and answered.")
                print("Python -> game -> Python communication works.")
                return
        print(f"no echo after 5 s (inbox={s['inbox']}, outbox={s['outbox']})")


if __name__ == "__main__":
    main()
