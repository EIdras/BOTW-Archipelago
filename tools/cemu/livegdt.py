"""Lire et ecrire les flags GameData que le jeu consulte REELLEMENT, a chaud.

Il existe deux stockages pour un meme flag :

  * un tableau d'entrees de 8 octets `{hash, valeur}`, celui que gdt_index.py
    localise. La sauvegarde le serialise, mais le moteur ne le consulte pas en
    cours de partie. Y ecrire ne produit un effet qu'apres un rechargement.

  * les objets de flag vivants, atteints depuis le singleton GameDataMgr. C'est
    ce que lisent les getters du jeu. Une ecriture brute ici est volatile :
    elle contourne l'enregistrement des changements par les setters natifs.
    Le test du 8 septembre 2026 confirme que les flags AP ainsi modifies
    restent a zero sur disque apres sauvegarde. Ne pas utiliser cette methode
    comme preuve de livraison persistante.

Chaine d'acces, etablie par desassemblage puis verifiee en memoire :

    *(0x1046D5B0)          -> GameDataMgr
    mgr->0x710             -> pointeur
    *(mgr->0x710)          -> TriggerParam
    TriggerParam->0x04     -> nombre de bools
    TriggerParam->0x0C     -> tableau de POINTEURS (4 octets chacun)
    tableau[index]         -> objet de flag, 16 octets

Objet de flag :

    +0x00  pointeur partage (identique pour tous les flags)
    +0x04  proprietes sur les 16 bits hauts, VALEUR sur les 16 bits bas
           -> l'octet de poids faible du booleen est donc a +0x07
    +0x08  hash
    +0x0C  0

Usage :

    python tools/cemu/livegdt.py IsGet_Obj_IceMaker          # lire
    python tools/cemu/livegdt.py IsGet_Obj_IceMaker 1 --write # ecrire
    python tools/cemu/livegdt.py CurrentHart --watch          # changements
"""
import pathlib
import struct
import sys
import time
import zlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from winmem import Process
from mailbox import be, cemu_pid, find_cave, guest_base
from gdt_index import load_flags

GDT_MGR_PTR = 0x1046D5B0

# Ces flags appartiennent au mod et ne figurent donc pas dans l'index extrait
# du jeu vanilla. Ils deviennent visibles après installation du Bootup.pack AP
# et un redémarrage complet de Cemu.
CUSTOM_FLAGS = {
    "APReceivedCursor": (zlib.crc32(b"APReceivedCursor") & 0xFFFFFFFF, "s32"),
    "APSeedToken": (zlib.crc32(b"APSeedToken") & 0xFFFFFFFF, "s32"),
}

# Wii U 1.5.0. TriggerParam begins with a u32 then one 12-byte PtrArray per
# scalar type.  The bool offsets below are the layout measured in game.  S32
# and F32 are the immediately following arrays; their Flag<T> layout follows
# the same prefix, with {initial, min, max, value, hash} starting at +0x08.
# S32/F32 offsets were first identified from the type layout, then instrumented
# on 2026-08-25: MaxHartValue=12, StaminaMax=1000.0, KorokNutsNum=1 and
# CurrentRupee=0 were read, rewritten unchanged, and read back identically.
# Their *memory layout* is verified; the visible effect of a changed value is a
# separate acceptance test and remains labelled as such in item_map.json.
TYPE_LAYOUT = {
    "bool": {"count": 0x04, "array": 0x0C, "size": 0x10,
             "value": 0x07, "hash": 0x08},
    "s32":  {"count": 0x10, "array": 0x18, "size": 0x20,
             "value": 0x14, "hash": 0x18},
    "f32":  {"count": 0x1C, "array": 0x24, "size": 0x20,
             "value": 0x14, "hash": 0x18},
}


def read_u32(p, address, label):
    raw = p.read(address, 4)
    if raw is None or len(raw) != 4:
        raise RuntimeError(f"lecture mémoire impossible : {label}")
    return be(raw)


class LiveGdt:
    """Index (type, hash) -> adresse invitee de l'objet de flag vivant."""

    def __init__(self, p, base):
        self.p = p
        self.base = base
        mgr = read_u32(p, base + GDT_MGR_PTR, "GameDataMgr")
        if not (0x10000000 <= mgr < 0x60000000):
            raise RuntimeError(f"GameDataMgr invalide ({mgr:#010x}) - partie chargee ?")
        self.mgr = mgr
        tp_ptr = read_u32(p, base + mgr + 0x710, "pointeur TriggerParam")
        self.tp = read_u32(p, base + tp_ptr, "TriggerParam")
        self.index = {kind: {} for kind in TYPE_LAYOUT}

    def build(self, kinds=("bool", "s32", "f32")):
        """Lire les tableaux de pointeurs des types scalaires demandes."""
        total = 0
        for kind in kinds:
            layout = TYPE_LAYOUT[kind]
            count = read_u32(
                self.p, self.base + self.tp + layout["count"],
                f"compte {kind}")
            array = read_u32(
                self.p, self.base + self.tp + layout["array"],
                f"tableau {kind}")
            if not count or not (0x10000000 <= array < 0x60000000):
                continue
            raw = self.p.read(self.base + array, count * 4)
            if not raw or len(raw) != count * 4:
                continue
            ptrs = struct.unpack(f">{count}I", raw)
            valid = [q for q in ptrs if 0x10000000 <= q < 0x60000000]
            if not valid:
                continue
            low, high = min(valid), max(valid) + layout["size"]
            blob = self.p.read(self.base + low, high - low) if (
                high - low < 64 << 20) else None
            for q in valid:
                offset = q - low + layout["hash"]
                hraw = (blob[offset:offset + 4] if blob is not None
                        else self.p.read(self.base + q + layout["hash"], 4))
                if hraw is not None and len(hraw) == 4:
                    self.index[kind].setdefault(be(hraw), q)
            total += len(self.index[kind])
        return total

    def get(self, hash_u32, kind="bool"):
        """Lire une valeur scalaire dans l'objet vivant.

        Pour un bool, le bit 0 seul est la valeur. Pour s32/f32, la valeur est
        le mot a +0x14 dans le Flag<T> Wii U.
        """
        layout = TYPE_LAYOUT[kind]
        a = self.index[kind].get(hash_u32)
        if a is None:
            return None
        raw = self.p.read(self.base + a + layout["value"], 1 if kind == "bool" else 4)
        if not raw:
            return None
        if kind == "bool":
            return raw[0] & 1
        if kind == "s32":
            return struct.unpack(">i", raw)[0]
        return struct.unpack(">f", raw)[0]

    def set(self, hash_u32, value, kind="bool"):
        """Ecriture brute en memoire, sans garantie de persistance ni setter natif."""
        layout = TYPE_LAYOUT[kind]
        a = self.index[kind].get(hash_u32)
        if a is None:
            return False
        addr = self.base + a + layout["value"]
        if kind == "bool":
            current = self.p.read(addr, 1)
            if not current:
                return False
            cur = current[0]
            data = bytes([(cur & 0xFE) | (1 if value else 0)])
        elif kind == "s32":
            data = struct.pack(">i", int(value))
        else:
            data = struct.pack(">f", float(value))
        return self.p.write(addr, data)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    flag = args[0]
    value = float(args[1]) if len(args) > 1 and "." in args[1] else (
        int(args[1]) if len(args) > 1 else None)
    do_write = "--write" in sys.argv

    pid = cemu_pid()
    if not pid:
        sys.exit("Cemu n'est pas lance")
    _, type_of, hash_of = load_flags()
    custom = CUSTOM_FLAGS.get(flag)
    h = custom[0] if custom else hash_of.get(flag)
    if h is None:
        sys.exit(f"flag inconnu : {flag}")

    with Process(pid, writable=do_write) as p:
        cave = find_cave(p)
        if cave is None:
            sys.exit("code cave introuvable - le graphic pack est-il actif ?")
        base, _, _ = guest_base(p, cave - 12)
        g = LiveGdt(p, base)
        n = g.build()
        print(f"TriggerParam {g.tp:#010x}, {n} indexes scalaires")

        kind = custom[1] if custom else type_of.get(h)
        if kind not in TYPE_LAYOUT:
            sys.exit(f"type {kind} non gere (bool, s32 et f32 seulement)")
        cur = g.get(h, kind)
        if cur is None:
            sys.exit(f"{flag} absent du tableau vivant "
                     f"(type {kind})")
        obj = g.index[kind][h]
        value_address = obj + TYPE_LAYOUT[kind]["value"]
        print(f"{flag} = {cur}   objet {obj:#010x}   valeur {value_address:#010x}")

        if "--watch" in sys.argv:
            print("surveillance a 20 Hz ; Ctrl+C pour arreter")
            started = time.monotonic()
            previous = cur
            try:
                while True:
                    time.sleep(0.05)
                    current = g.get(h, kind)
                    if current != previous:
                        elapsed = time.monotonic() - started
                        print(f"{elapsed:9.3f}s  {flag}: {previous} -> {current}",
                              flush=True)
                        previous = current
            except KeyboardInterrupt:
                print("arrete")
            return

        if value is None or not do_write:
            if value is not None:
                print("\nessai a blanc - ajoute --write pour appliquer")
            return
        g.set(h, value, kind)
        print(f"-> {g.get(h, kind)}")


if __name__ == "__main__":
    main()
