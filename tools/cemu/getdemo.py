"""Ouvrir la grande fenetre d'obtention d'objet, avec notre texte.

    python tools/cemu/getdemo.py --etat
    python tools/cemu/getdemo.py Item_Fruit_A
    python tools/cemu/getdemo.py Item_Ore_E --titre "Bombes" --desc "Envoye par Alice"
    python tools/cemu/getdemo.py Item_Ore_E --titre "{2}Bombes{/} (Alice)"
    python tools/cemu/getdemo.py Item_Fruit_A --couleurs   # les 7 index a l'ecran
    python tools/cemu/getdemo.py Item_Fruit_A --photo

BALISAGE, identique a celui de la boite de dialogue

    {0}..{/}      couleur ; {/} revient au defaut
    {size:80}     taille, en pourcentage
    {t:g,t,hex}   n'importe quel code de controle, pour experimenter
    un antislash-n litteral    saut de ligne (la description en accepte
                               plusieurs ; le panneau ne coupe pas tout seul)

Il n'y avait rien de special a faire : la substitution ecrit de l'UTF-16BE
brut, et les codes de controle sont des unites de ce flux comme les autres.

COULEURS, RELEVEES A L'ECRAN DANS CETTE FENETRE

    {0} rouge     {1} vert      {2} noir (gris fonce)   {3} bleu
    {4} orange    {5} gris clair    {6} blanc

ATTENTION : ce n'est PAS la table de la boite de dialogue. Les deux partagent
les index 0 et 1 puis divergent -- ici {2} est noir et {4} orange, la-bas {2}
est bleu clair et {4} bleu, et l'orange n'existe pas. La table index -> teinte
est definie PAR LAYOUT dans le `.bflyt` : chaque canal a la sienne, et la
supposer partagee donne du texte de la mauvaise couleur sans rien signaler.
`--couleurs` affiche les sept index cote a cote pour la remesurer ailleurs.

L'APPEL

    0x035fe7f4(gestionnaire, objet_chaine)
        gestionnaire = *(0x1047b054)    PAS *(0x1047e650), qui est celui des ecrans
        objet_chaine = { char* ASCII @+0 ; 0x1008bf50 @+4 ; taille @+8 }

Il fait trois choses : creer l'ecran 0x0b, COPIER LE NOM D'ACTEUR dans
`gestionnaire->0x20` (tronque a `->0x28`, 64 octets), puis l'ouvrir. C'est
l'etape du milieu qui manquait a `getwintext.py --ouvre`, et c'est pour ca que
la fenetre synthetique se dessinait sans rien montrer : elle etait VIDE.

A partir du seul nom d'acteur, le jeu resout titre, description ET icone.

D'OU VIENT L'ADRESSE

Chaine d'ancrage, entierement hors ligne :

    Randomizer (mod de Waikuteru) appelle GetDemo::GetItemByNameR
      -> SUBFLOW GetDemo::ShowGetDemoDialogByName
        -> EventSystemActor::Demo_OpenGetDemoDialog
          -> EventSystemActor.baiprog, Action_100 : ClassName OpenGetDemoDialog
            -> ses 4 noms de parametres, contigus en .rodata (0x1008bf90...)
              -> tous references par 0x0234be58 = loadParams_
                -> une seule relocation la vise : vtable 0x1008bff8
                  -> enter_ = 0x0234bba8, dont le chemin simple fait :
                       r3 = *(0x1047b054) ; r4 = this+0x1c ; bl 0x035fe7f4

L'objet chaine, mesure sur trois sites (dont une construction sur pile en
0x0234bd1c) : `{ const char* @+0 ; vtable @+4 ; s32 taille @+8 }`. Le vptr est
en +0x04, pas en +0x00 -- contre-intuitif, mais 0x035fe7f4 lit bien le char*
en +0x00 pour le recopier, et n'appelle que vtable[+0x1c] (longueur).

CE QUI EST VERIFIE EN JEU

* la fenetre s'affiche entierement : titre, description et icone ;
* elle RESTE OUVERTE toute seule -- aucun maintien n'est necessaire. Le
  bricolage `apHoldN` ne servait qu'a la fenetre synthetique ;
* le joueur la ferme au bouton, comme une vraie. Il n'y a donc rien a
  implementer pour la fermer.

LE PIEGE, PAYE UNE FOIS

Une fenetre laissee ouverte EMPOISONNE L'OBJET SUIVANT : le prochain coffre
affiche NOTRE objet a la place du sien. `enter_` teste `0x035fda08()` d'abord
et part sur un autre chemin (`0x035ff004`) si une fenetre existe deja -- le nom
du vrai objet n'est alors jamais recopie. D'ou le refus d'ouvrir par-dessus une
fenetre en cours, sauf `--force`.

L'ORACLE

Ne pas croire l'ecran sur parole : le controle qui tranche est
`gestionnaire->0x20` APRES l'appel. S'il contient le nom, l'appel a abouti.
C'est le seul temoin qui distingue « rien ne s'est passe » de « la fenetre
s'ouvre mais ne montre rien ».

Mesure negative, a ne pas refaire : poser le bit 0x100 de `ecran+0x94` -- le
drapeau de fermeture que le jeu utilise lui-meme -- est INERTE ici.
"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from mailbox import open_cave, CaveUnavailable, be
from saydialog import markup

# --- adresses invitees, 1.5.0 EUR ---------------------------------------
MGR_PTR = 0x1047B054      # -> le gestionnaire de la fenetre d'obtention
SCR_PTR = 0x1047E650      # -> le gestionnaire d'ECRANS (case 0x0b = la fenetre)
OPEN_FN = 0x035FE7F4      # (mgr, chaine) : cree, remplit le nom, ouvre
STR_VT = 0x1008BF50       # vtable de l'objet chaine

# L'objet chaine vit dans la QUEUE d'apText, apres le nom ASCII. Surtout pas
# dans sub_buf : c'est le tampon du TITRE de la substitution, et l'ecraser
# armerait un titre corrompu a la premiere fenetre.
OBJ_OFF = 0xC0

# Voisine utile, non appelee ici : 0x035fda08() dit si la fenetre est libre.
# Elle IGNORE ses arguments -- elle relit l'ecran 0x0b elle-meme, ce que fait
# aussi ecran() ci-dessous, en moins cher.


def rd(p, c, guest, n=4):
    """Lire n octets a une adresse invitee."""
    raw = p.read(c.base + guest, n)
    return be(raw) if n == 4 else raw


def ecran(p, c):
    """(ecran de la case 0x0b, octet d'activite). Meme calcul que 0x035fda08."""
    scr = rd(p, c, SCR_PTR)
    if not scr:
        return 0, 0xFF
    tab = rd(p, c, scr + 0x18)
    e = rd(p, c, tab + 0x0B * 4) if tab else 0
    return e, (rd(p, c, scr + 0x604, 0x10)[0x0B] if e else 0xFF)


def etat(p, c, verbeux=True):
    """Le gestionnaire, son tampon de nom, l'ecran, la substitution."""
    mgr = rd(p, c, MGR_PTR)
    e, act = ecran(p, c)
    if not verbeux:
        return mgr, e, act
    print(f"gestionnaire *({MGR_PTR:#010x}) = {mgr:#010x}")
    if not mgr:
        print("  NUL -- le jeu n'a pas encore construit la fenetre d'obtention.")
        print("  Ramasser un objet une fois, puis relancer.")
        return mgr, e, act
    buf, cap = rd(p, c, mgr + 0x20), rd(p, c, mgr + 0x28)
    print(f"  ->0x20  tampon du nom = {buf:#010x}")
    print(f"  ->0x28  capacite      = {cap} ({cap:#x})")
    if buf:
        print(f"  contenu actuel       = {c.cstr(buf, min(cap, 64))!r}")
    print(f"ecran case 0x0b = {e:#010x}   activite = {act:#04x}"
          + ("   OUVERTE" if e and act != 0xFF else "   (absent)" if not e else ""))
    ok, req = be(p.read(c.opn_ok, 4)), be(p.read(c.opn_req, 4))
    ligne = "invocateur : "
    if hasattr(c, "pf_req") and c.pf_ready():
        pfr = be(p.read(c.pf_req, 4))
        ligne += "per-frame DISPONIBLE (sans prerequis)"
        ligne += f"   requete EN ATTENTE={pfr}" if pfr else ""
        ligne += f"   |  ancien apOpnOk={ok}"
    elif hasattr(c, "pf_req"):
        ligne += (f"per-frame ABSENT du patch charge (apPfReq lit "
                  f"{be(p.read(c.pf_req, 4)):#x}) -- PATCH PERIME, fermer et "
                  f"rouvrir Cemu ; en attendant, ancien invocateur "
                  f"(apOpnOk={ok})")
    else:
        ligne += f"apOpnOk={ok} " + ("(vivant)" if ok
                                     else "(ENDORMI -- ouvrir un coffre une fois)")
    ligne += f"   ancienne requete EN ATTENTE={req}" if req else ""
    print(ligne)
    t_req, t_ok, d_req, d_ok, auto = c.sub_state()
    if t_req or d_req or auto:
        print(f"substitution ARMEE : titre={t_req} desc={d_req} auto={auto}")
    return mgr, e, act


def main():
    opt = sys.argv[1:]
    argv = [a for a in opt if not a.startswith("--")]
    # retirer les valeurs des options a argument
    for name in ("--titre", "--desc"):
        if name in opt:
            v = opt[opt.index(name) + 1] if len(opt) > opt.index(name) + 1 else None
            if v in argv:
                argv.remove(v)

    # Tester `startswith("--")` ne marche pas : un titre peut commencer par des
    # tirets, et c'est exactement le cas des regles de mesure.
    DRAPEAUX = {"--etat", "--photo", "--force", "--titre", "--desc",
                "--couleurs", "--ancien"}

    def val(name):
        i = opt.index(name) if name in opt else -1
        if i < 0:
            return None
        if i + 1 >= len(opt) or opt[i + 1] in DRAPEAUX:
            sys.exit(f"{name} attend une valeur")
        return opt[i + 1]

    try:
        p, c = open_cave()
    except CaveUnavailable as e:
        sys.exit(str(e))

    with p:
        mgr, e, act = etat(p, c)
        if "--etat" in opt or not mgr:
            return
        if not argv:
            sys.exit('\nDonner un nom d\'acteur :\n'
                     '  python tools/cemu/getdemo.py Item_Fruit_A '
                     '--titre "Bombes" --desc "Envoye par Alice"')

        # Deux invocateurs. Le per-frame (apPfReq) tourne depuis le demarrage
        # du jeu ; l'ancien (apOpnReq, mode 8) vit dans le pilote de
        # MessageGet_00 et reste muet derriere apOpnOk tant que la vraie
        # fenetre n'a pas ete vue -- en laissant sa requete EN ATTENTE, qui
        # partait alors au prochain vrai coffre, lequel affichait notre objet.
        pf = (hasattr(c, "pf_req") and c.pf_ready()
              and "--ancien" not in opt)
        if not pf and not be(p.read(c.opn_ok, 4)):
            sys.exit(
                "\nREFUS : l'ancien invocateur n'est pas encore vivant "
                "(apOpnOk=0).\n"
                "  Ouvrir un coffre une fois, ou retirer --ancien.\n"
                "  Rien n'a ete arme : le prochain coffre est intact.")

        if e and act != 0xFF and "--force" not in opt:
            sys.exit(
                "\nREFUS : une fenetre est deja ouverte.\n"
                "  En ouvrir une par-dessus ne recopierait pas le nom, et le\n"
                "  PROCHAIN VRAI COFFRE afficherait cet objet-ci a la place du\n"
                "  sien. Fermer la fenetre au bouton, puis relancer.\n"
                "  (--force pour passer outre en connaissance de cause.)")

        nom = argv[0]
        # Le panneau NE COUPE PAS tout seul : les descriptions du jeu portent
        # leurs propres retours a la ligne. On accepte donc "\n" litteral.
        #
        # BALISAGE : le meme que la boite de dialogue -- {N}...{/} pour la
        # couleur, {size:80} pour la taille, {t:g,t,hex} pour essayer
        # n'importe quel code. Rien de special n'est requis ici : la
        # substitution ecrit de l'UTF-16BE brut dans this->{texte, longueur},
        # exactement comme les autres canaux, et les codes de controle sont
        # des unites de ce flux. La longueur passee au jeu les compte, ce qui
        # est correct -- c'est ce que fait le jeu pour ses propres messages.
        #
        # RESERVE, non levee : la table d'index -> teinte est definie PAR
        # LAYOUT dans le .bflyt. Celle relevee a l'ecran vaut pour la boite de
        # dialogue ; rien ne garantit que la fenetre d'obtention emploie la
        # meme. `--couleurs` affiche les sept index pour le mesurer.
        titre, desc = val("--titre"), val("--desc")
        if "--couleurs" in opt:
            titre = "{0}A{1}B{2}C{3}D{4}E{5}F{6}G{/}H"
            desc = ("{0}zero {1}un {2}deux {3}trois\\n"
                    "{4}quatre {5}cinq {6}six{/} defaut")
        if titre is not None:
            titre = markup(titre)
        if desc is not None:
            desc = markup(desc)
        cap = rd(p, c, mgr + 0x28)
        if len(nom) + 1 > cap:
            print(f"\nATTENTION : {len(nom)} caracteres pour une capacite de "
                  f"{cap} -- le jeu tronquera.")

        # Le texte est arme AVANT l'ouverture : le panneau fige son contenu
        # quand il se construit, pas apres.
        if titre is not None:
            c.sub_write(titre)
            print(f"titre arme       : {titre!r}")
        if desc is not None:
            c.sub_write_desc(desc)
            print(f"description armee: {desc!r}")

        nom_g = c.write_text(nom, "ascii")
        obj_g = c.guest(c.text_buf + OBJ_OFF)
        p.write(c.text_buf + OBJ_OFF,
                nom_g.to_bytes(4, "big")
                + STR_VT.to_bytes(4, "big")
                + (0x40).to_bytes(4, "big"))
        print(f"objet chaine en {obj_g:#010x} = "
              f"{{ {nom_g:#010x} ; {STR_VT:#010x} ; 0x40 }}   nom={nom!r}")

        n = be(p.read(c.call_n, 4))
        voie = "per-frame (apPfReq)" if pf else "pilote MessageGet_00 (mode 8)"
        print(f"appel 0x035fe7f4({mgr:#010x}, {obj_g:#010x})  via {voie}")
        (c.call_pf if pf else c.call)(OPEN_FN, mgr, obj_g)

        for _ in range(300):
            if be(p.read(c.call_n, 4)) > n:
                break
            time.sleep(0.01)
        else:
            # Une requete non consommee RESTE EN ATTENTE dans le cave et part
            # au prochain passage du pilote -- donc au prochain vrai coffre,
            # qui affichait alors notre objet. L'annuler est obligatoire.
            p.write(c.pf_req if pf else c.opn_req, bytes(4))
            if titre is not None or desc is not None:
                c.sub_disarm()
            sys.exit("le cave n'a pas repondu : requete ANNULEE, substitution "
                     "desarmee.\n  Le jeu tourne-t-il ? FPS++ est-il actif ?")

        buf = rd(p, c, mgr + 0x20)
        vu = c.cstr(buf, min(cap, 64)) if buf else None
        ok = vu == nom
        print(f"\nmgr->0x20 apres l'appel = {vu!r}  "
              + ("<-- le nom est passe" if ok else "<-- PAS le nom attendu"))
        e, act = ecran(p, c)
        print(f"ecran case 0x0b = {e:#010x}   activite = {act:#04x}"
              + ("" if e and act != 0xFF else "   RIEN NE SERA DESSINE"))

        # Un armement qui ne serait pas consomme frapperait le prochain VRAI
        # coffre. En cas d'echec on desarme plutot que de laisser la mine.
        if not ok and (titre is not None or desc is not None):
            c.sub_disarm()
            print("substitution desarmee (l'appel n'a pas abouti)")

        if "--photo" in opt:
            import subprocess
            time.sleep(0.7)
            out = pathlib.Path(__file__).resolve().parents[2] / "getdemo.png"
            subprocess.run([sys.executable,
                            str(pathlib.Path(__file__).with_name("shot.py")),
                            str(out), "--jeu"], check=False)
            print(f"photo : {out}")

        if e:
            print("\nFermer la fenetre au bouton avant de reprendre le jeu :\n"
                  "  laissee ouverte, elle fera afficher CET objet au prochain "
                  "coffre.")


if __name__ == "__main__":
    main()
