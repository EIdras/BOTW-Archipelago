"""Lire et modifier la table des tailles de ressources (RSTB) de BOTW Wii U.

    python tools/rstb.py --lire  <table.srsizetable>
    python tools/rstb.py --cherche <table.srsizetable> UI/StockItem/Item_AP.bitemico
    python tools/rstb.py --ajoute <table_in> UI/StockItem/Item_AP.bitemico \\
                         --depuis mon_icone.sbitemico <table_out>
    python tools/rstb.py --ajoute <table_in> <chemin> --taille 47104 <table_out>

A QUOI CA SERT

La RSTB dit au jeu quelle taille de tampon reserver pour chaque ressource. Une
valeur trop PETITE fait planter au chargement ; trop grande ne coute que de la
memoire. Un fichier ajoute sans entree ici n'est pas fiable.

LE FORMAT, verifie octet pour octet sur la table du jeu (470 612 octets)

    'RSTB' u32 nb_crc u32 nb_noms         gros-boutiste
    nb_crc  x { u32 crc32(chemin) ; u32 taille }      TRIEE PAR CRC CROISSANT
    nb_noms x { char[128] chemin ; u32 taille }

Le tri n'est pas cosmetique : le jeu fait une recherche dichotomique. Une entree
inseree au mauvais endroit sera introuvable, en silence.

Le chemin est celui de la ressource DECOMPRESSEE, sans `content/` :
`UI/StockItem/Item_AP.bitemico` -- avec `.bitemico`, pas `.sbitemico`.

LA VALEUR, mesuree sur les quatre icones ajoutees par le randomizer

    taille RSTB = taille DECOMPRESSEE + 8192

Verifie sur les quatre, sans exception (96x96, 128x128 et 144x144) :

    Item_Material_DY   38912 -> 47104      Item_RG           67584 -> 75776
    Item_SkyviewEgg    38912 -> 47104      Weapon_Sword_100  94208 -> 102400

`--depuis` applique cette regle. Elle vaut pour les `.bitemico` ; d'autres types
de ressources ont d'autres marges, ne pas la generaliser sans mesurer.
"""
import pathlib
import struct
import sys
import zlib

MARGE_BITEMICO = 8192


def _oead():
    import oead
    return oead


def lire(path):
    """(entrees_crc {crc: taille}, entrees_nom {chemin: taille})."""
    d = pathlib.Path(path).read_bytes()
    if d[:4] == b"Yaz0":
        d = bytes(_oead().yaz0.decompress(d))
    if d[:4] != b"RSTB":
        raise SystemExit(f"{path} n'est pas une RSTB (magie {d[:4]!r})")
    n_crc, n_nom = struct.unpack_from(">II", d, 4)
    crc = {}
    o = 12
    for _ in range(n_crc):
        k, v = struct.unpack_from(">II", d, o)
        crc[k] = v
        o += 8
    noms = {}
    for _ in range(n_nom):
        nom = d[o:o + 128].split(b"\x00")[0].decode("utf-8", "replace")
        noms[nom] = struct.unpack_from(">I", d, o + 128)[0]
        o += 132
    if o != len(d):
        raise SystemExit(f"table mal formee : {o} octets lus sur {len(d)}")
    return crc, noms


def ecrire(path, crc, noms, compresser=True):
    """La table crc est reecrite TRIEE : le jeu la parcourt par dichotomie."""
    out = bytearray(b"RSTB" + struct.pack(">II", len(crc), len(noms)))
    for k in sorted(crc):
        out += struct.pack(">II", k, crc[k])
    for nom in noms:
        b = nom.encode()
        if len(b) > 127:
            raise SystemExit(f"chemin trop long pour la table par nom : {nom}")
        out += b.ljust(128, b"\x00") + struct.pack(">I", noms[nom])
    d = bytes(out)
    if compresser:
        d = bytes(_oead().yaz0.compress(d))
    pathlib.Path(path).write_bytes(d)
    return len(out)


def taille_decompressee(path):
    d = pathlib.Path(path).read_bytes()
    return len(_oead().yaz0.decompress(d)) if d[:4] == b"Yaz0" else len(d)


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    mode, table = argv[1], argv[2]

    if mode == "--lire":
        crc, noms = lire(table)
        print(f"{len(crc)} entrees par CRC, {len(noms)} par nom")
        for n, v in noms.items():
            print(f"   {n}  {v}")
        return

    if mode == "--cherche":
        chemin = argv[3]
        crc, noms = lire(table)
        k = zlib.crc32(chemin.encode())
        print(f"{chemin}\n  crc32 = {k:#010x}")
        print(f"  par CRC : {crc.get(k)}")
        print(f"  par nom : {noms.get(chemin)}")
        return

    if mode == "--ajoute":
        chemin = argv[3]
        if "--depuis" in argv:
            src = argv[argv.index("--depuis") + 1]
            dec = taille_decompressee(src)
            valeur = dec + MARGE_BITEMICO
            print(f"{src} : {dec} decompresse -> {valeur} (+{MARGE_BITEMICO})")
        elif "--taille" in argv:
            valeur = int(argv[argv.index("--taille") + 1])
        else:
            sys.exit("il faut --depuis <fichier> ou --taille <octets>")
        sortie = argv[-1]
        if sortie in (chemin, table):
            sys.exit("donner un fichier de sortie distinct")

        if chemin.endswith(".sbitemico") or "/s" in chemin:
            print("ATTENTION : le chemin doit etre celui de la ressource "
                  "DECOMPRESSEE (.bitemico, pas .sbitemico)")
        crc, noms = lire(table)
        k = zlib.crc32(chemin.encode())
        avant = crc.get(k)
        crc[k] = valeur
        n = ecrire(sortie, crc, noms)
        etat = f"remplacee (etait {avant})" if avant is not None else "ajoutee"
        print(f"{chemin}\n  crc32 = {k:#010x}  taille = {valeur}  [{etat}]")
        print(f"ecrit : {sortie}  ({len(crc)} entrees, {n} octets avant Yaz0)")
        return

    sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
