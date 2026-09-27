"""Afficher LE TEXTE QU'ON VEUT dans la notification du jeu.

    python tools/cemu/say.py "Simon a trouve la Paravoile" --duration 8
    python tools/cemu/say.py "un texte long ..." --duration 8   # empile
    python tools/cemu/say.py "..." --nowrap       # une seule ligne, sans decoupe
    python tools/cemu/say.py --inspect            # etat de la session
    python tools/cemu/say.py --cleanup            # reparer pointeur et pool

CE QUI SE PASSE VRAIMENT

Le patch ne peut passer qu'un NOM D'ACTEUR ; c'est le jeu qui le resout en texte
via ses tables. Les sondes en jeu ont donne la chaine complete :

    table statique 0x21c4f244  --ECRITE a l'affichage-->  pool 0x436690c0
                                                                ^
                                                          le widget, qui relit
                                                          le pool a chaque image

Route retenue : ecrire dans la table statique, afficher, restaurer la table.
C'est la seule qui ait jamais affiche notre texte.

Route ECARTEE (--pointer, gardee pour memoire) : rediriger le pointeur du pool
vers apText. Verifiee en jeu, elle n'affiche que le nom d'origine -- le jeu
ECRIT le message resolu a travers ce pointeur, donc notre texte est ecrase avant
d'etre dessine.

LA LONGUEUR : 40 CARACTERES, ET C'EST LA LIMITE DU JEU

40 caracteres passent, 44 font planter. Ce n'est PAS un artefact de la methode :
les noms d'objets les plus longs du jeu font ~45 caracteres, et l'interface
plante des qu'on depasse -- y compris dans l'inventaire, hors de toute
notification.

Deux contournements ont ete essayes et ecartes, tous deux verifies en jeu :

  * agrandir a chaud l'emplacement du message (--reserve) : mesure non
    reproductible, plantages ;
  * allonger le nom dans le FICHIER (tools/build_message_mod.py, 120
    caracteres) : construction correcte -- MSBT et SARC passent le test
    d'identite octet pour octet -- mais le jeu plante partout ou le nom est
    dessine.

Reponse retenue : DECOUPER en plusieurs notifications empilees. L'empilement
fonctionne, chaque ligne tient dans la limite, et rien ne deborde. C'est
automatique ; --nowrap s'en dispense.

COULEURS

Le jeu colore son texte avec un code de controle releve dans son archive de
messages (14 824 occurrences, groupe 0 / type 3 / 2 octets) :

    000E 0000 0003 0002 000N   passer en couleur N
    000E 0000 0003 0002 FFFF   revenir au defaut

Le balisage {N} ... {/} est traduit en ces codes.

    say.py "Alice t'envoie une {2}Epee{/}" --duration 8
    say.py "objet recu" --color 2
    say.py --palette              # une teinte par ligne, pour les identifier

Chaque segment colore coute 10 unites de code sur le budget de la ligne, tags
compris. Le plafond porte sur la chaine APRES balisage.

Une ligne balisee n'est pas decoupee : une ouverture separee de sa fermeture
teinterait toute la suite.

L'adresse de l'entree est dans le TAS : elle change a chaque lancement de Cemu.
Elle est localisee a la volee puis mise en cache (cle = PID + nom).
`--relocate` force une nouvelle recherche.

PORTEUR

Par defaut Item_Roast_16, "Fruit de lotus tempo grille" -- le nom en TEXTE
PUR le plus long du jeu (27 caracteres). Son emplacement fait donc 56 octets
au lieu des 12 de "Pomme", ce qui divise par pres de trois le debordement sur
les messages voisins. C'est aussi un plat rare, donc peu vu dans l'inventaire.

27 caracteres sont propres, sans aucun debordement. Jusqu'a 40 ca deborde mais
s'affiche. Pour une autre langue, passe --name avec le texte exact affiche.
"""
import json
import pathlib
import struct
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winmem import Process
from mailbox import Cave, cemu_pid, find_cave, guest_base
from findtext import read_utf16, scan

CACHE = pathlib.Path(tempfile.gettempdir()) / "botw_ap_msgtext.json"
WINDOW = 256            # octets sauvegardes autour de l'entree (route ecrasement)
POOL_SAVE = 512         # copie saine du pool, pour --cleanup
# Porteur : le nom en TEXTE PUR le plus long du jeu (27 caracteres). Son
# emplacement dans l'arene fait donc 56 octets au lieu des 12 de "Pomme", ce qui
# divise par pres de trois ce qu'un texte long deborde sur ses voisins. C'est
# aussi un objet cuisine rare, donc peu vu dans l'inventaire.
DEFAULT_ACTOR = "Item_Roast_16"
DEFAULT_NAME = "Fruit de lotus tempo grillé"
CLEAN_CHARS = len(DEFAULT_NAME)   # au-dela, on deborde (sans planter jusqu'a 40)
MAX_CHARS = 127         # plafond dur, quelle que soit la reservation
# Mesure, pas estimation : 27, 35 et 40 caracteres passent ; 44 fait planter.
# Au-dela de CLEAN_CHARS on deborde sur les messages voisins sans planter :
# --repair remet la copie saine une fois la notification expiree.
SAFE_CHARS = 40


def exact_matches(p, base, name, exclude=None):
    """Adresses ou la chaine est EXACTEMENT `name`, terminateur compris.

    Le filtre d'exactitude est indispensable : "Pomme" est aussi un prefixe de
    "Pommes", "Pomme grillee", "Pommes au four"... Sur une mesure reelle, 9 des
    11 occurrences etaient des prefixes.

    `exclude` retire NOTRE PROPRE code cave. Sans cela, des que le jeu a ecrit
    dans apText, le scan y retrouve le nom et prend notre tampon pour le pool du
    jeu : le pointeur est alors "redirige" vers lui-meme et plus rien n'est
    restaurable.
    """
    out = []
    for guest, _ in scan(p, base, [(name.encode("utf-16-be"), "be")]):
        if exclude and exclude[0] <= guest < exclude[1]:
            continue
        first, _ = read_utf16(p, base, guest)
        if first == name:
            out.append(guest)
    return out


def markers(n, length):
    """n marqueurs DISTINCTS de longueur donnee.

    Distincts, et pas un marqueur commun : une copie vivante est reecrite depuis
    la table. Avec le meme marqueur partout elle recevrait celui de la table et
    paraitrait statique. C'est l'unicite qui rend le tri fiable.
    """
    out = []
    for i in range(n):
        m = ("ARCHIPELAGO" * (length // 11 + 1))[:length]
        tag = str(i)
        out.append((m[:-len(tag)] + tag) if length > len(tag) else tag[:length])
    return out


def classify(p, base, c, cands, name, actor, verbose=False):
    """Trier statiques / copies vivantes en UNE seule notification.

    La duree est sauvegardee et remise : notify() ecrit apDuration, et la sonde
    du jeu ne le reecrit qu'au prochain vrai ramassage. Sans cette restauration,
    la duree de tri (0,5 s) restait en place pour tous les affichages suivants.
    """
    marks = markers(len(cands), len(name))
    for g, m in zip(cands, marks):
        p.write(base + g, m.encode("utf-16-be"))

    saved_dur = c.get_duration()
    c.notify(actor, duration=0.5)
    time.sleep(0.3)

    static, live = [], []
    for g, m in zip(cands, marks):
        now, _ = read_utf16(p, base, g)
        (static if now == m else live).append(g)
        if verbose:
            print(f"  {g:#010x}  ecrit {m!r} -> relu {now!r}  "
                  f"{'STATIQUE' if now == m else 'copie vivante'}")

    for g in cands:
        p.write(base + g, name.encode("utf-16-be"))
    if saved_dur and saved_dur > 0:
        p.write(c.duration, struct.pack(">f", saved_dur))
    return static, live


def _cache_load():
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text())
        except ValueError:
            pass
    return {}


def prime(p, c, actor, verbose=True):
    """Faire resoudre le message UNE FOIS avant de chercher.

    Le pool de destination est rempli PARESSEUSEMENT : tant que le message n'a
    pas ete demande, son entree n'existe pas. Chercher avant l'amorcage ne
    trouve donc que la table statique, sans copie vivante ni pointeur -- c'est
    exactement ce qui donnait "pool non repere" juste apres un redemarrage.
    """
    if verbose:
        print("  amorcage : un affichage bref pour peupler le pool ...")
    saved = c.get_duration()
    ok = c.notify(actor, duration=0.5)
    time.sleep(0.4)
    if saved and saved > 0:
        c.p.write(c.duration, struct.pack(">f", saved))
    return ok


def check_pointer(p, base, ent, verbose=True):
    """Le pointeur montre-t-il encore le pool du jeu ?

    Le jeu ECRIT a travers ce pointeur, il ne fait pas que le lire : tant qu'il
    vise apText, tout message resolu atterrit chez nous -- au point qu'un vrai
    ramassage de pomme affiche notre texte. On repare des qu'on le constate.
    """
    if not ent.get("slot") or not ent.get("live"):
        return None
    cur = int.from_bytes(p.read(base + ent["slot"], 4) or b"\0" * 4, "big")
    if cur == ent["live"]:
        return True
    if verbose:
        print(f"  pointeur egare : {ent['slot']:#010x} -> {cur:#010x} "
              f"au lieu de {ent['live']:#010x}")
        print("  remise en place.")
    p.write(base + ent["slot"], ent["live"].to_bytes(4, "big"))
    return False


def reserve_session(p, base, c, name, actor, nchars, cave=None, verbose=True):
    """Faire naitre GRAND l'emplacement du message dans le pool.

    Le pool est une arene compacte : l'emplacement d'un message est alloue la
    PREMIERE fois qu'il est resolu, a la taille qu'il a alors. "Pomme" fait 5
    caracteres, d'ou un emplacement minuscule -- et tout texte plus long
    deborde sur les voisins (44 caracteres suffisent a faire planter le jeu).

    En resolvant d'abord avec un texte long, l'emplacement nait a cette taille
    et les affichages suivants y tiennent SANS DEBORDER. Il n'y a donc plus de
    voisin ecrase, et plus de reparation a faire.

    A n'utiliser que sur une session FRAICHE : si le message a deja ete resolu,
    son emplacement est deja alloue, petit, et rien ne le redimensionne.
    """
    cands = exact_matches(p, base, name, exclude=cave)
    if len(cands) != 1:
        if verbose:
            print(f"{len(cands)} occurrences de {name!r} au lieu d'une seule.")
            print("Le message a deja ete resolu dans cette session : son")
            print("emplacement est deja alloue. Redemarre Cemu et recommence")
            print("SANS afficher de notification avant.")
        return None
    static = cands[0]

    filler = "".join(chr(0x41 + i % 26) for i in range(nchars))
    if verbose:
        print(f"reservation de {nchars} caracteres ...")
    saved = p.read(base + static, WINDOW)
    p.write(base + static, filler.encode("utf-16-be") + b"\x00\x00")
    ok = c.notify(actor, duration=0.5)
    time.sleep(0.4)
    if saved:
        p.write(base + static, saved)
    if not ok:
        if verbose:
            print("  l'affichage n'a pas repondu : ramasse un objet en jeu")
        return None

    # Chercher un PREFIXE, pas la chaine entiere : si le jeu tronque la copie,
    # chercher les 120 caracteres ne trouve rien et on conclut a tort a un
    # echec. Le prefixe localise l'emplacement, puis on lit ce qui y est
    # REELLEMENT arrive -- c'est la capacite reelle, mesuree et non supposee.
    probe = filler[:12]
    live = [g for g, _ in scan(p, base, [(probe.encode("utf-16-be"), "be")])
            if not (cave and cave[0] <= g < cave[1]) and g != static]
    if not live:
        if verbose:
            print("  rien n'a ete copie : le jeu a refuse ce nom.")
            print("  Essaie une reservation plus courte, ex. --reserve 60.")
        return None

    got, _ = read_utf16(p, base, live[0], maxunits=256)
    landed = len(got)
    if verbose:
        print(f"  emplacement = {live[0]:#010x}")
        if landed < nchars:
            print(f"  demande {nchars} caracteres, {landed} reellement copies")
            print(f"  -> le jeu tronque ; capacite reelle = {landed}")
        else:
            print(f"  {landed} caracteres copies sans troncature")

    ent = {"static": static, "live": live[0], "slot": None,
           "pristine": None, "reserved": landed}
    prime(p, c, actor, verbose=False)          # remettre le vrai nom dedans
    raw = p.read(base + ent["live"], POOL_SAVE)
    if raw:
        ent["pristine"] = raw.hex()
    if verbose:
        print(f"  table = {static:#010x}")
        print(f"  {ent['reserved']} caracteres disponibles sans debordement")
    return ent


def session(p, base, c, name, actor, force=False, verbose=True, cave=None):
    """Tout ce qu'il faut savoir pour cette session : entrees, pointeur, copie saine.

    Mis en cache car la recherche coute ~6 s et se refait a chaque lancement de
    Cemu (les adresses sont dans le tas). La validite du cache est verifiee sur
    le CONTENU, pas seulement sur le PID.
    """
    key = f"{p.pid}:{name}"
    data = _cache_load()
    ent = data.get(key)
    if not force and isinstance(ent, dict) and ent.get("static"):
        first, _ = read_utf16(p, base, ent["static"])
        if first == name:
            check_pointer(p, base, ent, verbose)
            return ent

    if verbose:
        print(f"reperage de {name!r} (~6 s) ...")

    # Chercher AVANT d'amorcer. Tant que le message n'a pas ete resolu, seule
    # la table statique contient le nom : une unique occurrence est donc
    # forcement celle-la, et le reperage se fait sans le moindre affichage.
    # L'ancien ordre coutait trois flashes visibles a l'ecran -- "Pomme",
    # "ARCH0", puis "Pomme" -- avant le vrai message.
    cands = exact_matches(p, base, name, exclude=cave)

    if not cands:
        # rien du tout : la table n'est pas encore chargee, il faut amorcer
        if not prime(p, c, actor, verbose):
            if verbose:
                print("  l'affichage d'amorcage n'a pas repondu.")
                print("  La table de messages n'est pas encore chargee.")
                print("  Charge une sauvegarde, puis relance.")
            return None
        cands = exact_matches(p, base, name, exclude=cave)
        if not cands:
            return None

    if len(cands) == 1:
        ent = {"static": cands[0], "live": None, "slot": None, "pristine": None}
    else:
        # le pool est deja peuple : il faut trier, ce qui coute un flash bref
        static, live = classify(p, base, c, cands, name, actor)
        if not static:
            return None
        ent = {"static": static[0], "live": live[0] if live else None,
               "slot": None, "pristine": None}
        if ent["live"]:
            # Le pool contient encore le marqueur de tri. Le faire reecrire par
            # une resolution NORMALE avant de prendre la copie saine : sans
            # cela --repair reinjectait "ARCH0" a l'ecran.
            prime(p, c, actor, verbose=False)
            raw = p.read(base + ent["live"], POOL_SAVE)
            if raw:
                ent["pristine"] = raw.hex()
            slots = [g for g, _ in scan(
                p, base, [(ent["live"].to_bytes(4, "big"), "p")], align=4)]
            # un seul pointeur = redirection sans ambiguite ; plusieurs = on
            # s'abstient plutot que de deviner lequel le widget utilise
            if len(slots) == 1:
                ent["slot"] = slots[0]

    data[key] = ent
    CACHE.write_text(json.dumps(data))
    if verbose:
        print(f"  table  = {ent['static']:#010x}")
        if ent["live"]:
            print(f"  pool   = {ent['live']:#010x}")
        print(f"  route ECRASEMENT, {SAFE_CHARS} caracteres par ligne")
    return ent


def say_via_pointer(p, base, c, text, slot, actor, duration=None, keep=False):
    """Rediriger le pointeur du widget vers apText.

    Rien n'est ecrit dans les tables du jeu : ni limite de longueur, ni degat.
    Le pointeur est rendu dans un `finally` -- sauf --keep, qui sert a savoir si
    le widget relit le pointeur a chaque image (auquel cas le rendre trop tot
    ferait retomber le texte sur le nom d'origine).
    """
    orig = p.read(base + slot, 4)
    addr = c.write_text(text)
    if not p.write(base + slot, addr.to_bytes(4, "big")):
        raise RuntimeError("ecriture du pointeur refusee")
    try:
        return c.notify(actor, duration=duration)
    finally:
        if orig and not keep:
            p.write(base + slot, orig)
            # relecture : le jeu peut reecrire ce pointeur de son cote. Sans
            # verification, il resterait braque sur apText et tout message
            # resolu -- y compris un vrai ramassage -- afficherait notre texte.
            back = p.read(base + slot, 4)
            if back != orig:
                print(f"  ATTENTION : le pointeur n'a pas tenu "
                      f"({int.from_bytes(back or b'', 'big'):#010x} "
                      f"au lieu de {int.from_bytes(orig, 'big'):#010x})")
                print("  utilise --cleanup avant de continuer a jouer.")


# Code de controle de couleur du jeu : marqueur, groupe 0, type 3, 2 octets de
# parametre. Releve dans l'archive de messages (14 824 occurrences), pas devine :
#   000E 0000 0003 0002 000N   passer en couleur N
#   000E 0000 0003 0002 FFFF   revenir au defaut
COLOR = "\u000e\u0000\u0003\u0002"
RESET = COLOR + "\uffff"
TAG_COST = 5                    # unites de code par tag, a defalquer du budget


def colorize(s):
    """Traduire le balisage {N} ... {/} en codes de controle du jeu."""
    out, i = [], 0
    while i < len(s):
        if s[i] == "{":
            j = s.find("}", i)
            if j != -1:
                body = s[i + 1:j]
                if body == "/":
                    out.append(RESET)
                    i = j + 1
                    continue
                if body.isdigit() and int(body) < 0xFFFF:
                    out.append(COLOR + chr(int(body)))
                    i = j + 1
                    continue
        out.append(s[i])
        i += 1
    return "".join(out)


def has_markup(s):
    return colorize(s) != s


def wrap(text, width=SAFE_CHARS):
    """Decouper en lignes d'au plus `width` caracteres, aux espaces.

    C'est la reponse retenue aux textes longs. Elargir l'emplacement du porteur
    s'est revele impraticable (mesure non reproductible, plantages), alors que
    l'empilement de plusieurs notifications fonctionne deja et ne deborde sur
    rien : chaque ligne tient dans la marge mesuree.
    """
    lines, cur = [], ""
    for word in text.split():
        if len(word) > width:                 # mot plus long que la ligne
            if cur:
                lines.append(cur)
                cur = ""
            while len(word) > width:
                lines.append(word[:width])
                word = word[width:]
        if not cur:
            cur = word
        elif len(cur) + 1 + len(word) <= width:
            cur += " " + word
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def repair_pool(p, base, ent, verbose=True):
    """Remettre la copie saine du pool prise au premier reperage."""
    if not ent.get("pristine") or not ent.get("live"):
        return False
    ok = p.write(base + ent["live"], bytes.fromhex(ent["pristine"]))
    if verbose:
        print(f"  pool repare : {'OK' if ok else 'REFUSE'}")
    return bool(ok)


def say_inplace(p, base, c, text, ent, name, actor, duration=None,
                force=False, repair=None, room=None):
    """Ecrire dans la table statique, afficher, restaurer -- puis reparer le pool.

    C'est la seule route qui ait jamais affiche notre texte. Le jeu recopie la
    table vers le pool au moment de l'affichage ; comme le pool est un arene
    compacte, un texte plus long que le nom porteur deborde sur les messages
    voisins. D'ou la reparation : `repair` est le delai en secondes avant de
    remettre la copie saine.

    `repair=0` repare immediatement -- ce qui sert justement a savoir si le
    widget relit le pool a chaque image (le texte retomberait alors sur le nom
    d'origine sous les yeux) ou s'il en a pris une copie.
    """
    # un emplacement reserve autorise sa propre taille sans debordement ; sinon
    # on reste sous la borne mesuree (40 passe, 44 plante)
    cap = MAX_CHARS if force else (room or ent.get("reserved") or SAFE_CHARS)
    if len(colorize(text)) > cap:
        raise ValueError(
            f"{len(text)} caracteres, plafond {cap}. Sans porteur elargi, 40 "
            f"passent et 44 font planter le jeu. Construis le mod de messages "
            f"(tools/build_message_mod.py) pour lever la limite.")
    # la fenetre sauvegardee doit couvrir ce qu'on ecrit : avec un porteur
    # reserve a 120 caracteres, 256 octets ne suffiraient plus a tout restaurer
    # le balisage devient des codes de controle : c'est la chaine FINALE qui
    # compte pour le budget, chaque tag valant 5 unites de code
    payload = colorize(text)
    saved = p.read(base + ent["static"], max(WINDOW, len(payload) * 2 + 32))
    p.write(base + ent["static"], payload.encode("utf-16-be") + b"\x00\x00")
    try:
        ok = c.notify(actor, duration=duration)
    finally:
        if saved:
            p.write(base + ent["static"], saved)
    if repair is not None:
        if repair:
            time.sleep(repair)
        repair_pool(p, base, ent)
    return ok


def cleanup(p, base, ent):
    """Remettre le pointeur en place, puis la copie saine du pool.

    Le pointeur d'abord : c'est lui qui fait afficher notre texte a la place du
    nom d'un objet reellement ramasse.
    """
    if not ent:
        print("rien en cache pour cette session.")
        return False
    ok = True
    if ent.get("slot") and ent.get("live"):
        ok &= bool(p.write(base + ent["slot"],
                           ent["live"].to_bytes(4, "big")))
        print(f"pointeur {ent['slot']:#010x} -> {ent['live']:#010x} : "
              f"{'OK' if ok else 'REFUSE'}")
    if ent.get("pristine") and ent.get("live"):
        raw = bytes.fromhex(ent["pristine"])
        w = p.write(base + ent["live"], raw)
        ok &= bool(w)
        print(f"{len(raw)} octets du pool restaures : {'OK' if w else 'REFUSE'}")
    elif not ent.get("slot"):
        print("aucune copie saine en cache.")
        print("Redemarre Cemu : les degats ne sont qu'en RAM.")
        return False
    return ok


def inspect(p, base, c, name, actor, ent):
    print(f"table statique  = {ent['static']:#010x}")
    print(f"pool (widget)   = "
          f"{ent['live']:#010x}" if ent.get("live") else "pool non repere")
    if ent.get("slot"):
        cur = int.from_bytes(p.read(base + ent["slot"], 4) or b"\0" * 4, "big")
        print(f"pointeur        = {ent['slot']:#010x} -> {cur:#010x}")
        print(f"route           = POINTEUR, jusqu'a {MAX_CHARS} caracteres")
    else:
        print(f"route           = ECRASEMENT, plafond {len(name)} caracteres")
    if ent.get("live"):
        raw = p.read(base + ent["live"], 64)
        if raw:
            txt = "".join(chr(int.from_bytes(raw[i:i + 2], "big"))
                          if 32 <= int.from_bytes(raw[i:i + 2], "big") < 0xD800
                          else "." for i in range(0, 48, 2))
            print(f"contenu du pool : {txt!r}")
            print("  (des caracteres incoherents ici = pool abime, "
                  "utilise --cleanup)")


def main():
    argv = sys.argv[1:]
    if not argv:
        sys.exit(__doc__)

    def opt(n, default=None):
        """Valeur d'une option, ou le defaut.

        La borne est verifiee : une option placee en DERNIER (--palette seul)
        faisait lever un IndexError au lieu de prendre son defaut.
        """
        if n not in argv:
            return default
        i = argv.index(n) + 1
        if i >= len(argv) or argv[i].startswith("--"):
            return default
        return argv[i]

    # carrier.json est ecrit par tools/build_message_mod.py : il dit quel objet
    # porte le remplissage et quel texte chercher. Sans lui, on retombe sur le
    # jeu non modifie ("Pomme", 40 caracteres par ligne).
    carrier = pathlib.Path(__file__).resolve().parent / "carrier.json"
    cinfo = {}
    if carrier.exists():
        try:
            cinfo = json.loads(carrier.read_text(encoding="utf-8"))
        except ValueError:
            pass
    name = opt("--name", cinfo.get("name", DEFAULT_NAME))
    actor = opt("--actor", cinfo.get("actor", DEFAULT_ACTOR))
    room = cinfo.get("chars")
    duration = None
    if "--persist" in argv:
        duration = 100000.0
    elif "--duration" in argv:
        duration = float(opt("--duration"))
    positional = [a for i, a in enumerate(argv)
                  if not a.startswith("--")
                  and (i == 0 or not argv[i - 1].startswith("--"))]

    pid = cemu_pid()
    if not pid:
        sys.exit("Cemu n'est pas lance")

    with Process(pid, writable=True) as p:
        a = find_cave(p)
        if a is None:
            sys.exit("cave introuvable - le graphic pack est-il actif ?")
        base, cave_g, _ = guest_base(p, a - 12)
        if base is None:
            sys.exit("base invite/hote introuvable")
        c = Cave(p, a, base)
        # notre cave, a exclure du scan : le jeu y ecrit des qu'on a redirige
        # le pointeur, et on retrouverait alors notre propre tampon
        cave = (cave_g, cave_g + 2048)

        if "--check" in argv:
            # Aucun affichage : sert justement quand afficher fait planter.
            # Dit uniquement si le nom porteur est present en memoire, donc si
            # Cemu a bien applique le remplacement de fichier.
            hits = exact_matches(p, base, name, exclude=cave)
            print(f"porteur attendu : {name[:24]!r}... ({len(name)} caracteres)")
            if hits:
                print(f"TROUVE a {', '.join(f'{h:#010x}' for h in hits)}")
                print("Cemu a bien applique le remplacement de fichier.")
            else:
                print("ABSENT de la memoire.")
                short = exact_matches(p, base, DEFAULT_NAME, exclude=cave)
                if short:
                    print(f"En revanche {DEFAULT_NAME!r} est present : le mod")
                    print("n'est PAS charge (pack decoche, ou Cemu ne fait pas")
                    print("le remplacement de fichier).")
                else:
                    print("Et le nom d'origine non plus : le jeu n'a peut-etre")
                    print("pas fini de charger.")
            return


        ok, rn, tick = c.resolve_ready()
        if not ok:
            sys.exit(
                f"le resolveur du patch charge ne tourne pas "
                f"(apResolveN={rn}, tick={tick}).\n"
                "FERMER ET ROUVRIR CEMU : recharger une sauvegarde ne suffit "
                "pas.")
        if not c.ready():
            sys.exit(
                "le pool de lignes de notification n'est pas resolu\n"
                "(ecran 0x28 absent de la table d'ecrans).\n"
                "Charge une sauvegarde, puis relance.")

        if "--reserve" in argv:
            # Piste abandonnee, conservee documentee dans
            # notes de laboratoire (texte libre) : deux essais ont donne 78 puis
            # 13 caracteres, et le troisieme a fait planter le jeu. Ecrire un
            # nom tres long dans la table statique corrompt les messages
            # suivants pendant que le jeu peut les lire.
            sys.exit(
                "--reserve est desactive : mesure non reproductible (78 puis\n"
                "13 caracteres) et plantage du jeu au troisieme essai.\n"
                "Utilise le decoupage en plusieurs lignes, qui est fiable :\n"
                '  python tools/cemu/say.py "un texte long..." --duration 8')

        ent = session(p, base, c, name, actor,
                      force="--relocate" in argv, cave=cave)
        if ent is None:
            print(f"entree {name!r} introuvable.")
            print("  - le texte doit etre exactement celui affiche a l'ecran")
            print("  - as-tu affiche une notification au moins une fois ?")
            return

        if "--cleanup" in argv:
            cleanup(p, base, ent)
            return
        if "--inspect" in argv:
            inspect(p, base, c, name, actor, ent)
            return
        if not positional:
            print("")
            print("Donne le texte a afficher en argument.")
            return

        repair = float(opt("--repair")) if "--repair" in argv else None

        if "--palette" in argv:
            # Une teinte par ligne empilee : le budget d'une ligne ne permet pas
            # de montrer plusieurs couleurs a la fois (10 unites de code par
            # segment colore).
            n = int(opt("--palette") or 8)
            print(f"{n} teintes, une par ligne -- note celles qui te plaisent")
            for k in range(n):
                line = "{%d}couleur %d{/}" % (k, k)
                try:
                    say_inplace(p, base, c, line, ent, name, actor,
                                duration or 12.0, force=True, room=room)
                except (ValueError, RuntimeError) as e:
                    sys.exit(str(e))
                time.sleep(0.35)
            print("Regarde l'ecran.")
            return

        text = " ".join(positional)
        if opt("--color") is not None:
            text = "{%s}%s{/}" % (opt("--color"), text)
        width = room or SAFE_CHARS
        if has_markup(text):
            # le balisage traverserait mal une coupure de ligne :
            # une ouverture sans sa fermeture teinterait toute la suite
            lines = [text]
        else:
            lines = wrap(text, width) if "--nowrap" not in argv else [text]
        if len(lines) > 1:
            print(f"{len(text)} caracteres -> {len(lines)} lignes empilees")
            for i, line in enumerate(lines):
                print(f"  {i + 1}. {line!r}")
                try:
                    say_inplace(p, base, c, line, ent, name, actor,
                                duration, force="--force" in argv,
                                repair=repair, room=room)
                except (ValueError, RuntimeError) as e:
                    sys.exit(str(e))
                time.sleep(0.35)   # laisser la ligne precedente descendre
            print("")
            print("Regarde l'ecran.")
            return

        text = lines[0]
        print(f"affichage : {text!r} ({len(text)} caracteres)")
        try:
            if "--pointer" in argv:
                # conservee pour memoire : le jeu ECRIT le message resolu a
                # travers ce pointeur, donc notre texte est ecrase avant d'etre
                # dessine. Verifie en jeu -- n'affiche que le nom d'origine.
                ok = say_via_pointer(p, base, c, text, ent["slot"], actor,
                                     duration, keep="--keep" in argv)
            else:
                ok = say_inplace(p, base, c, text, ent, name, actor,
                                 duration, force="--force" in argv,
                                 repair=repair, room=room)
        except (ValueError, RuntimeError) as e:
            sys.exit(str(e))
        print("notification declenchee -- regarde l'ecran" if ok
              else "le code injecte n'a pas repondu (tick a 0 ?)")


if __name__ == "__main__":
    main()
