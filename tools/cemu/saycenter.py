"""Afficher NOTRE texte dans le message central du jeu.

    python tools/cemu/saycenter.py "Alice t'envoie une Epee"
    python tools/cemu/saycenter.py "..." --index 5
    python tools/cemu/saycenter.py --locate      # reperer sans afficher

LE MECANISME, ETABLI PAR MESURE

    0x02ed1f7c(this, index, SafeString*)   empile la demande  -> this+0x154 = 1
    0x02ed1e1c(this, drapeau)              depile et affiche  -> this+0x154 = 0

Les deux sont demandes dans la MEME frame : `apCheckPlay` puis `apCheckMsg` sont
deux blocs successifs du hook per-frame. Chacun pris isolement ne fait rien --
l'empilement laisse le compteur a 1, et le depilage sort par `ble` sur une liste
vide. Il a fallu les deux.

Le texte, lui, suit la meme voie que la notification d'objet : le jeu resout le
message depuis une table statique au moment de l'affichage, donc on y ecrit le
notre, on declenche, et on restaure aussitot.

PREREQUIS : PLUS AUCUN, sinon que l'IHM du jeu existe

Il fallait autrefois avoir declenche un vrai message central depuis le
lancement, pour que la sonde voie passer le `this`. Il est desormais RESOLU a
chaque image : c'est `*(ecran 0x25 + 0x1b84)`, releve sur 0x02fbcaf8 -- une
methode de l'ecran 0x25 qui fait `lwz r3, 0x1b84(r3)` avant de sauter dans
l'empilement 0x02ed1f7c. L'objet obtenu porte bien la liste en +0x14c et son
compte en +0x154, les deux champs que la fonction d'affichage teste.
"""
import json
import pathlib
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winmem import Process
from mailbox import Cave, be, cemu_pid, diagnose, find_cave, guest_base
from findtext import read_utf16, scan
from say import colorize, has_markup

CACHE = pathlib.Path(tempfile.gettempdir()) / "botw_ap_center.json"
# Texte du message d'index 5, en francais. Sert d'ancre pour retrouver l'entree
# dans la table statique ; --msg permet d'en viser un autre.
DEFAULT_INDEX = 5
# Le POINT FINAL fait partie du message. Sans lui `locate()` ne trouvait rien :
# il compare la chaine ENTIERE, pas un prefixe, et refusait donc toutes ses
# propres trouvailles -- panne qui se lisait "entree introuvable".
DEFAULT_MSG = "Le compartiment des vêtements est plein."
WINDOW = 256


def trigger(p, c, idx, timeout=5.0):
    """Empiler puis depiler, dans la meme frame."""
    before = be(p.read(c.play_done, 4))
    p.write(c.play_a, (idx & 0xFFFFFFFF).to_bytes(4, "big"))
    p.write(c.play_raw, bytes(4))
    p.write(c.play_req, (1).to_bytes(4, "big"))
    p.write(c.ms_index, (idx & 0xFFFFFFFF).to_bytes(4, "big"))
    p.write(c.ms_flag, (1).to_bytes(4, "big"))
    p.write(c.ms_queue, bytes(4))
    p.write(c.ms_state, bytes(4))
    p.write(c.ms_req, (1).to_bytes(4, "big"))
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(0.05)
        raw = p.read(c.play_done, 4)
        if not raw:
            raise RuntimeError("Cemu ne repond plus (le jeu a plante).")
        if be(raw) != before:
            return be(p.read(c.ms_ret, 4))
    return None


def locate(p, base, c, msg, idx, cave, verbose=True):
    """Adresse de l'entree du message dans la table statique.

    Plusieurs copies existent : la table lue a l'affichage, et l'arene ou le
    texte resolu est recopie. Un marqueur distinct par candidat, puis un vrai
    affichage, les separe -- la table garde le sien, l'arene recoit celui de la
    table. C'est la meme methode que pour la notification d'objet.
    """
    key = f"{p.pid}:{msg}"
    data = {}
    if CACHE.exists():
        try:
            data = json.loads(CACHE.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
    if key in data:
        first, _ = read_utf16(p, base, data[key])
        if first == msg:
            return data[key]

    if verbose:
        print(f"reperage de {msg[:34]!r} ... (~6 s)")
    cands = []
    for g, _ in scan(p, base, [(msg.encode("utf-16-be"), "be")]):
        if cave and cave[0] <= g < cave[1]:
            continue
        first, _ = read_utf16(p, base, g)
        if first == msg:
            cands.append(g)
    if not cands:
        return None
    if len(cands) == 1:
        static = cands[0]
    else:
        marks = [("ARCHIPELAGO" * (len(msg) // 11 + 2))[:len(msg) - 1] + str(i)
                 for i in range(len(cands))]
        for g, m in zip(cands, marks):
            p.write(base + g, m.encode("utf-16-be"))
        trigger(p, c, idx)
        time.sleep(0.4)
        keep = [g for g, m in zip(cands, marks)
                if read_utf16(p, base, g)[0] == m]
        for g in cands:
            p.write(base + g, msg.encode("utf-16-be"))
        if not keep:
            return None
        static = keep[0]

    data[key] = static
    CACHE.write_text(json.dumps(data), encoding="utf-8")
    if verbose:
        print(f"  entree = {static:#010x}  ({len(msg)} caracteres de place)")
    return static


def main():
    argv = sys.argv[1:]

    def opt(n, d=None):
        if n not in argv:
            return d
        i = argv.index(n) + 1
        return argv[i] if i < len(argv) and not argv[i].startswith("--") else d

    msg = opt("--msg", DEFAULT_MSG)
    idx = int(opt("--index", str(DEFAULT_INDEX)))
    positional = [a for i, a in enumerate(argv)
                  if not a.startswith("--")
                  and (i == 0 or not argv[i - 1].startswith("--"))]

    pid = cemu_pid()
    if not pid:
        sys.exit("Cemu n'est pas lance")

    with Process(pid, writable=True) as p:
        a = find_cave(p)
        if a is None:
            print("cave introuvable.")
            print("")
            diagnose()
            return
        base, cave_g, _ = guest_base(p, a - 12)
        c = Cave(p, a, base)
        cave = (cave_g, cave_g + 2048)

        ok, rn, tick = c.resolve_ready()
        if not ok:
            sys.exit(f"le resolveur du patch charge ne tourne pas "
                     f"(apResolveN={rn}, tick={tick}).\n"
                     "FERMER ET ROUVRIR CEMU : recharger une sauvegarde ne "
                     "suffit pas.")
        if not be(p.read(c.push_this, 4)):
            sys.exit("l'objet des messages n'est pas resolu "
                     "(*(ecran 0x25 + 0x1b84) vaut 0).\n"
                     "Charge une sauvegarde, puis relance.")

        static = locate(p, base, c, msg, idx, cave)
        if static is None:
            print(f"entree {msg[:34]!r} introuvable.")
            print("  Le texte doit etre EXACTEMENT celui affiche a l'ecran.")
            print("  Affiche le message une fois, note-le, et passe-le a --msg.")
            return

        if "--locate" in argv or not positional:
            print("")
            print(f"Place disponible : {len(msg)} caracteres.")
            print('Donne un texte en argument pour l\'afficher.')
            return

        # Le balisage {N} ... {/} devient des codes de controle du jeu.
        # C'est la chaine APRES balisage qui compte pour la place.
        text = colorize(positional[0])
        if len(text) > len(msg):
            sys.exit(f"{len(text)} caracteres pour un emplacement de "
                     f"{len(msg)}. Au-dela on deborde sur les messages voisins "
                     f"-- c'est ce qui faisait planter le jeu avec la "
                     f"notification d'objet.")

        print(f"affichage : {positional[0]!r} "
              f"({len(text)} unites de code" +
              (", balisage couleur inclus)" if has_markup(positional[0])
               else ")"))
        saved = p.read(base + static, max(WINDOW, len(text) * 2 + 32))
        p.write(base + static, text.encode("utf-16-be") + b"\x00\x00")
        try:
            ret = trigger(p, c, idx)
        finally:
            if saved:
                p.write(base + static, saved)
        if ret:
            print("declenche -- regarde l'ecran.")
        else:
            print(f"le jeu a refuse (retour {ret}).")


if __name__ == "__main__":
    main()
