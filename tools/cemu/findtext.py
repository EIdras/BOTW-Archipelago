"""Localiser en RAM le TEXTE AFFICHE d'une notification, pour le remplacer.

Le probleme : 0x02FFA888(ligne, nom) recoit un NOM D'ACTEUR ("Item_Fruit_A").
C'est le jeu qui le resout en texte affiche ("Pomme"). Nous ne controlons donc
que le nom, pas le texte.

UTILISATION
  1. Affiche une notification et LIS le texte a l'ecran :
         python tools/cemu/notify.py Item_Fruit_A --persist
  2. Cherche-le. Les correspondances EXACTES sont listees en premier :
         python tools/cemu/findtext.py "Pomme"
  3. Teste un candidat -- ecrit un marqueur, fait afficher, puis restaure :
         python tools/cemu/findtext.py --probe 0x21c4f244
  4. Si le marqueur s'affiche, cherche qui POINTE dessus pour rediriger vers
     notre tampon au lieu d'ecraser (plus aucune limite de longueur) :
         python tools/cemu/findtext.py --refs 0x21c4f244
         python tools/cemu/findtext.py --repoint 0xSLOT --text "Mon texte"

  --poke ADDR --text "..."   ecrase sur place, sans filet (destructif)

DEUX PIEGES DEJA PAYES
  * Une correspondance n'est pas forcement le bon mot : "Pomme" est aussi un
    PREFIXE de "Pommes", "Pomme grillee", "Pommes au four". Seule une chaine
    suivie immediatement d'un terminateur est le nom de l'objet. D'ou le tri.
  * Chercher en UTF-16LE trouve les memes octets decales d'un cran. Ces
    fantomes sont filtres.
"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winmem import Process
from mailbox import Cave, cemu_pid, find_cave, guest_base

GUEST_SPAN = 1 << 32
CHUNK = 32 << 20


def scan(p, base, needles, align=1):
    """Adresses invitees ou l'un des motifs apparait."""
    hits = []
    longest = max(len(n) for n, _ in needles)
    for rbase, rsize in p.regions(min_size=1 << 12):
        if not (base <= rbase < base + GUEST_SPAN):
            continue
        off = 0
        while off < rsize:
            n = min(CHUNK, rsize - off)
            buf = p.read(rbase + off, n)
            if buf:
                for pat, tag in needles:
                    i = buf.find(pat)
                    while i != -1:
                        g = rbase + off + i - base
                        if g % align == 0:
                            hits.append((g, tag))
                        i = buf.find(pat, i + 1)
            if n < CHUNK:
                break
            off += n - longest
    return hits


def read_utf16(p, base, guest, maxunits=64):
    """Chaine UTF-16BE a cette adresse, et celle qui suit son terminateur."""
    raw = p.read(base + guest, maxunits * 2)
    if not raw:
        return "", ""
    def decode(start):
        out = []
        i = start
        while i + 1 < len(raw):
            u = int.from_bytes(raw[i:i + 2], "big")
            if u == 0:
                break
            out.append(chr(u) if 32 <= u < 0xD800 else "�")
            i += 2
        return "".join(out), i + 2
    first, nxt = decode(0)
    second, _ = decode(nxt)
    return first, second


def marker_for(n):
    """Marqueur de meme longueur que l'original : aucun debordement possible."""
    return ("ARCHIPELAGO" * (n // 11 + 1))[:n]


def do_search(p, base, target):
    hits = scan(p, base, [(target.encode("utf-16-be"), "be")])
    exact, prefix = [], []
    for guest, _ in hits:
        first, second = read_utf16(p, base, guest)
        (exact if first == target else prefix).append((guest, first, second))

    print(f"{len(exact)} correspondance(s) EXACTE(s), "
          f"{len(prefix)} prefixe(s) ecarte(s)\n")
    for guest, first, second in exact:
        print(f"  EXACT  {guest:#010x}  {first!r}")
        if second:
            print(f"                     suivi de {second[:48]!r}")
    if not exact:
        print("  Aucune. Le texte lu a l'ecran est-il exact (accents, casse) ?")
        for guest, first, _ in prefix[:10]:
            print(f"  prefixe {guest:#010x}  {first!r}")
        return exact
    print("")
    print("Teste-les un par un ; le premier qui change l'ecran est le bon :")
    for guest, _, _ in exact:
        print(f"  python tools/cemu/findtext.py --probe {guest:#010x}")
    return exact


def do_probe(p, base, c, guest, actor, keep, hold):
    """Ecrire un marqueur, faire afficher, dire si le jeu l'a reecrit.

    Ce test remplace un classement anterieur qui etait faux : il comparait
    l'avant et l'apres en affichant un AUTRE objet, mais avec --persist aucune
    ligne n'est recyclee, donc rien ne pouvait changer. Ici on force la
    difference au lieu de l'attendre.
    """
    original, _ = read_utf16(p, base, guest)
    if not original:
        sys.exit(f"aucune chaine lisible a {guest:#010x}")
    raw_orig = original.encode("utf-16-be")
    mark = marker_for(len(original))

    print(f"original = {original!r}")
    print(f"marqueur = {mark!r}   (meme longueur : rien n'est deborde)")
    if not p.write(base + guest, mark.encode("utf-16-be")):
        sys.exit("ecriture refusee")

    print("")
    print(f"affichage de {actor} -- REGARDE L'ECRAN MAINTENANT")
    ok = c.notify(actor, duration=hold)
    if not ok:
        # Sans declencheur, il n'y a pas eu de test : le dire, et s'arreter la.
        # Demander « le marqueur s'est-il affiche ? » apres un declencheur
        # rate, c'est reclamer une conclusion sur une mesure qui n'a pas eu
        # lieu -- et une reponse « non » serait lue comme « mauvaise adresse ».
        print("")
        print("LE DECLENCHEUR A ECHOUE : aucune notification n'a ete affichee,")
        print("donc ce test n'a rien mesure. Ne conclus rien de l'ecran.")
        print("")
        print("Cause la plus frequente : le prerequis de session. Le cave")
        print("capture PauseMenuDataMgr et l'ecran de notification au vol, il")
        print("faut donc avoir ramasse un objet une fois depuis le lancement.")
        print("")
        print("Pour la fenetre d'obtention, ce test ne convient de toute")
        print("facon pas : il force un BANDEAU, pas la grande fenetre. Passe")
        print("plutot par --refs sur les copies en tas.")
        p.write(base + guest, raw_orig)
        print("")
        print("original restaure.")
        return
    time.sleep(1.0)

    now, _ = read_utf16(p, base, guest)
    print("")
    if now == mark:
        print("Le jeu n'a PAS reecrit cette zone : c'est une table statique.")
        print("Si le marqueur s'est affiche, cette adresse pilote le texte.")
    else:
        print(f"Le jeu a reecrit la zone ({now!r}) : copie vivante, refaite a")
        print("chaque affichage. Il faudrait ecrire APRES les trois appels.")

    if keep:
        print("")
        print("--keep : le marqueur est laisse en place.")
    else:
        time.sleep(hold if hold and hold < 10 else 4.0)
        p.write(base + guest, raw_orig)
        print("")
        print("original restaure.")
    print("")
    print("Le marqueur s'est-il affiche a l'ecran ?")


def do_refs(p, base, target):
    """Qui pointe sur cette adresse ?

    Rediriger un pointeur vaut mieux qu'ecraser la table : aucune limite de
    longueur, et le texte d'origine reste intact. Seuls les emplacements alignes
    sur 4 sont retenus -- un pointeur PowerPC l'est toujours.
    """
    hits = scan(p, base, [(target.to_bytes(4, "big"), "ptr")], align=4)
    print(f"{len(hits)} emplacement(s) aligne(s) contenant {target:#010x}\n")
    for guest, _ in hits[:40]:
        print(f"  {guest:#010x}")
    if len(hits) > 40:
        print(f"  ... et {len(hits) - 40} autres")
    if hits:
        print("")
        print("Rediriger l'un d'eux vers notre tampon :")
        print(f"  python tools/cemu/findtext.py --repoint {hits[0][0]:#010x} "
              f"--text \"Mon texte\"")
    else:
        print("Aucun pointeur absolu. La table est probablement adressee par")
        print("un index ou un decalage : il faudra ecraser sur place, donc")
        print("rester dans la longueur d'origine.")
    return hits


def do_repoint(p, base, c, slot, text):
    addr = c.write_text(text)
    ok = p.write(base + slot, addr.to_bytes(4, "big"))
    print(f"texte pose dans apText = {addr:#010x} ({len(text)} caracteres)")
    print(f"pointeur {slot:#010x} redirige : {'OK' if ok else 'REFUSE'}")
    if ok:
        print("")
        print("Refais afficher une notification pour voir le resultat.")
    return ok


def do_poke(p, base, guest, text):
    original, _ = read_utf16(p, base, guest)
    data = text.encode("utf-16-be") + b"\x00\x00"
    if len(text) > len(original):
        print(f"ATTENTION : {len(text)} caracteres pour {len(original)} "
              f"d'origine -- la chaine suivante sera ecrasee.")
    ok = p.write(base + guest, data)
    print(f"ecriture de {len(data)} octets a {guest:#010x} : "
          f"{'OK' if ok else 'REFUSEE'}")
    return ok


def do_writehex(p, base, guest, hexstr):
    """Reecrire des octets bruts : de quoi defaire un --poke rate.

    Aucun terminateur n'est ajoute, contrairement a --poke : on remet
    exactement ce qui etait la, terminateurs internes compris.
    """
    data = bytes.fromhex(hexstr.replace(" ", ""))
    ok = p.write(base + guest, data)
    print(f"{len(data)} octets bruts a {guest:#010x} : "
          f"{'OK' if ok else 'REFUSE'}")
    if ok:
        first, second = read_utf16(p, base, guest)
        print(f"relu : {first!r} puis {second[:32]!r}")
    return ok


def main():
    argv = sys.argv[1:]
    if not argv:
        sys.exit(__doc__)

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    text = opt("--text")
    actor = opt("--actor", "Item_Fruit_A")
    hold = float(opt("--hold", "8"))
    keep = "--keep" in argv
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
        base, _, _ = guest_base(p, a - 12)
        if base is None:
            sys.exit("base invite/hote introuvable")
        c = Cave(p, a, base)

        if opt("--probe"):
            do_probe(p, base, c, int(opt("--probe"), 0), actor, keep, hold)
        elif opt("--refs"):
            do_refs(p, base, int(opt("--refs"), 0))
        elif opt("--repoint"):
            if not text:
                sys.exit("--repoint exige --text \"...\"")
            do_repoint(p, base, c, int(opt("--repoint"), 0), text)
        elif opt("--writehex"):
            if not opt("--hex"):
                sys.exit("--writehex exige --hex \"0050006f...\"")
            do_writehex(p, base, int(opt("--writehex"), 0), opt("--hex"))
        elif opt("--poke"):
            if not text:
                sys.exit("--poke exige --text \"...\"")
            do_poke(p, base, int(opt("--poke"), 0), text)
        elif positional:
            do_search(p, base, positional[0])
        else:
            sys.exit(__doc__)


if __name__ == "__main__":
    main()
