"""Lire et fabriquer une icone d'objet Wii U (.sbitemico).

    python tools/bitemico.py --extrait Item_SkyviewEgg.sbitemico egg.png
    python tools/bitemico.py --remplace modele.sbitemico logo.png Item_AP.sbitemico
    python tools/bitemico.py --infos modele.sbitemico

POURQUOI CE FICHIER COMPTE

Le moteur construit lui-meme le chemin `UI/StockItem/%s.bitemico` a partir du
NOM D'ACTEUR, avec repli sur `UI/StockItem/NoImage.bitemico` (chaines relevees
dans le RPX en 0x1025deec et 0x1021d8ac). Deposer un fichier a ce nom suffit
donc a donner une icone -- c'est la voie du contenu, pas du code.

Le jeu de base n'en contient AUCUN : les icones des objets normaux sont rendues
depuis leur modele. `UI/StockItem/` est le chemin de surcharge, celui qu'utilise
le randomizer de Waikuteru pour ses objets ajoutes.

LE FORMAT, mesure sur Item_SkyviewEgg.sbitemico du randomizer

    Yaz0 -> BFRES 'FRES' v3.5 gros-boutiste, un seul bloc FTEX :
        96 x 96, 1 mip, format 0x41a = TCS_R8_G8_B8_A8_SRGB (RGBA8 non compresse)
        tileMode 4 (2D tiled thin1), swizzle 0xd0000, pitch 96
        imageSize 0x9000 = 96*96*4, exactement

L'image fait donc la meme taille en pixels bruts qu'en octets stockes : on peut
remplacer les donnees SUR PLACE, sans toucher a un seul offset du BFRES.

LE PAVAGE

Les textures Wii U ne sont pas lineaires : l'adresse d'un pixel passe par
AddrLib (pipes, banks, micro-tuiles de 8x8). `addr_macro_tiled()` en est le
portage pour notre cas -- 2D tiled, sans echange de banques, sans multi-
echantillonnage. La MEME fonction sert dans les deux sens : l'extraction batit
la permutation, le remplacement l'applique a l'envers. Si l'image extraite est
juste, la reecriture l'est aussi.

Verification : `--extrait` sur une icone du randomizer doit donner une image
reconnaissable. C'est le seul controle qui vaille.
"""
import pathlib
import struct
import sys
import zlib

# --- AddrLib, constantes Wii U (R600 family) ----------------------------
M_BANKS = 4
M_BANKS_BITS = 2
M_PIPES = 2
M_PIPES_BITS = 1
M_GROUP_BITS = 8          # pipeInterleaveBytes = 256


def pixel_index_micro_tile(x, y, bpp):
    """Position du pixel dans sa micro-tuile 8x8. Cas bpp=32 uniquement."""
    if bpp != 32:
        raise NotImplementedError("seul le RGBA8 (32 bpp) est gere")
    b0 = x & 1
    b1 = (x & 2) >> 1
    b2 = y & 1
    b3 = (x & 4) >> 2
    b4 = (y & 2) >> 1
    b5 = (y & 4) >> 2
    return b0 | (b1 << 1) | (b2 << 2) | (b3 << 3) | (b4 << 4) | (b5 << 5)


def addr_macro_tiled(x, y, bpp, pitch, height, tile_mode,
                     pipe_swizzle=0, bank_swizzle=0):
    """Octet ou vit le pixel (x, y). 2D tiled thin1, 1 echantillon, 1 tranche."""
    micro_tile_bits = bpp * 64                       # epaisseur 1
    pixel_index = pixel_index_micro_tile(x, y, bpp)
    elem_offset = (bpp * pixel_index + 7) // 8

    pipe = ((y >> 3) ^ (x >> 3)) & 1
    bank_bit0 = ((y // (16 * M_PIPES)) ^ (x >> 3)) & 1
    bank_bit1 = ((y // (8 * M_PIPES)) ^ (x >> 4)) & 1
    bank = bank_bit0 | (bank_bit1 << 1)

    # rotation : m_pipes * ((m_banks >> 1) - 1) pour les modes 4 a 11
    rotation = M_PIPES * ((M_BANKS >> 1) - 1) if 4 <= tile_mode <= 11 else 0
    swizzle = pipe_swizzle + M_PIPES * bank_swizzle
    bank_pipe = (pipe + M_PIPES * bank) ^ swizzle          # tranche 0
    bank_pipe %= M_PIPES * M_BANKS
    pipe, bank = bank_pipe % M_PIPES, bank_pipe // M_PIPES
    del rotation                                            # nul en tranche 0

    macro_pitch, macro_height = 8 * M_BANKS, 8 * M_PIPES
    if tile_mode in (5, 9):
        macro_pitch >>= 1
        macro_height *= 2
    elif tile_mode in (6, 10):
        macro_pitch >>= 2
        macro_height *= 4

    macro_tiles_per_row = pitch // macro_pitch
    macro_tile_bytes = (bpp * macro_height * macro_pitch + 7) // 8
    macro_tile_offset = ((x // macro_pitch)
                         + macro_tiles_per_row * (y // macro_height)) * macro_tile_bytes

    total = elem_offset + (macro_tile_offset >> (M_BANKS_BITS + M_PIPES_BITS))
    mask = (1 << M_GROUP_BITS) - 1
    low = total & mask
    high = (total & ~mask) << (M_BANKS_BITS + M_PIPES_BITS)
    return (bank << (M_PIPES_BITS + M_GROUP_BITS)) | (pipe << M_GROUP_BITS) | low | high


# --- BFRES : localiser le bloc FTEX et ses donnees ----------------------

class Icone:
    def __init__(s, raw):
        s.raw = bytearray(raw)
        o = s.raw.find(b"FTEX")
        if o < 0:
            raise SystemExit("pas de bloc FTEX dans ce BFRES")
        s.ftex = o
        f = struct.unpack_from(">16I", s.raw, o + 4)
        (s.dim, s.width, s.height, s.depth, s.mips, s.format, s.aa, s.use,
         s.image_size, _ptr, s.mip_size, _mptr, s.tile_mode, s.swizzle,
         s.align, s.pitch) = f
        # le decalage vers les pixels est un mot du bloc FTEX ; on le retrouve
        # en cherchant le seul bloc de image_size octets aligne sur align.
        s.data_off = s._trouver_donnees()

    def _trouver_donnees(s):
        """Les pixels sont le dernier bloc, aligne, de image_size octets."""
        n = len(s.raw)
        if n < s.image_size:
            raise SystemExit("fichier plus court que imageSize")
        cand = (n - s.image_size) & ~(s.align - 1)
        # controle : le bloc doit tenir entierement dans le fichier
        while cand > 0 and cand + s.image_size > n:
            cand -= s.align
        return cand

    def infos(s):
        return (f"{s.width}x{s.height}  mips={s.mips}  format={s.format:#x}  "
                f"tileMode={s.tile_mode}  swizzle={s.swizzle:#x}  pitch={s.pitch}  "
                f"imageSize={s.image_size:#x}  pixels @{s.data_off:#x}")

    def _verifier(s):
        if s.format != 0x41A:
            raise SystemExit(f"format {s.format:#x} non gere (attendu 0x41a, RGBA8)")
        if s.tile_mode != 4:
            raise SystemExit(f"tileMode {s.tile_mode} non gere (attendu 4)")
        # imageSize se calcule sur le PITCH, pas sur la largeur : le pitch est
        # arrondi au multiple de 32 superieur (144 de large -> pitch 160 sur
        # Weapon_Sword_100). Verifier contre width rejetait ces icones-la.
        if s.image_size != s.pitch * s.height * 4:
            raise SystemExit(f"imageSize {s.image_size:#x} ne colle pas a "
                             f"pitch*height*4 ({s.pitch * s.height * 4:#x})")

    def table(s):
        """[(index_lineaire, adresse_pavee)] pour chaque pixel."""
        ps = (s.swizzle >> 8) & 1
        bs = (s.swizzle >> 9) & 3
        return [(4 * (y * s.width + x),
                 addr_macro_tiled(x, y, 32, s.pitch, s.height, s.tile_mode, ps, bs))
                for y in range(s.height) for x in range(s.width)]

    def lire_rgba(s):
        s._verifier()
        d, out = s.raw, bytearray(s.width * s.height * 4)
        for lin, adr in s.table():
            out[lin:lin + 4] = d[s.data_off + adr: s.data_off + adr + 4]
        return bytes(out)

    def ecrire_rgba(s, rgba):
        s._verifier()
        if len(rgba) != s.width * s.height * 4:
            raise SystemExit(f"il faut {s.width}x{s.height} pixels RGBA, "
                             f"recu {len(rgba) // 4} pixels")
        for lin, adr in s.table():
            s.raw[s.data_off + adr: s.data_off + adr + 4] = rgba[lin:lin + 4]


# --- PNG minimal (RGBA8, sans entrelacement) ----------------------------

def png_ecrire(path, w, h, rgba):
    brut = b"".join(b"\x00" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    def bloc(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c))
    png = (b"\x89PNG\r\n\x1a\n"
           + bloc(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + bloc(b"IDAT", zlib.compress(brut, 9))
           + bloc(b"IEND", b""))
    pathlib.Path(path).write_bytes(png)


def png_lire(path):
    d = pathlib.Path(path).read_bytes()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{path} n'est pas un PNG")
    idat, w = b"", None
    o = 8
    while o < len(d):
        n, typ = struct.unpack_from(">I4s", d, o)
        corps = d[o + 8:o + 8 + n]
        if typ == b"IHDR":
            w, h, prof, coul, comp, filt, entre = struct.unpack(">IIBBBBB", corps)
            if prof != 8 or coul != 6:
                raise SystemExit("il faut un PNG 8 bits RGBA (couleur 6, profondeur 8)")
            if entre:
                raise SystemExit("PNG entrelace non gere")
        elif typ == b"IDAT":
            idat += corps
        elif typ == b"IEND":
            break
        o += 12 + n
    if w is None:
        raise SystemExit("PNG sans IHDR")
    return w, h, _defiltrer(zlib.decompress(idat), w, h)


def _defiltrer(brut, w, h):
    """Les cinq filtres PNG. bpp = 4 pour du RGBA8."""
    bpp, ligne = 4, w * 4
    out = bytearray()
    prec = bytearray(ligne)
    o = 0
    for _ in range(h):
        f = brut[o]
        o += 1
        cur = bytearray(brut[o:o + ligne])
        o += ligne
        for i in range(ligne):
            a = cur[i - bpp] if i >= bpp else 0
            b = prec[i]
            c = prec[i - bpp] if i >= bpp else 0
            if f == 1:   cur[i] = (cur[i] + a) & 0xFF
            elif f == 2: cur[i] = (cur[i] + b) & 0xFF
            elif f == 3: cur[i] = (cur[i] + (a + b) // 2) & 0xFF
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                cur[i] = (cur[i] + pred) & 0xFF
            elif f:
                raise SystemExit(f"filtre PNG {f} inconnu")
        out += cur
        prec = cur
    return bytes(out)


# --- entree/sortie .sbitemico -------------------------------------------

def _oead():
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import oead
    return oead


def charger(path):
    oead = _oead()
    d = pathlib.Path(path).read_bytes()
    return Icone(oead.yaz0.decompress(d) if d[:4] == b"Yaz0" else d)


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    mode = argv[1]
    if mode == "--infos":
        print(charger(argv[2]).infos())
    elif mode == "--extrait":
        ico = charger(argv[2])
        print(ico.infos())
        png_ecrire(argv[3], ico.width, ico.height, ico.lire_rgba())
        print("ecrit :", argv[3])
    elif mode == "--remplace":
        oead = _oead()
        ico = charger(argv[2])
        w, h, rgba = png_lire(argv[3])
        if (w, h) != (ico.width, ico.height):
            sys.exit(f"le PNG fait {w}x{h}, le modele attend "
                     f"{ico.width}x{ico.height}")
        ico.ecrire_rgba(rgba)
        pathlib.Path(argv[4]).write_bytes(
            bytes(oead.yaz0.compress(bytes(ico.raw))))
        print("ecrit :", argv[4], f"({len(ico.raw)} octets avant Yaz0)")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
