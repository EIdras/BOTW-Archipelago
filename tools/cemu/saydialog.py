"""Afficher NOTRE texte dans la fenetre de dialogue -- la boite bleue.

    python tools/cemu/saydialog.py --state
    python tools/cemu/saydialog.py --open              # porteur d'origine
    python tools/cemu/saydialog.py "Alice t'envoie une Epee"
    python tools/cemu/saydialog.py --colors            # quel index = quelle teinte
    python tools/cemu/saydialog.py --fill 300          # reperes tous les 10
    python tools/cemu/saydialog.py "..." --nowrap      # garder ses propres \n
    python tools/cemu/saydialog.py "..." --arc DemoMsg/Demo008_2 --label talk00

BALISAGE

    {0}..{/}      couleur ; {/} revient au defaut
    {size:80}     code groupe 0 / type 2, en pourcentage
    {t:g,t,hex}   n'importe quel code de controle, pour experimenter
    \n            saut de ligne

COULEURS, RELEVEES A L'ECRAN

    {0} rouge     {1} vert     {2} bleu clair   {3} noir (gris fonce)
    {4} bleu      {5} gris     {6} blanc        {/} blanc (defaut)

L'ordre de la liste de zeldamods (blue, red, grey...) n'est PAS celui des
index : seul l'ecran l'a dit. Les teintes etant definies par layout dans le
`.bflyt`, cette table vaut pour la fenetre de dialogue -- rien ne garantit
qu'elle vaille pour le cadre des conseils ou la notification.

DUREE : PAS TROUVEE

Les deux candidats du recensement (groupe 1 type 3, groupe 1 type 0) n'ont eu
aucun effet visible : le texte s'affiche d'un coup, il n'y a pas d'effet
machine a ecrire a temporiser sur ce chemin. `{pause:N}` a donc ete RETIRE du
balisage plutot que laisse a faire croire qu'il agit.

Le `-1` passe en 6e argument de `0x0358fd38` n'est pas une duree non plus : la
constante `0x24924925` qui suit est le reciproque magique de 7, et la fonction
calcule `(index(libelle) + r6) mod 7` -- un selecteur de variante.

L'enchainement des pages vient donc de la fenetre, pas du texte.

COMBIEN DE CARACTERES

Le porteur ne limite rien : on n'ecrase pas l'arene des messages, on fait
pointer `this+0x1d0` sur notre propre tampon.

Mesure : **trois lignes de 30 caracteres par page**, et le jeu pagine tout seul
au-dela -- 309 unites se sont affichees en trois pages. Le texte est donc
coupe aux espaces a 30 caracteres par defaut, le balisage ne comptant pas dans
la largeur. `--nowrap` laisse la main, `--width N` change la largeur.

Le plafond total vient de notre tampon (2047 unites) ; la fenetre, elle, a
avale 826 unites sans broncher. `--fill N` place des reperes tous
les dix caracteres pour lire une troncature d'un coup d'oeil.

LA CHAINE, ETABLIE PAR MESURE

`msgring.py` a montre que le libelle `talk00` du message de sanctuaire est
resolu depuis le site `0x035fb64c`. En remontant :

    0x035ff8fc(_, SafeString* archive, SafeString* libelle, a, b, drapeau)
        ouvre la fenetre si besoin, puis si drapeau == 0 appelle
    0x035fb5f8(this, archive, libelle)
        resout le message et range { texte, longueur } dans this+0x1d0

Le premier argument de `0x035ff8fc` est ignore (la fenetre vient d'un global),
et `a` / `b` ne sont lus que sur la branche a drapeau non nul -- verifie : r26
et r27 ne reapparaissent qu'en `0x035ffa1c` / `0x035ffa20`. On les laisse donc
nuls. `--replay` rejoue ceux qu'une vraie ouverture a laisses, pour comparer.

LE TEXTE LIBRE

Pas de detour par l'arene des messages : on ecrase directement `this+0x1d0`
avec `{ notre tampon UTF-16BE, longueur }`, dans la MEME image que l'ouverture
(`apCheckDlg` puis `apCheckDlgText` sont deux blocs successifs du hook
per-frame). La longueur est en unites UTF-16, terminateur exclu -- mesure faite
sur le cadre des conseils : porteur de 101 unites, longueur relevee 100.

PREREQUIS : PLUS AUCUN, sinon que l'IHM du jeu existe

Le drapeau (6e argument) est TOUJOURS force a zero. A 1, la fonction part dans
0x035fb1b4 qui dereference les 4e et 5e arguments : rejouer ceux d un appel
precedent -- des pointeurs de tas deja morts -- a plante le jeu. A zero ils ne
sont jamais relus.

Il fallait autrefois avoir vu une vraie boite de dialogue depuis le lancement.
C'etait un verrou de NOTRE fait, et il ne protegeait rien : les arguments
qu'il attendait sont forces a zero de toute facon. 0x035ff8fc, elle, ne
demande rien -- elle va chercher l'ecran 0x26 dans la table du gestionnaire
et LE CREE s'il manque (`li r3, 0x26 ; bl 0x033924c4`). Verifie a froid :
l'emplacement 0x26 passait de 0x00000000 a un ecran vivant sur notre appel.

Le seul prerequis qui reste vient du jeu : 0x035ff8fc dereference
*(0x1047E650) sans le tester. Le cave resout donc la table d'ecrans a chaque
image (apScrTable) et refuse tant qu'elle vaut 0.
"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winmem import Process
from mailbox import Cave, be, cemu_pid, diagnose, find_cave, guest_base
from say import colorize

DEFAULT_ARC = "DemoMsg/Demo008_2"
DEFAULT_LABEL = "talk00"


def tag(grp, typ, params=b""):
    """Un code de controle : 0x000E, groupe, type, taille, parametres.

    Encodage releve sur les MSBT du jeu, pas suppose : la couleur deja utilisee
    par say.py (`000e 0000 0003 0002 <index>`) est le cas particulier
    groupe 0 / type 3, et tous les autres codes suivent la meme forme.
    """
    if len(params) % 2:
        raise ValueError("les parametres se comptent en unites de 16 bits")
    units = [0x000E, grp, typ, len(params)]
    units += [int.from_bytes(params[i:i + 2], "big")
              for i in range(0, len(params), 2)]
    for u in units:
        if 0xD800 <= u <= 0xDFFF:
            raise ValueError(f"unite {u:#06x} dans la plage des substituts "
                             f"UTF-16 : inencodable")
    return "".join(chr(u) for u in units)


# Releve par recensement sur les 991 MSBT du jeu : le pourcentage est le seul
# parametre observe (100, 80, 125, 120). La forme de l'encodage est certaine,
# l'effet ne l'est que pour la couleur et la taille -- les deux candidats de
# temporisation, eux, n'ont rien change a l'ecran. {t:g,t,hex} permet d'essayer
# n'importe quel autre code sans toucher au code source.
SIZE = lambda pct: tag(0, 2, pct.to_bytes(2, "big"))  # 100, 80, 125, 120


def markup(s):
    """Balisage etendu, par-dessus le {N}...{/} de say.py.

        {0}..{/}      couleur (index 0 a 6, {/} revient au defaut)
        {size:80}     code groupe 0 / type 2, pourcentage
        {t:g,t,hex}   n'importe quel code, pour experimenter
        \\n            saut de ligne (la fenetre en affiche trois)
    """
    s = s.replace("\\n", "\n")
    out, i = [], 0
    while i < len(s):
        if s[i] == "{":
            j = s.find("}", i)
            if j != -1:
                body = s[i + 1:j]
                if body.startswith("size:"):
                    out.append(SIZE(int(body[5:], 0)))
                    i = j + 1
                    continue
                if body.startswith("t:"):
                    g, t, hx = body[2:].split(",")
                    out.append(tag(int(g, 0), int(t, 0), bytes.fromhex(hx)))
                    i = j + 1
                    continue
        out.append(s[i])
        i += 1
    return colorize("".join(out))


WIDTH = 30          # mesure : trois lignes de 30 tiennent sur une page
LINES = 3


def wrap_markup(s, width=WIDTH):
    """Couper aux espaces, sans compter le balisage dans la largeur.

    Un `{0}` ne prend aucune place a l'ecran : le compter ferait des lignes
    trop courtes, et couper au milieu casserait la balise. Les groupes entre
    accolades sont donc des jetons de largeur nulle, jamais scindes.
    """
    if "\n" in s or "\\n" in s:
        return s                      # decoupe deja choisie par l'appelant

    def visible(tok):
        out, i = 0, 0
        while i < len(tok):
            if tok[i] == "{" and tok.find("}", i) != -1:
                i = tok.find("}", i) + 1
                continue
            out += 1
            i += 1
        return out

    lines, cur, cur_len = [], "", 0
    for word in s.split(" "):
        w = visible(word)
        if cur and cur_len + 1 + w > width:
            lines.append(cur)
            cur, cur_len = word, w
        else:
            cur = word if not cur else cur + " " + word
            cur_len = w if cur_len == 0 else cur_len + 1 + w
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def poke_cstr(p, addr, s, size):
    data = s.encode("ascii", "replace")
    if len(data) + 1 > size:
        raise ValueError(f"{s!r} depasse le tampon de {size} octets")
    p.write(addr, data + bytes(size - len(data)))


def wait(p, field, before, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(0.05)
        raw = p.read(field, 4)
        if not raw:
            raise RuntimeError("Cemu ne repond plus (le jeu a plante).")
        if be(raw) != before:
            return True
    return False


def state(p, c):
    print(f"  table d ecrans (apScrTable)  : {be(p.read(c.scr_table, 4)):#010x}")
    print(f"  ouvertures vues (0x035ff8fc) : {be(p.read(c.dlg_open_n, 4))}"
          f"  dont a drapeau nul : {be(p.read(c.dlg_open0_n, 4))}")
    print(f"  poses de message (0x035fb5f8): {be(p.read(c.dlg_set_n, 4))}")
    print(f"  fenetre (this)               : {be(p.read(c.dlg_this, 4)):#010x}")
    print(f"  arguments releves            : "
          f"a={be(p.read(c.dlg_arg6, 4)):#010x} "
          f"b={be(p.read(c.dlg_arg7, 4)):#010x} "
          f"drapeau={be(p.read(c.dlg_arg8, 4))}")
    this = be(p.read(c.dlg_this, 4))
    if this and c.base is not None:
        raw = p.read(this + 0x1D0 + c.base, 8)
        if raw:
            print(f"  this+0x1d0                   : "
                  f"ptr={be(raw[0:4]):#010x} longueur={be(raw[4:8])}")


def main():
    argv = sys.argv[1:]

    def opt(name, default=None):
        if name in argv and len(argv) > argv.index(name) + 1:
            return argv[argv.index(name) + 1]
        return default

    arc = opt("--arc", DEFAULT_ARC)
    label = opt("--label", DEFAULT_LABEL)
    text = next((a for a in argv if not a.startswith("--")
                 and a not in (arc, label)), None)

    if "--colors" in argv:
        # Les index 0 a 6 existent (recensement des MSBT) mais rien ne dit
        # lequel donne quelle teinte : le seul juge est l'ecran.
        text = ("{0}zero{/} {1}un{/} {2}deux{/}\\n"
                "{3}trois{/} {4}quatre{/} {5}cinq{/}\\n"
                "{6}six{/} sept-defaut")
    if "--fill" in argv:
        n = int(opt("--fill", "200"))
        # Reperes tous les dix caracteres : une troncature se lit d'un coup
        # d'oeil, la ou un texte uniforme ne dirait rien.
        base = "".join(f"{(k // 10) % 10}" if k % 10 else "|"
                       for k in range(n))
        text = "\\n".join(base[k:k + 30] for k in range(0, len(base), 30))

    pid = cemu_pid()
    if not pid:
        sys.exit("Cemu n'est pas lance")

    with Process(pid, writable=True) as p:
        a = find_cave(p)
        if a is None:
            print("cave introuvable.\n")
            diagnose()
            return
        base, _, _ = guest_base(p, a - 12)
        c = Cave(p, a, base)

        if "--state" in argv or (not text and "--open" not in argv):
            print("etat de la fenetre de dialogue :\n")
            state(p, c)
            print("")
            print("Pour l'ouvrir :  --open")
            print("Avec du texte :  saydialog.py \"mon texte\"")
            return

        ok, rn, tick = c.resolve_ready()
        if not ok:
            sys.exit(f"le resolveur du patch charge ne tourne pas "
                     f"(apResolveN={rn}, tick={tick}).\n"
                     "FERMER ET ROUVRIR CEMU : recharger une sauvegarde ne "
                     "suffit pas.")
        if not be(p.read(c.scr_table, 4)):
            sys.exit("l'IHM du jeu n'est pas construite (table d'ecrans "
                     "introuvable).\nCharge une sauvegarde, puis relance.")

        # --- le drapeau reste a zero, et ce n'est pas un detail --------------
        # A 1, 0x035ff8fc part dans 0x035fb1b4, qui DEREFERENCE les 4e et 5e
        # arguments. Rejouer ceux d'un appel precedent -- deux pointeurs de tas
        # deja morts -- a plante le jeu. A 0, ils ne sont jamais relus : on les
        # laisse nuls plutot que de propager des valeurs sans garantie.
        a6 = a7 = 0
        flag = 0
        if "--replay" in argv:
            a6 = be(p.read(c.dlg_arg6, 4))
            a7 = be(p.read(c.dlg_arg7, 4))
            print(f"  --replay : a={a6:#010x} b={a7:#010x} (drapeau force a 0)")
        p.write(c.dlg_arg6, a6.to_bytes(4, "big"))
        p.write(c.dlg_arg7, a7.to_bytes(4, "big"))
        p.write(c.dlg_arg8, flag.to_bytes(4, "big"))

        poke_cstr(p, c.arc_buf, arc, 64)
        poke_cstr(p, c.lbl_buf, label, 32)

        if text:
            if "--nowrap" not in argv:
                text = wrap_markup(text, int(opt("--width", WIDTH)))
            s = markup(text)
            try:
                ptr, n = c.write_dlg_text(s)
            except ValueError as e:
                sys.exit(f"{e}\nRien n'a ete envoye au jeu : la demande n'est\n"
                         f"posee qu'une fois le texte ecrit.")
            p.write(c.dlg_str_ptr, ptr.to_bytes(4, "big"))
            p.write(c.dlg_str_len, n.to_bytes(4, "big"))

        print(f"archive {arc!r}  libelle {label!r}")
        before_open = be(p.read(c.dlg_done, 4))
        before_text = be(p.read(c.dlg_text_done, 4))

        # --- ne jamais ecrire dans un 'this' perime --------------------------
        # La fenetre est un objet transitoire : le pointeur capture a la
        # session precedente peut avoir ete libere, et lui ecrire dessus est
        # ce qui avait fait planter le jeu du cote de PickUpWin. On le remet a
        # zero ; seule la sonde de NOTRE appel, dans la meme image, le
        # repeuplera. Si l'appel n'aboutit pas, le bloc texte ne fait rien.
        p.write(c.dlg_this, bytes(4))

        if text:
            p.write(c.dlg_text_req, (1).to_bytes(4, "big"))
        p.write(c.dlg_req, (1).to_bytes(4, "big"))

        ok = wait(p, c.dlg_done, before_open)
        print(f"  ouverture : {'appel effectue' if ok else 'AUCUN'}")
        if text:
            ok2 = wait(p, c.dlg_text_done, before_text)
            print(f"  texte     : {n} unites UTF-16, "
                  f"{'ecrit' if ok2 else 'PAS ECRIT'}")
        print("")
        state(p, c)


if __name__ == "__main__":
    main()
