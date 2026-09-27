"""Read and make a Wii U item icon (.sbitemico).

    python tools/bitemico.py --extract Item_SkyviewEgg.sbitemico egg.png
    python tools/bitemico.py --replace template.sbitemico logo.png Item_AP.sbitemico
    python tools/bitemico.py --info template.sbitemico

WHY THIS FILE MATTERS

The engine builds the path `UI/StockItem/%s.bitemico` itself from the ACTOR
NAME, falling back to `UI/StockItem/NoImage.bitemico` (strings found in the RPX
at 0x1025deec and 0x1021d8ac). A file with that name is therefore enough to
give an item its icon: a content change, not a code change.

The base game ships NONE: the icons of ordinary items are rendered from their
model. `UI/StockItem/` is the override path, the one Waikuteru's randomizer
uses for the items it adds.

THE FORMAT, measured on the randomizer's Item_SkyviewEgg.sbitemico

    Yaz0 -> BFRES 'FRES' v3.5 big-endian, a single FTEX block:
        96 x 96, 1 mip, format 0x41a = TCS_R8_G8_B8_A8_SRGB (uncompressed RGBA8)
        tileMode 4 (2D tiled thin1), swizzle 0xd0000, pitch 96
        imageSize 0x9000 = 96*96*4, exactly

The image has the same size as raw pixels and as stored bytes: its data can be
replaced IN PLACE, without moving a single offset of the BFRES.

THE TILING

Wii U textures are not linear: a pixel's address goes through AddrLib (pipes,
banks, 8x8 micro tiles). `addr_macro_tiled()` ports it for our case: 2D tiled,
no bank swapping, no multisampling. The SAME function works both ways:
extracting builds the permutation, replacing applies it in reverse. If the
extracted image is right, so is the rewrite.

Check: `--extract` on one of the randomizer's icons must give a recognizable
image. It is the only check that counts.
"""
import pathlib
import struct
import sys
import zlib

# --- AddrLib, Wii U constants (R600 family) -------------------------------
M_BANKS = 4
M_BANKS_BITS = 2
M_PIPES = 2
M_PIPES_BITS = 1
M_GROUP_BITS = 8          # pipeInterleaveBytes = 256


def pixel_index_micro_tile(x, y, bpp):
    """Position of the pixel in its 8x8 micro tile. bpp=32 only."""
    if bpp != 32:
        raise NotImplementedError("only RGBA8 (32 bpp) is supported")
    b0 = x & 1
    b1 = (x & 2) >> 1
    b2 = y & 1
    b3 = (x & 4) >> 2
    b4 = (y & 2) >> 1
    b5 = (y & 4) >> 2
    return b0 | (b1 << 1) | (b2 << 2) | (b3 << 3) | (b4 << 4) | (b5 << 5)


def addr_macro_tiled(x, y, bpp, pitch, height, tile_mode,
                     pipe_swizzle=0, bank_swizzle=0):
    """Byte where pixel (x, y) lives. 2D tiled thin1, 1 sample, 1 slice."""
    micro_tile_bits = bpp * 64                       # thickness 1
    pixel_index = pixel_index_micro_tile(x, y, bpp)
    elem_offset = (bpp * pixel_index + 7) // 8

    pipe = ((y >> 3) ^ (x >> 3)) & 1
    bank_bit0 = ((y // (16 * M_PIPES)) ^ (x >> 3)) & 1
    bank_bit1 = ((y // (8 * M_PIPES)) ^ (x >> 4)) & 1
    bank = bank_bit0 | (bank_bit1 << 1)

    # rotation: m_pipes * ((m_banks >> 1) - 1) for modes 4 to 11
    rotation = M_PIPES * ((M_BANKS >> 1) - 1) if 4 <= tile_mode <= 11 else 0
    swizzle = pipe_swizzle + M_PIPES * bank_swizzle
    bank_pipe = (pipe + M_PIPES * bank) ^ swizzle          # slice 0
    bank_pipe %= M_PIPES * M_BANKS
    pipe, bank = bank_pipe % M_PIPES, bank_pipe // M_PIPES
    del rotation                                            # zero in slice 0

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


# --- BFRES: find the FTEX block and its data ------------------------------

class Icon:
    def __init__(self, raw):
        self.raw = bytearray(raw)
        o = self.raw.find(b"FTEX")
        if o < 0:
            raise SystemExit("no FTEX block in this BFRES")
        self.ftex = o
        f = struct.unpack_from(">16I", self.raw, o + 4)
        (self.dim, self.width, self.height, self.depth, self.mips, self.format, self.aa,
         self.use, self.image_size, _ptr, self.mip_size, _mptr, self.tile_mode,
         self.swizzle, self.align, self.pitch) = f
        # the offset to the pixels is a word of the FTEX block; it is found
        # again by looking for the only aligned block of image_size bytes.
        self.data_off = self._find_data()

    def _find_data(self):
        """The pixels are the last aligned block of image_size bytes."""
        n = len(self.raw)
        if n < self.image_size:
            raise SystemExit("file shorter than imageSize")
        candidate = (n - self.image_size) & ~(self.align - 1)
        # check: the block must fit entirely in the file
        while candidate > 0 and candidate + self.image_size > n:
            candidate -= self.align
        return candidate

    def info(self):
        return (f"{self.width}x{self.height}  mips={self.mips}  format={self.format:#x}  "
                f"tileMode={self.tile_mode}  swizzle={self.swizzle:#x}  pitch={self.pitch}  "
                f"imageSize={self.image_size:#x}  pixels @{self.data_off:#x}")

    def _check(self):
        if self.format != 0x41A:
            raise SystemExit(f"format {self.format:#x} not supported (expected 0x41a, RGBA8)")
        if self.tile_mode != 4:
            raise SystemExit(f"tileMode {self.tile_mode} not supported (expected 4)")
        # imageSize is computed on the PITCH, not on the width: the pitch is
        # rounded up to a multiple of 32 (144 wide -> pitch 160 on
        # Weapon_Sword_100). Checking against the width rejected those icons.
        if self.image_size != self.pitch * self.height * 4:
            raise SystemExit(f"imageSize {self.image_size:#x} does not match "
                             f"pitch*height*4 ({self.pitch * self.height * 4:#x})")

    def table(self):
        """[(linear index, tiled address)] for every pixel."""
        ps = (self.swizzle >> 8) & 1
        bs = (self.swizzle >> 9) & 3
        return [(4 * (y * self.width + x),
                 addr_macro_tiled(x, y, 32, self.pitch, self.height, self.tile_mode, ps, bs))
                for y in range(self.height) for x in range(self.width)]

    def read_rgba(self):
        self._check()
        d, out = self.raw, bytearray(self.width * self.height * 4)
        for linear, address in self.table():
            out[linear:linear + 4] = d[self.data_off + address: self.data_off + address + 4]
        return bytes(out)

    def write_rgba(self, rgba):
        self._check()
        if len(rgba) != self.width * self.height * 4:
            raise SystemExit(f"{self.width}x{self.height} RGBA pixels needed, "
                             f"got {len(rgba) // 4} pixels")
        for linear, address in self.table():
            self.raw[self.data_off + address: self.data_off + address + 4] = rgba[linear:linear + 4]


# --- minimal PNG (RGBA8, not interlaced) ----------------------------------

def write_png(path, w, h, rgba):
    raw = b"".join(b"\x00" + rgba[y * w * 4:(y + 1) * w * 4] for y in range(h))
    def chunk(kind, data):
        c = kind + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    pathlib.Path(path).write_bytes(png)


def read_png(path):
    d = pathlib.Path(path).read_bytes()
    if d[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{path} is not a PNG")
    idat, w = b"", None
    o = 8
    while o < len(d):
        n, kind = struct.unpack_from(">I4s", d, o)
        body = d[o + 8:o + 8 + n]
        if kind == b"IHDR":
            w, h, depth, colour, _compression, _filter, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or colour != 6:
                raise SystemExit("an 8-bit RGBA PNG is needed (colour type 6, depth 8)")
            if interlace:
                raise SystemExit("interlaced PNG not supported")
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
        o += 12 + n
    if w is None:
        raise SystemExit("PNG without IHDR")
    return w, h, _unfilter(zlib.decompress(idat), w, h)


def _unfilter(raw, w, h):
    """The five PNG filters. bpp = 4 for RGBA8."""
    bpp, line = 4, w * 4
    out = bytearray()
    previous = bytearray(line)
    o = 0
    for _ in range(h):
        f = raw[o]
        o += 1
        cur = bytearray(raw[o:o + line])
        o += line
        for i in range(line):
            a = cur[i - bpp] if i >= bpp else 0
            b = previous[i]
            c = previous[i - bpp] if i >= bpp else 0
            if f == 1:   cur[i] = (cur[i] + a) & 0xFF
            elif f == 2: cur[i] = (cur[i] + b) & 0xFF
            elif f == 3: cur[i] = (cur[i] + (a + b) // 2) & 0xFF
            elif f == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                cur[i] = (cur[i] + pred) & 0xFF
            elif f:
                raise SystemExit(f"unknown PNG filter {f}")
        out += cur
        previous = cur
    return bytes(out)


# --- .sbitemico in and out ------------------------------------------------

def _oead():
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    import oead
    return oead


def load(path):
    oead = _oead()
    d = pathlib.Path(path).read_bytes()
    return Icon(oead.yaz0.decompress(d) if d[:4] == b"Yaz0" else d)


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    mode = argv[1]
    if mode == "--info":
        print(load(argv[2]).info())
    elif mode == "--extract":
        icon = load(argv[2])
        print(icon.info())
        write_png(argv[3], icon.width, icon.height, icon.read_rgba())
        print("written:", argv[3])
    elif mode == "--replace":
        oead = _oead()
        icon = load(argv[2])
        w, h, rgba = read_png(argv[3])
        if (w, h) != (icon.width, icon.height):
            sys.exit(f"the PNG is {w}x{h}, the template expects "
                     f"{icon.width}x{icon.height}")
        icon.write_rgba(rgba)
        pathlib.Path(argv[4]).write_bytes(
            bytes(oead.yaz0.compress(bytes(icon.raw))))
        print("written:", argv[4], f"({len(icon.raw)} bytes before Yaz0)")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
