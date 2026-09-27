"""Talk to the code injected into BOTW through its code cave.

    python tools/cemu/mailbox.py            # etat : tick, inbox, outbox
    python tools/cemu/mailbox.py 1234       # envoyer 1234 et attendre l'echo

Cemu garde en memoire hote une copie du TEXTE du patch, donc la signature
apparait plusieurs fois. Le vrai cave est celui ou la constante de version suit
la signature : dans les copies de Cemu ce sont des pointeurs hote 64 bits.
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
HOOK_GUEST = 0x031FA97C          # adresse invitee ou notre bla doit se trouver
DEFAULT_LOG = pathlib.Path.home() / "AppData/Roaming/Cemu/log.txt"
LOG = None   # explicit override; otherwise BOTW_CEMU_LOG, read at call time


def log_path():
    """Cemu log to resolve the cave from.

    Read at call time, not at import: this module is imported indirectly (via
    rpx) long before a lab harness sets BOTW_CEMU_LOG, and a path frozen at
    import silently pointed at the original Cemu profile's log, whose stale
    codecave addresses made the guest base unresolvable (9f).
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


PROBE_GUEST = 0x02EB53E4        # entree de PauseMenuDataMgr::itemGet
PROBE_WORD = 0x9421FF98         # stwu r1, -0x68(r1), telle qu'elle est dans le RPX


def guest_base(p, cave_host):
    """Map guest addresses to host ones: host = guest + base.

    La base est validee sur une instruction du RPX qu'aucun pack ne patche, et
    non sur notre propre hook : un autre graphic pack peut s'approprier la meme
    adresse (FPS++ patche 0x031FA97C), et valider sur notre hook ferait alors
    echouer toute la resolution alors que la base est bonne.
    """
    for g in cave_guest_candidates():
        base = cave_host - g
        raw = p.read(base + PROBE_GUEST, 4)
        if raw and len(raw) == 4 and be(raw) == PROBE_WORD:
            return base, g, None
    return None, None, None


def hook_owner(p, base):
    """Notre hook per-frame tient-il toujours, ou un autre pack l'a-t-il pris ?"""
    raw = p.read(base + HOOK_GUEST, 4)
    if not raw or len(raw) < 4:
        return None
    v = be(raw)
    if (v >> 26) != 18 or not ((v >> 1) & 1) or not (v & 1):
        return "aucun hook"
    return v & 0x03FFFFFC


def hook_is_ours(p, base, cave_g, owner):
    """La cible du hook per-frame est-elle bien NOTRE sonde ?

    Une simple fourchette d'adresses ne suffit pas, et la premiere version en
    donnait la preuve : elle acceptait `cave_g + 0x400`, alors que le code du
    cave commence apres ~5,4 Ko de donnees. Notre propre sonde etait donc
    denoncee comme volee a chaque lancement de `mailbox.py`.

    Le test decisif est la signature de la sonde : elle rejoue l'instruction
    d'origine, puis charge la page du cave avec `lis r11, cave_g >> 16` pour
    incrementer le tick. Un autre pack n'a aucune raison d'ecrire cette
    constante-la.
    """
    if not isinstance(owner, int):
        return False
    raw = p.read(base + owner + 4, 4)
    if not raw or len(raw) < 4:
        return False
    return be(raw) == 0x3D600000 | ((cave_g >> 16) & 0xFFFF)


class CaveUnavailable(RuntimeError):
    """Cemu absent, patch inactif, ou base invite/hote irresolvable."""


def open_cave(*, writable=True):
    """Ouvrir le cave : renvoie (Process, Cave). A fermer avec le Process.

        from mailbox import open_cave
        p, c = open_cave()
        with p:
            ...

    Tous les outils refaisaient ce passe-partout a l'identique. Le client
    Archipelago n'a pas a le connaitre : il lui faut un objet Cave, pas la
    procedure de recherche de signature.
    """
    pid = cemu_pid()
    if not pid:
        raise CaveUnavailable("Cemu n'est pas lance")
    p = Process(pid, writable=writable)
    try:
        addr = find_cave(p)
        if addr is None:
            raise CaveUnavailable(
                "code cave introuvable : le graphic pack est-il actif ? "
                "(python tools/cemu/mailbox.py pour le diagnostic)")
        base, _, _ = guest_base(p, addr - 12)
        if base is None:
            raise CaveUnavailable(
                "base invite/hote irresolvable : relancer le jeu")
        return p, Cave(p, addr, base)
    except Exception:
        p.__exit__(None, None, None)
        raise


class Cave:
    """Carte des champs du code cave, tous relatifs au champ de version.

    L'ordre doit rester synchronise avec le bloc de donnees en tete de
    patch_apInject.asm. Un decalage ici ne provoque pas d'erreur : il ecrit
    silencieusement dans le mauvais champ.
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
        self.hook_counts = version_addr + 72      # 9 compteurs consecutifs
        self.pickup_this = version_addr + 108
        self.screen_this = version_addr + 112     # l'ecran PickUpWin
        self.duration = version_addr + 116        # flottant capture au vol
        self.save_f1 = version_addr + 120
        self.list_this = version_addr + 124       # ecran + 0x1b68 : pool de lignes
        self.name_buf = version_addr + 152
        self.text_buf = version_addr + 216       # 256 octets de texte libre
        self.ms_mask = version_addr + 472        # sondes du message central
        self.ms_counts = version_addr + 476      # 6 compteurs consecutifs
        self.ms_this = version_addr + 500
        self.ms1_this = version_addr + 504   # 'this' de la candidate
        self.ms_req = version_addr + 508
        self.ms_index = version_addr + 512
        self.ms_state = version_addr + 516
        self.ms_done = version_addr + 520
        self.ms_queue = version_addr + 524   # garde this+0x150
        self.ms_saveq = version_addr + 528
        self.ms_ret = version_addr + 532     # retour de l'API, 0 = refuse
        self.ms_flag = version_addr + 536    # r4 : booleen, pas un index
        self.ms_pass = version_addr + 540    # atteint l'empilement
        self.ms_bail = version_addr + 544    # sortie anticipee
        self.ms_mid = version_addr + 552     # apres les 3 premiers tests
        self.ms_dbg8c = version_addr + 556   # 0x8c vu par la fonction
        self.ms_dbg154 = version_addr + 560  # releves par le cave, dans la
        self.ms_dbg150 = version_addr + 564  # meme frame que l'appel
        self.ms_dbgc = version_addr + 568
        self.push_this = version_addr + 572  # args releves sur l'empilement
        self.push_a = version_addr + 576
        self.push_b = version_addr + 580
        self.push_n = version_addr + 584
        self.play_a = version_addr + 588    # valeurs a rejouer
        self.play_b = version_addr + 592
        self.play_req = version_addr + 596
        self.play_done = version_addr + 600
        self.msg_cstr = version_addr + 604   # SafeString a nous
        self.play_raw = version_addr + 612   # 1 = rejouer le pointeur du jeu
        # --- cadre bleu des conseils (MessageTipsRunTime_00) ---
        self.tips_mask = version_addr + 616
        self.tips_counts = version_addr + 620     # 8 compteurs consecutifs
        self.tips_this = version_addr + 652       # widget, vu par image
        self.tips_show_this = version_addr + 656  # this vu a l'affichage reel
        self.tips_show_idx = version_addr + 660   # index demande par le jeu
        self.tips_req = version_addr + 664
        self.tips_index = version_addr + 668
        self.tips_done = version_addr + 672
        self.tips_text_req = version_addr + 676
        self.tips_text_len = version_addr + 680
        self.tips_text_done = version_addr + 684
        self.tips_spy_ptr = version_addr + 688    # objet texte du jeu : mot 0
        self.tips_spy_len = version_addr + 692    # et mot 1
        self.pane_cstr = version_addr + 696
        self.tips_str_ptr = version_addr + 704
        # --- traceur des resolutions de message (0x03a38ad0) ---
        self.ring_left = version_addr + 712   # quota restant
        self.ring_ptr = version_addr + 716    # ou ecrire, adresse INVITEE
        # --- fenetre de dialogue (Message_00 / MessageSp_00) ---
        self.dlg_open_n = version_addr + 720   # appels vus de 0x035ff8fc
        self.dlg_open0_n = version_addr + 724  # ... dont a drapeau NUL
        self.dlg_set_n = version_addr + 728    # appels vus de 0x035fb5f8
        self.dlg_this = version_addr + 732     # la fenetre ; son +0x1d0 porte
        self.dlg_seen_arc = version_addr + 736 # le texte { ptr, longueur }
        self.dlg_seen_lbl = version_addr + 740
        self.dlg_arg6 = version_addr + 744     # arguments releves sur un vrai
        self.dlg_arg7 = version_addr + 748     # appel, pour etre rejoues
        self.dlg_arg8 = version_addr + 752
        self.dlg_req = version_addr + 756
        self.dlg_done = version_addr + 760
        self.dlg_text_req = version_addr + 764
        self.dlg_text_done = version_addr + 768
        self.dlg_str_ptr = version_addr + 772
        self.dlg_str_len = version_addr + 776
        self.arc_buf = version_addr + 796      # 64 octets, ASCII
        self.lbl_buf = version_addr + 860      # 32 octets, ASCII
        self.ring = version_addr + 892         # 48 entrees { site, libelle }
        self.ring_n = 48
        self.dlg_buf = version_addr + 1276     # 4096 octets = 2048 unites
        self.dlg_buf_size = 4096
        # --- interception des ramassages (itemGet) ---
        self.ig_left = version_addr + 5372     # quota du journal
        self.ig_ptr = version_addr + 5376      # ou ecrire, adresse INVITEE
        self.block_req = version_addr + 5380   # 1 = neutraliser le prochain
        self.block_done = version_addr + 5384
        self.grant_mark = version_addr + 5388  # 1 = objet ACCORDE en cours
        self.block_grants = version_addr + 5392  # neutraliser tous les accordes

        # Banc de sondes de la fenetre d'obtention d'objet (MessageGet_00) :
        # 19 compteurs contigus, un par fonction de 0x02fcf29c a 0x02fd33e0.
        # Ajoutes en FIN de bloc pour ne decaler aucun champ existant.
        self.get0 = version_addr + 5828
        self.get_n = 19
        self.get_from0 = version_addr + 5904   # adresse de retour
        self.get_this0 = version_addr + 5980   # r3
        self.get_r4_0 = version_addr + 6056    # r4
        self.get_r5_0 = version_addr + 6132    # r5
        self.get_seq = version_addr + 6208     # compteur d'ordre partage
        self.get_ord0 = version_addr + 6212    # rang, banc 1

        # Banc 2 : la classe gestionnaire, 13 fonctions de 0x03606ad0 a
        # 0x03607560. C'est la que vit l'API appelable de la fenetre.
        self.get_win0 = version_addr + 6288
        self.get_win_n = 13
        self.get_win_from0 = version_addr + 6340
        self.get_win_this0 = version_addr + 6392
        self.get_win_r4_0 = version_addr + 6444
        self.get_win_r5_0 = version_addr + 6496
        self.get_win_ord0 = version_addr + 6548

        # Le pilote 0x03a3ec0c : ses sept arguments releves sur un vrai
        # declenchement, et le rejeu avec notre propre chaine a la place
        # de r6.
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
        self.get_drv_name = version_addr + 6644   # 64 octets

        # Capture FILTREE : ne vaut que pour MessageGet_00, figee par la sonde
        # apGetProbe1 que seul cet ecran traverse. Les champs get_drv_* ci-
        # dessus valent pour le dernier ecran ouvert, quel qu'il soit.
        self.get_win_ok = version_addr + 6708
        self.get_win_cthis = version_addr + 6712
        self.get_win_ca4 = version_addr + 6716
        self.get_win_ca5 = version_addr + 6720
        self.get_win_ca6 = version_addr + 6724
        self.get_win_ca7 = version_addr + 6728
        self.get_win_ca8 = version_addr + 6732
        self.get_win_ca9 = version_addr + 6736

        # Trois sondes du texte des panneaux : { compte, r3, mot0, mot1 }.
        self.get_txt_n0 = version_addr + 6740
        self.get_txt_n = 3
        self.get_txt_req = version_addr + 6792
        self.get_txt_done = version_addr + 6796
        self.get_txt_b0 = version_addr + 6800    # 64 octets recopies
        self.get_txt_our = version_addr + 6864   # 128 octets = 64 unites

        # Sonde de l'entree du resolveur commun 0x03082c70. Quatre captures
        # successives apres armement, 44 octets chacune :
        # { r3, r4, r5, 32 octets du libelle pointe par *(r4) }.
        self.res_arm = version_addr + 6992
        self.res_n = version_addr + 6996
        self.res_a0 = version_addr + 7004
        self.res_slots = 4
        self.res_stride = 44
        self.res_ret0 = version_addr + 7180    # adresse de retour, par creneau

        # Substitution du nom d'objet a 0x030835c8, ou r3 est le texte resolu.
        self.sub_n = version_addr + 7196
        self.sub_out = version_addr + 7200
        self.sub_w0 = version_addr + 7204      # 4 mots de l'objet renvoye
        self.sub_req = version_addr + 7220
        self.sub_done = version_addr + 7224
        self.sub_out_buf = version_addr + 7236  # r29 : la VRAIE sortie
        self.sub_o0 = version_addr + 7240       # 8 mots de cette sortie
        self.sub_len = version_addr + 7232      # notre objet, 4 mots
        self.sub_buf = version_addr + 7288      # notre texte, 256 octets

        # Meme mecanisme pour la description, site 0x03083860.
        self.sub_desc_n = version_addr + 7544
        self.sub_desc_req = version_addr + 7548
        self.sub_desc_done = version_addr + 7552
        self.sub_desc_len = version_addr + 7556
        self.sub_desc_buf = version_addr + 7560   # 512 octets = 256 unites
        self.sub_auto = version_addr + 8072      # compte d'objets accordes
        self.sub_auto_n = version_addr + 8076    # resolutions par objet

        # Ouvrir la fenetre nous-memes : les six registres du vrai site, et
        # le rejeu des DEUX appels enchaines (fabrique puis ouverture).
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
        # Capture filtree : ne vaut que pour MessageGet_00. La sonde brute se
        # declenche a chaque ouverture d'ecran, 40 fois par partie.
        self.opn_ok = version_addr + 8120
        self.opn_c24 = version_addr + 8124
        self.opn_c25 = version_addr + 8128
        self.opn_c26 = version_addr + 8132
        self.opn_c27 = version_addr + 8136
        self.opn_c28 = version_addr + 8140
        self.opn_c31 = version_addr + 8144
        # r1 releve a trois endroits, pour savoir s'il y a plusieurs piles.
        self.r1_frame = version_addr + 8148
        self.r1_ui = version_addr + 8152
        self.r1_name = version_addr + 8156
        self.r1_opn = version_addr + 8160
        self.opn_step = version_addr + 8164   # 1 = fabrique seule, 2 = tout
        self.opn_phase = version_addr + 8168  # jusqu'ou le rejeu est alle
        self.opn_r3 = version_addr + 8172     # ce que la fabrique a rendu
        self.opn_heap = version_addr + 8308   # 0 = tas courant (recommande)
        self.opn_mode = version_addr + 8312   # 0 = fabrique, 1 = trampoline, 2 = englobante
        self.opn_ctx_on = version_addr + 8316  # 0 = ne PAS recopier le tas mort
        self.opn_arg4 = version_addr + 8320    # r30, argument 2 de 0x03a42b94
        # D'ou vient un tas vivant : sonde du getter 0x030aa1ac.
        self.heap_req = version_addr + 8324
        self.heap_n = version_addr + 8328
        self.heap_root = version_addr + 8332   # *(0x1046C8B0)
        self.heap_mgr = version_addr + 8336    # *(0x1046C920)
        self.heap_fb = version_addr + 8340     # *(root + 4), repli statique
        self.heap_cur = version_addr + 8344    # ce que 0x030aa1ac a rendu
        # Le prologue de 0x03a42b94 : six arguments + l'appelant.
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
        # L'etage au-dessus : 0x030806f0, qui appelle 0x03a42b94 puis
        # enchaine la mise en scene.
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
        self.opn_anim = version_addr + 8476   # jouer l'animation "open"
        self.opn_varg = version_addr + 8480   # le mode passe a vtable[0x1a4]
        # Registre a decalage de la mise en scene 0x03a40d20(ecran, mode).
        # Le sommet de la chaine : 0x02b769c4(r3, r4), l'objet accorde.
        self.grant_r3 = version_addr + 8484
        self.grant_r4 = version_addr + 8488
        self.grant_lr = version_addr + 8492
        # La copie de la structure de pile que 0x02b769c4 recoit en r4.
        self.grant_buf_ptr = version_addr + 8496
        # La diffusion 0x032bc730(dispatcher, nomObjet).
        self.disp_n = version_addr + 8500
        self.disp_r3 = version_addr + 8504
        self.disp_r4 = version_addr + 8508
        self.disp_lr = version_addr + 8512
        self.grant_name = version_addr + 8516
        self.disp_arg = version_addr + 8520      # le dispatcher, MESURE
        # L'invocateur generique : Python range une adresse et huit
        # arguments, le cave saute. Plus aucune experience d'appel ne
        # demande de modifier le patch.
        self.call_addr = version_addr + 8524
        self.call_a1 = version_addr + 8528       # 8 arguments consecutifs
        self.call_ret = version_addr + 8560
        self.call_n = version_addr + 8564
        # Le MEME invocateur, mais sur le hook per-frame : celui-la tourne
        # depuis le demarrage du jeu, sans prerequis. L'autre vit dans le
        # pilote de MessageGet_00 et reste muet tant que la vraie fenetre n'a
        # pas ete vue -- en laissant la requete en attente, qui partait alors
        # au prochain vrai coffre. Partage apCallAddr / apCallA1..A8.
        self.pf_req = version_addr + 9260
        # Le resolveur de pointeurs de canaux, sur le meme hook per-frame :
        # il reecrit pmdm_this / screen_this / list_this / ms1_this /
        # push_this / dlg_this a chaque image depuis les globales du jeu, au
        # lieu d'attendre qu'une sonde les voie passer.
        self.resolve_n = version_addr + 9264     # passages -- garde-fou
        self.scr_table = version_addr + 9268     # table d'ecrans, 0 = IHM absente
        # Selection de rune demandee au jeu (apCheckSel), en fin de bloc.
        # Absents des patchs anterieurs : sel_ready() le verifie.
        self.sel_magic = version_addr + 9272
        self.sel_req = version_addr + 9276
        self.sel_type = version_addr + 9280
        self.sel_done = version_addr + 9284
        self.sel_result = version_addr + 9288
        # Les douze niveaux de la chaine d'appel, sondes d'un coup.
        # Chaque niveau : N, r3, r4, r5, r6, r7, Lr -- 7 mots.
        self.lvl0 = version_addr + 8568
        self.lvl_mots = 7
        self.lvl_ids = (0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 13)
        # La chaine d'appel complete, deroulee depuis le cadre du grant.
        # La chaine d'appel de la FENETRE, deroulee sur la creation de
        # l'ecran. C'est celle qu'on veut : le deroulage du don d'objet
        # menait a l'attribution, pas a l'affichage.
        # Le maintien de la fenetre, une fois par image dans le cave.
        # Compte d'images, pas booleen : un client mort laisse le jeu revenir
        # a la normale tout seul.
        self.hold_n = version_addr + 8904
        self.hold_q = version_addr + 8908        # 0 = ne pas toucher a +0x44
        self.wstk_f = version_addr + 8912
        self.wstk_l0 = version_addr + 8916
        self.stk_f = version_addr + 8972
        self.stk_l0 = version_addr + 8976        # 14 adresses de retour
        self.stk_n = 14
        self.grant_buf = version_addr + 9032     # 32 mots
        self.show_n = version_addr + 9160
        self.show_t0 = version_addr + 9164
        self.show_m0 = version_addr + 9196
        self.show_l0 = version_addr + 9228
        self.grant_n = version_addr + 5396     # passages dans 0x02b769c4
        self.ig_ring = version_addr + 5400     # 32 entrees de 12 octets
        self.ig_ring_n = 32

    def ig_arm(self, n=None):
        """Armer le journal des ramassages."""
        n = min(n or self.ig_ring_n, self.ig_ring_n)
        self.p.write(self.ig_ring, bytes(self.ig_ring_n * 12))
        self.p.write(self.ig_ptr, self.guest(self.ig_ring).to_bytes(4, "big"))
        self.p.write(self.ig_left, n.to_bytes(4, "big"))
        return n

    def ig_read(self):
        """[(site d'appel, cstr du nom, quantite)] deja enregistres."""
        left = be(self.p.read(self.ig_left, 4))
        used = self.ig_ring_n - left
        raw = self.p.read(self.ig_ring, used * 12) if used else b""
        return [(be(raw[i * 12:i * 12 + 4]),
                 be(raw[i * 12 + 4:i * 12 + 8]),
                 be(raw[i * 12 + 8:i * 12 + 12]))
                for i in range(used)]

    def ring_arm(self, n=None):
        """Armer le traceur : il enregistrera les n prochaines resolutions.

        Le pointeur est une adresse invitee -- c'est le code injecte qui ecrit
        dedans, pas nous.
        """
        n = min(n or self.ring_n, self.ring_n)
        self.p.write(self.ring, bytes(self.ring_n * 8))
        self.p.write(self.ring_ptr, self.guest(self.ring).to_bytes(4, "big"))
        self.p.write(self.ring_left, n.to_bytes(4, "big"))
        return n

    def ring_read(self):
        """[(site d'appel, adresse invitee du libelle)] deja enregistrees.

        `ring_left` seul ne suffit pas a dire combien d'entrees sont ecrites :
        au sortir d'un lancement du jeu il vaut 0, exactement comme lorsque le
        quota est epuise, et `ring_n - 0` faisait alors passer 48 lignes vides
        pour 48 resolutions. Le pointeur d'ecriture tranche : le code injecte
        ne le renseigne jamais de lui-meme, seul `ring_arm` le pose.
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
        """Lire une chaine C a une adresse invitee.

        Le decodage est en "backslashreplace" et non "replace" : la console
        Windows est en cp1252 et ne sait pas ecrire le U+FFFD que produit
        "replace". Le journal des messages plantait donc au premier libelle
        non ASCII -- juste apres avoir affiche les lignes utiles.
        """
        if not guest_addr or self.base is None:
            return None
        raw = self.p.read(guest_addr + self.base, n)
        if not raw:
            return None
        return raw.split(b"\x00")[0].decode("ascii", "backslashreplace")

    def get_probes(self):
        """Compteurs des 19 sondes de la fenetre d'obtention d'objet."""
        raw = self.p.read(self.get0, self.get_n * 4)
        return [be(raw[i * 4:i * 4 + 4]) for i in range(self.get_n)]

    def get_reset(self):
        """Remettre le banc a zero, juste avant de declencher."""
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
        """(compte, sortie, [4 mots de l'objet renvoye ou None]).

        Les quatre mots viennent de 0x60(r1), le tampon de sortie que
        l'appelant passe au resolveur -- et non de *(r3), qui vaut 0 au retour
        et faisait planter le jeu.
        """
        n = be(self.p.read(self.sub_n, 4))
        out = be(self.p.read(self.sub_out, 4))
        raw = self.p.read(self.sub_w0, 16)
        mots = ([be(raw[i * 4:i * 4 + 4]) for i in range(4)]
                if raw and len(raw) == 16 else None)
        raw2 = self.p.read(self.sub_o0, 32)
        sortie = ([be(raw2[i * 4:i * 4 + 4]) for i in range(8)]
                  if raw2 and len(raw2) == 32 else None)
        return n, out, mots, be(self.p.read(self.sub_out_buf, 4)), sortie

    def open_item_window(self, titre=None, description=None, step=2):
        """Ouvrir la fenetre d'obtention d'objet, sans objet.

        Rejoue les DEUX appels du vrai site : la fabrique qui produit l'objet
        ecran, puis la case 0x4c de sa vtable qui l'ouvre. Ne rejouer que le
        second -- ce que faisait `getwin.py --open` -- plantait le jeu trois
        fois sur trois.

        Prerequis : avoir vu la vraie fenetre une fois depuis le lancement du
        jeu, pour que les six registres du site soient captures.
        """
        if not be(self.p.read(self.opn_ok, 4)):
            raise RuntimeError("MessageGet_00 n'a pas ete vu s'ouvrir depuis "
                               "le lancement : ouvre un vrai coffre une fois")
        self.p.write(self.opn_step, step.to_bytes(4, "big"))
        if titre is not None:
            self.sub_write(titre, 2)
        if description is not None:
            self.sub_write_desc(description, 2)
        self.p.write(self.opn_phase, bytes(4))
        self.p.write(self.opn_req, (1).to_bytes(4, "big"))

    def heap_probe(self):
        """Demander la sonde du tas courant, sur le fil de l'IHM.

        Rend (n, root, mgr, fb, cur) apres coup. La sonde s'execute a la
        prochaine image dans apGetWinProbe6 -- le seul point instrumente qui
        tourne sur la bonne famille de pile.
        """
        self.p.write(self.heap_req, (1).to_bytes(4, "big"))

    def heap_state(self):
        return tuple(be(self.p.read(a, 4)) for a in
                     (self.heap_n, self.heap_root, self.heap_mgr,
                      self.heap_fb, self.heap_cur))

    def levels(self):
        """[(niveau, appels, [r3..r7], lr)] pour les douze etages sondes."""
        out = []
        for k, niv in enumerate(self.lvl_ids):
            b = self.lvl0 + k * self.lvl_mots * 4
            mots = [be(self.p.read(b + i * 4, 4))
                    for i in range(self.lvl_mots)]
            out.append((niv, mots[0], mots[1:6], mots[6]))
        return out

    def call(self, addr, *args):
        """Appeler n'importe quoi depuis le fil d'IHM. Jusqu'a 8 arguments.

        Aucune verification ici : c'est a l'appelant de lire la memoire et de
        s'assurer que ce qu'il passe tient. Le cave ne garde que le saut.
        """
        self.p.write(self.call_addr, addr.to_bytes(4, "big"))
        for i in range(8):
            v = args[i] if i < len(args) else 0
            self.p.write(self.call_a1 + i * 4, (v & 0xFFFFFFFF).to_bytes(4, "big"))
        self.p.write(self.opn_mode, (8).to_bytes(4, "big"))
        self.p.write(self.opn_phase, bytes(4))
        self.p.write(self.opn_req, (1).to_bytes(4, "big"))

    def pf_ready(self):
        """Le patch charge connait-il apPfReq ?

        GARDE-FOU du piege 4 bis : un champ ajoute en fin de bloc tombe sur du
        CODE tant que Cemu n'a pas ete relance, et se lit sans erreur. Le champ
        est un drapeau : il ne peut valoir que 0 ou 1. Toute autre valeur
        signifie que le patch en memoire est perime.
        """
        return be(self.p.read(self.pf_req, 4)) in (0, 1)

    def resolve_ready(self):
        """Le patch charge connait-il le resolveur de pointeurs ?

        MEME GARDE-FOU que `pf_ready`, avec l'invariant qui a deja servi dans
        `getprobe.py` : un compteur incremente une fois par image ne peut pas
        depasser le nombre d'images ecoulees. Sur un patch perime le champ
        tombe sur du code et se lit sans erreur -- mais il vaut alors un mot
        d'instruction, tres au-dessus du tick.

        Rend (pret, resolve_n, tick) pour que l'appelant puisse le DIRE.
        """
        n = be(self.p.read(self.resolve_n, 4))
        tick = be(self.p.read(self.tick, 4))
        return (0 < n <= tick), n, tick

    def ui_ready(self):
        """L'IHM du jeu est-elle construite ? (table d'ecrans resolue)

        C'est le seul prerequis qui reste, et il n'a rien de notre fait : les
        fonctions d'affichage dereferencent le gestionnaire d'ecrans sans le
        tester. Il tombe de lui-meme des qu'une sauvegarde est chargee.
        """
        ok, _, _ = self.resolve_ready()
        return ok and be(self.p.read(self.scr_table, 4)) != 0

    def channels(self):
        """Etat des quatre canaux d'affichage, pour le dire au demarrage.

        {nom: (pointeur, pret)}. Le client Archipelago doit l'afficher : un
        canal muet sans explication est la cause d'erreur numero un.
        """
        champs = (("give / itemGet", self.pmdm_this),
                  ("notification", self.list_this),
                  ("message central", self.ms1_this),
                  ("boite de dialogue", self.scr_table))
        out = {}
        for nom, addr in champs:
            v = be(self.p.read(addr, 4))
            out[nom] = (v, v != 0)
        return out

    def call_pf(self, addr, *args):
        """Idem `call`, mais depuis le hook PER-FRAME.

        Aucun prerequis : ce hook tourne depuis le demarrage du jeu, la ou
        `call` dort tant que MessageGet_00 n'a pas ete vu. Meme protocole,
        memes champs d'arguments, meme compteur `call_n`.

        Reserve : le patch documente une affinite de thread pour le REJEU du
        site d'ouverture -- pile 0x12b3c510 la-bas, 0x0e201270 ici, quatre
        plantages a la cle. Elle valait pour les modes qui manipulent
        l'interieur d'un ecran ; pour un appel propre elle reste a mesurer.
        """
        if not self.pf_ready():
            raise RuntimeError(
                "apPfReq lit une valeur impossible : le patch charge est "
                "PERIME. Fermer et rouvrir Cemu (recharger une sauvegarde ne "
                "suffit pas).")
        self.p.write(self.call_addr, addr.to_bytes(4, "big"))
        for i in range(8):
            v = args[i] if i < len(args) else 0
            self.p.write(self.call_a1 + i * 4, (v & 0xFFFFFFFF).to_bytes(4, "big"))
        self.p.write(self.pf_req, (1).to_bytes(4, "big"))

    def call_stack(self, fenetre=False):
        """Adresses de retour : chaine du don d'objet, ou de la FENETRE."""
        base = self.wstk_l0 if fenetre else self.stk_l0
        return [be(self.p.read(base + i * 4, 4))
                for i in range(self.stk_n)]

    def show_ring(self):
        """Les 8 derniers appels de 0x03a40d20 : (ecran, mode, appelant).

        La sonde ne filtre pas -- 0x03a40d20 sert 94 classes -- donc c'est
        ici qu'on reconnait le notre. Entree 0 = la plus recente.
        """
        n = be(self.p.read(self.show_n, 4))
        out = []
        for i in range(8):
            out.append((be(self.p.read(self.show_t0 + i * 4, 4)),
                        be(self.p.read(self.show_m0 + i * 4, 4)),
                        be(self.p.read(self.show_l0 + i * 4, 4))))
        return n, out

    def upper_args(self):
        """Les cinq arguments de 0x030806f0 pour MessageGet_00, et l'appelant."""
        champs = (self.upc_ok, self.up_lr, self.upc_a1, self.upc_a2,
                  self.upc_a3, self.upc_a4, self.upc_a5)
        ok, lr, *args = [be(self.p.read(a, 4)) for a in champs]
        return ok, lr, args

    def open_prologue(self):
        """Les six arguments de 0x03a42b94 pour MessageGet_00, et l'appelant.

        Capture figee par apGetProbe1 : elle ne vaut que si le compte rendu
        est non nul, sinon la vraie fenetre n'a pas ete vue s'ouvrir.
        """
        champs = (self.opn_prc_ok, self.opn_prc_lr, self.opn_prc_r1,
                  self.opn_prc_a1, self.opn_prc_a2, self.opn_prc_a3,
                  self.opn_prc_a4, self.opn_prc_a5, self.opn_prc_a6)
        ok, lr, r1, *args = [be(self.p.read(a, 4)) for a in champs]
        return ok, lr, r1, args

    def open_state(self):
        """(captures brutes, rejeux, captures filtrees MessageGet_00)."""
        return (be(self.p.read(self.opn_n, 4)),
                be(self.p.read(self.opn_done, 4)),
                be(self.p.read(self.opn_ok, 4)))

    def arm_next_grant(self, titre, description=None, n=2):
        """Substituer le texte du PROCHAIN objet accorde -- coffre, Korogu,
        sanctuaire, cadeau de PNJ.

        C'est la forme a utiliser dans un client Archipelago. Elle differe de
        `show_item_text` sur le seul point qui compte : c'est le CAVE qui
        choisit l'instant, sur la sonde des objets accordes, pas nous.

        Pourquoi ca compte : le site qui resout le nom est generique -- il
        sert aussi a l'inventaire. Armer a la main puis ouvrir son sac
        detourne le nom de l'objet regarde. Mesure en jeu. Ici la
        substitution ne s'arme qu'a l'instant d'un objet accorde, donc jamais
        pendant une consultation.
        """
        self.sub_write(titre, 0)
        if description is not None:
            self.sub_write_desc(description, 0)
        self.p.write(self.sub_auto_n, n.to_bytes(4, "big"))
        self.p.write(self.sub_auto, (1).to_bytes(4, "big"))

    def show_item_text(self, titre, description=None, n=2):
        """Prototype: publish text for n resolutions, without request identity.

        The legacy hook is global. EventFlow callers must verify the Item_AP
        gates before using this primitive. A quota does not expire on its own
        if the companion disappears. This is not a production delivery API.
        """
        # Validate both strings before publishing either quota. This prevents
        # an invalid description from leaving the title armed on its own.
        self._sub_payload(titre, 256, n)
        if description is not None:
            self._sub_payload(description, 512, n)
        self.sub_write(titre, n)
        if description is not None:
            self.sub_write_desc(description, n)

    def sub_write_desc(self, s, n=2):
        """Idem pour la description, site 0x03083860."""
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
            raise ValueError(f"{units} unites : le tampon en tient {size // 2 - 1}")
        return data + bytes(size - len(data)), units.to_bytes(4, "big"), n.to_bytes(4, "big")

    def sub_disarm(self):
        """Tout desarmer : la fenetre suivante redevient normale."""
        self.p.write(self.sub_req, bytes(4))
        self.p.write(self.sub_desc_req, bytes(4))
        self.p.write(self.sub_auto, bytes(4))

    def sub_state(self):
        """(titre_arme, titre_pose, desc_armee, desc_posee, auto)."""
        return (be(self.p.read(self.sub_req, 4)),
                be(self.p.read(self.sub_done, 4)),
                be(self.p.read(self.sub_desc_req, 4)),
                be(self.p.read(self.sub_desc_done, 4)),
                be(self.p.read(self.sub_auto, 4)))

    def sub_write(self, s, n=2):
        """Poser notre texte, et armer la substitution pour n resolutions.

        La sortie du resolveur est le couple { const char16_t*, longueur en
        unites }, mesure { 0x21c541ec, 17 } pour 'Opale brute'. La longueur
        EXCLUT le terminateur, comme partout ailleurs dans ce jeu.

        n vaut 2 par defaut : la construction de la fenetre resout _Name deux
        fois, et ne substituer qu'une seule des deux laisserait le vrai nom
        reapparaitre.
        """
        data, length, quota = self._sub_payload(s, 256, n)
        self.p.write(self.sub_buf, data)
        self.p.write(self.sub_len, length)
        self.p.write(self.sub_req, quota)

    def res_arm_now(self, n=None):
        """Armer la capture des n prochaines resolutions (4 au plus)."""
        n = min(n or self.res_slots, self.res_slots)
        self.p.write(self.res_a0, bytes(self.res_slots * self.res_stride))
        self.p.write(self.res_n, bytes(4))
        self.p.write(self.res_arm, n.to_bytes(4, "big"))
        return n

    def res_read(self):
        """[(r3, r4, r5, libelle)] des captures faites."""
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
        """Les 64 octets du texte, recopies par la sonde au moment de l'appel.

        Recopies dans le cave plutot que relus a l'adresse capturee : le
        tampon du jeu est reutilise, et le lire quelques images plus tard ne
        montre plus ce que la fenetre a recu.
        """
        return self.p.read(self.get_txt_b0, 64)

    def write_get_text(self, s):
        """Poser notre texte UTF-16BE et armer la substitution (un coup)."""
        data = s.encode("utf-16-be")
        if len(data) + 2 > 128:
            raise ValueError(f"{len(s)} unites : le tampon en tient 63")
        self.p.write(self.get_txt_our, data + bytes(128 - len(data)))
        self.p.write(self.get_txt_req, (1).to_bytes(4, "big"))

    def get_texts(self):
        """[(compte, r3, mot0, mot1)] pour les 3 sondes de texte de pane."""
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
        """[(compte, appelant, r3, r4, r5, rang)] pour le banc 1."""
        return self._cols(self.get_n, self.get0, self.get_from0,
                          self.get_this0, self.get_r4_0, self.get_r5_0,
                          self.get_ord0)

    def get_win_calls(self):
        """[(compte, appelant, r3, r4, r5, rang)] pour le banc 2."""
        return self._cols(self.get_win_n, self.get_win0, self.get_win_from0,
                          self.get_win_this0, self.get_win_r4_0,
                          self.get_win_r5_0, self.get_win_ord0)

    def tips_probes(self, n=8):
        """Masque et compteurs des sondes du cadre des conseils."""
        mask = be(self.p.read(self.tips_mask, 4))
        raw = self.p.read(self.tips_counts, n * 4)
        return mask, [be(raw[i * 4:i * 4 + 4]) for i in range(n)]

    def tips_reset(self, n=8):
        self.p.write(self.tips_mask, bytes(4))
        self.p.write(self.tips_counts, bytes(n * 4))

    def ms_probes(self, n=6):
        """Masque et compteurs des sondes MainScreen."""
        mask = be(self.p.read(self.ms_mask, 4))
        raw = self.p.read(self.ms_counts, n * 4)
        return mask, [be(raw[i * 4:i * 4 + 4]) for i in range(n)]

    def ms_reset(self, n=6):
        self.p.write(self.ms_mask, b"\x00" * 4)
        self.p.write(self.ms_counts, b"\x00" * (n * 4))

    def guest(self, host_addr):
        """Adresse invitee correspondant a une adresse hote."""
        if self.base is None:
            raise RuntimeError("base invite/hote inconnue")
        return host_addr - self.base

    def write_text(self, s, encoding="utf-16-be"):
        """Poser une chaine dans apText et renvoyer son adresse INVITEE.

        Le tampon vit dans le cave : son adresse ne bouge pas de la session,
        contrairement aux objets du tas. C'est ce qui permet d'y faire pointer
        le jeu durablement.
        """
        data = s.encode(encoding)
        term = b"\x00\x00" if "16" in encoding else b"\x00"
        if len(data) + len(term) > 256:
            raise ValueError("texte trop long pour le tampon de 256 octets")
        self.p.write(self.text_buf, data + term + b"\x00" * (256 - len(data) - len(term)))
        return self.guest(self.text_buf)

    def write_dlg_text(self, s):
        """Poser du texte UTF-16BE dans le tampon de la fenetre de dialogue.

        Renvoie (adresse invitee, longueur en unites UTF-16). La longueur
        EXCLUT le terminateur : mesure faite sur le cadre des conseils, porteur
        de 101 unites pour une longueur relevee de 100.
        """
        data = s.encode("utf-16-be")
        if len(data) + 2 > self.dlg_buf_size:
            raise ValueError(
                f"{len(s)} unites : le tampon en tient "
                f"{self.dlg_buf_size // 2 - 1}")
        self.p.write(self.dlg_buf,
                     data + bytes(self.dlg_buf_size - len(data)))
        return self.guest(self.dlg_buf), len(s)

    def probes(self, n=9):
        """Masque et compteurs des sondes PickUpWin."""
        mask = be(self.p.read(self.hook_mask, 4))
        raw = self.p.read(self.hook_counts, n * 4)
        return mask, [be(raw[i * 4:i * 4 + 4]) for i in range(n)]

    def reset_probes(self, n=9):
        self.p.write(self.hook_mask, b"\x00" * 4)
        self.p.write(self.hook_counts, b"\x00" * (n * 4))

    def read(self):
        raw = self.p.read(self.tick, 64)
        if not raw or len(raw) < 64:
            # Cemu a disparu en cours de route : le dire clairement plutot que
            # de laisser un TypeError sur du None quelques lignes plus bas.
            raise RuntimeError(
                "Cemu ne repond plus (processus ferme, ou jeu plante).")
        return dict(tick=be(raw[0:4]), inbox=be(raw[4:8]),
                    outbox=be(raw[8:12]), lastseen=be(raw[12:16]),
                    itemget=be(raw[16:20]), name_ptr=be(raw[20:24]),
                    value=be(raw[24:28]), pmdm_this=be(raw[28:32]),
                    give_req=be(raw[32:36]), give_value=be(raw[36:40]),
                    give_done=be(raw[40:44]), rune_req=be(raw[44:48]),
                    rune_count=be(raw[48:52]), rune_done=be(raw[52:56]),
                    notify_req=be(raw[56:60]), notify_done=be(raw[60:64]))

    def ready(self):
        """Le chemin de notification peut-il REELLEMENT afficher ?

        Le code injecte incremente apNotifyDone meme quand apListThis vaut 0 et
        qu'il ne peut donc rien faire : notify() renvoyait alors True sans que
        rien ne s'affiche, et des mesures entieres ont ete prises pour valides
        sur cette base. La seule preuve utilisable est que le pool de lignes
        soit connu -- il l'est desormais SANS ramassage prealable : le
        resolveur le tire de l'ecran 0x28 (PickUpWin) + 0x1b68 a chaque image.
        """
        return be(self.p.read(self.list_this, 4)) != 0

    def get_duration(self):
        import struct
        return struct.unpack(">f", self.p.read(self.duration, 4))[0]

    def notify(self, actor_name, timeout=3.0, duration=None):
        """Demander au jeu d'afficher son bandeau d'objet obtenu.

        `duration` remplace la valeur que le jeu emploie (5.0). Elle est ecrite
        juste avant la demande, car la sonde reecrit ce champ a chaque vrai
        ramassage : la poser une fois pour toutes ne tiendrait pas.
        """
        import struct
        if not self.ready():
            return False
        raw = actor_name.encode("ascii")
        if len(raw) > 62:
            raise ValueError("nom trop long pour le tampon de 64 octets")
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

    SEL_MAGIC = 0x52534C31  # "RSL1", ecrit par tools/build_rune_selection_sync.py

    def sel_ready(self):
        """Le patch charge sait-il demander une selection de rune ?

        Meme piege que `pf_ready` : sur un patch sans apCheckSel, ces champs
        tombent sur du code et se lisent sans erreur. Le mot magique tranche.
        """
        return be(self.p.read(self.sel_magic, 4)) == self.SEL_MAGIC

    def request_rune_selection(self, rune_type, timeout=1.0):
        """Faire appeler par le jeu 0x02A2D6D4(*(0x10463798), type).

        Rend True si l'appel a eu lieu, False si le cave l'a refuse (type
        hors des runes livrees, objet de selection absent), None sans reponse
        dans le delai : la requete peut alors encore partir a l'image
        suivante. La demande n'est qu'ENREGISTREE : la mise a jour par image
        du jeu l'applique ensuite (voir botw_client/rune_selection.py).
        """
        if not self.sel_ready():
            raise CaveUnavailable(
                "patch sans selection de rune : FERMER ET ROUVRIR CEMU")
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
        """Faire appeler par le jeu son propre compteur de runes, et le lire."""
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
        """Demander au code injecte d'appeler itemGet."""
        raw = actor_name.encode("ascii")
        if len(raw) > 62:
            raise ValueError("nom trop long pour le tampon de 64 octets")
        self.p.write(self.name_buf, raw + b"\x00" * (64 - len(raw)))
        self.p.write(self.give_value, int(quantity).to_bytes(4, "big"))
        return self.p.write(self.give_req, (1).to_bytes(4, "big"))

    def last_item_name(self, name_ptr):
        """Suivre le SafeString* capture par le hook itemGet jusqu'a la chaine.

        Un sead::SafeString ici fait 8 octets : {const char* cstr; void* vtable}.
        Le nom d'acteur est donc a deux niveaux d'indirection du pointeur capture.
        """
        if not name_ptr or self.base is None:
            return None
        # le cave vit vers 0x01800000, le tas du jeu vers 0x10000000+ :
        # accepter les deux, sinon un nom donne par nous-memes est illisible
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
        print(f"  log de Cemu introuvable ({log})")
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
        print("  ERREUR D'ASSEMBLAGE -- Cemu a rejete tout le fichier :")
        for e in errs[:6]:
            print("   ", e)
        print("")
        print("  Corrige l'instruction fautive, puis relance Cemu.")
    elif applied:
        print("  Le patch s'est applique :")
        for a in applied[-2:]:
            print("   ", a)
        print("")
        print("  Mais la signature reste introuvable : Cemu tourne peut-etre")
        print("  encore sur une session anterieure. Relance le jeu.")
    else:
        print("  Aucune trace du pack dans le log.")
        print("  - est-il coche dans Options > Graphic Packs ?")
        print("  - Cemu a-t-il ete relance depuis ?")


def main():
    value = int(sys.argv[1]) if len(sys.argv) > 1 else None
    pid = cemu_pid()
    if not pid:
        sys.exit("Cemu n'est pas lance")

    with Process(pid, writable=value is not None) as p:
        a = find_cave(p)
        if a is None:
            print("cave introuvable.")
            print("")
            diagnose()
            return

        base, cave_g, _ = guest_base(p, a - 12)
        c = Cave(p, a, base)
        s = c.read()
        print(f"cave trouve (version a {a:#014x})")
        if base is not None:
            print(f"  cave invite    = {cave_g:#010x}")
            print(f"  base inv->hote = {base:#014x}   (hote = invite + base)")
            owner = hook_owner(p, base)
            if owner is None or owner == "aucun hook":
                print(f"  !! aucun hook a {HOOK_GUEST:#010x}")
            elif not hook_is_ours(p, base, cave_g, owner):
                print(f"  !! HOOK VOLE : {HOOK_GUEST:#010x} saute vers {owner:#010x},")
                print("     hors de notre cave. Un autre graphic pack patche la meme")
                print("     adresse -- FPS++ le fait. Desactive-le : sans ce hook,")
                print("     la boite aux lettres et give.py ne fonctionnent plus.")
        else:
            print("  base invite/hote introuvable")
        print(f"  tick     = {s['tick']}      <- preuve de vie (per-frame)")
        print(f"  inbox    = {s['inbox']}")
        print(f"  outbox   = {s['outbox']}")
        print(f"  lastseen = {s['lastseen']}")
        print("")
        print(f"  itemGet appele {s['itemget']} fois")
        if s["itemget"]:
            nom = c.last_item_name(s["name_ptr"])
            print(f"  dernier objet  = {nom if nom else '(nom illisible)'}"
                  f"   quantite = {s['value']}")
            print(f"  name_ptr brut  = {s['name_ptr']:#010x}")

        if s["tick"] == 0:
            print("")
            print("  tick a 0 : le hook n'a jamais ete atteint.")

        # --- etat des canaux, DIT et non laisse a deviner ---------------------
        # Le message d'erreur d'un outil qui refuse est vite oublie ; le voir
        # ici, a chaque diagnostic, coute une ligne.
        print("")
        ok, rn, tick = c.resolve_ready()
        if not ok:
            print(f"  resolveur de pointeurs : ABSENT du patch charge "
                  f"(apResolveN={rn}, tick={tick})")
            print("  -> FERMER ET ROUVRIR CEMU. Recharger une sauvegarde ne "
                  "suffit pas.")
        else:
            print(f"  resolveur de pointeurs : {rn} passages   table d'ecrans = "
                  f"{be(p.read(c.scr_table, 4)):#010x}")
            for nom, (ptr, pret) in c.channels().items():
                print(f"    {nom:<20} {ptr:#010x}  "
                      f"{'pret' if pret else 'NON RESOLU -> refusera'}")

        if value is None:
            print("")
            print("relance pour voir tick augmenter, ou passe une valeur en")
            print("argument pour tester l'aller-retour.")
            return

        print("")
        print(f"envoi de {value} dans inbox ...")
        if not c.send(value):
            sys.exit("ecriture refusee")
        for _ in range(50):
            time.sleep(0.1)
            s = c.read()
            if s["inbox"] == 0 and s["outbox"] == value:
                print(f"ECHO RECU : outbox={s['outbox']}, inbox remis a {s['inbox']}")
                print("")
                print("Le code injecte a lu notre message et a repondu.")
                print("La communication Python -> jeu -> Python fonctionne.")
                return
        print(f"pas d'echo apres 5 s (inbox={s['inbox']}, outbox={s['outbox']})")


if __name__ == "__main__":
    main()
