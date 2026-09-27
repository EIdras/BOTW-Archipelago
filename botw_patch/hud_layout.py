"""The AP connection indicator of the HUD: layout resources (docs/reference/
hud_indicator.md).

The HUD is Bootup.pack > Layout/Common.sblarc > blyt/MainScreen_00.bflyt, a
set of 21 parts. One more part, Pa_APStatus_00, is placed under N_All_00 (it
hides with the rest of the HUD), bottom left, and points to a layout of its
own, PaAPStatus_00:
  * two pictures of the Archipelago logo: P_APOffline_00 (grey, visible by
    default: with no client, nothing is connected) and P_APOnline_00 (in
    colour, hidden). The client swaps their visible bits when the connection
    changes; the game's HUD code does not know these panes and leaves them;
  * built from the vanilla PaIconChallenge_00 (one picture, one material,
    one texture), the smallest layout of the same shape;
  * two RGBA8 sRGB textures (the ^l format of the vanilla Nt_KeySmall_00),
    made from the project's 512 px logo, assets/wiiu/Item_AP.sbitemico.

Formats read from the files (FLYT/FLIM 5.2, big endian): a section is a
magic, a size including its 8-byte header, and a body. Pane block (pan1, pic1,
prt1): flags (bit 0 visible), origin, alpha, part scale, name[24],
user data[8], translation (3 floats) at +0x2c, rotation, scale, size (2
floats) at +0x4c. A picture then has 4 vertex colours, its material index
(u16) at +0x64 and texture coordinates; a part has a property count, a
magnification and the part layout name. A material has its name[28], black
and white colours, flags, then its texture maps (texture index u16 at +0x38).
"""
from __future__ import annotations

import struct
from pathlib import Path

from botw_client.hud_protocol import OFFLINE, ONLINE, PART_LAYOUT, PART_PANE
from tools.bitemico import addr_macro_tiled     # the measured GX2 tiling

ROOT = Path(__file__).resolve().parents[1]

ARCHIVE = "Layout/Common.sblarc"            # inside Pack/Bootup.pack
SCREEN = "blyt/MainScreen_00.bflyt"
TEMPLATE = "blyt/PaIconChallenge_00.bflyt"
PARENT_LAST = "Pa_Time_00"                  # last child of N_All_00
TEXTURES = {ONLINE: "Nt_APOnline_00^l.bflim", OFFLINE: "Nt_APOffline_00^l.bflim"}
POSITION = (-590.0, -310.0)                 # bottom left of the 1280x720 HUD
SIZE = 44.0
TEXTURE_SIZE = 64
FORMAT_RGBA8_SRGB = 20                      # FLIM format of the ^l textures
TILE_MODE, SWIZZLE = 4, 2                   # as Nt_KeySmall_00^l (flags 0x44)
PANE_BLOCK = 0x54                           # section header + pane block


# --- FLYT container ------------------------------------------------------------

def read_layout(raw: bytes) -> tuple[bytes, list[tuple[bytes, bytes]]]:
    if raw[:4] != b"FLYT" or raw[4:6] != b"\xfe\xff":
        raise ValueError("pas un FLYT gros-boutiste")
    header_size = struct.unpack_from(">H", raw, 6)[0]
    size, count = struct.unpack_from(">IH", raw, 0x0c)
    if size != len(raw):
        raise ValueError("taille de FLYT incohérente")
    out, offset = [], header_size
    for _ in range(count):
        magic = raw[offset:offset + 4]
        length = struct.unpack_from(">I", raw, offset + 4)[0]
        out.append((magic, raw[offset + 8:offset + length]))
        offset += length
    if offset != len(raw):
        raise ValueError("sections de FLYT incomplètes")
    return raw[:header_size], out


def write_layout(header: bytes, sections: list[tuple[bytes, bytes]]) -> bytes:
    body = b"".join(magic + struct.pack(">I", len(data) + 8) + data
                    for magic, data in sections)
    out = bytearray(header + body)
    struct.pack_into(">IH", out, 0x0c, len(out), len(sections))
    return bytes(out)


def _name(text: str, size: int) -> bytes:
    raw = text.encode("ascii")
    if len(raw) >= size:
        raise ValueError(f"nom trop long : {text}")
    return raw + b"\0" * (size - len(raw))


def _string(text: str) -> bytes:
    raw = text.encode("ascii") + b"\0"
    return raw + b"\0" * (-len(raw) % 4)


def pane_name(data: bytes) -> str:
    return data[4:28].split(b"\0")[0].decode("ascii")


def _pane(data: bytes, name: str | None = None, *, visible: bool | None = None,
          position: tuple[float, float] | None = None,
          size: tuple[float, float] | None = None) -> bytes:
    """A pane block (section body) with some fields replaced."""
    out = bytearray(data)
    if name is not None:
        out[4:28] = _name(name, 24)
    if visible is not None:
        out[0] = (out[0] | 1) if visible else (out[0] & ~1)
    if position is not None:
        struct.pack_into(">ff", out, 0x24, *position)
    if size is not None:
        struct.pack_into(">ff", out, 0x44, *size)
    return bytes(out)


# --- the part layout -----------------------------------------------------------

def part_layout(template: bytes) -> bytes:
    """PaAPStatus_00: RootPane > [P_APOffline_00 (visible), P_APOnline_00]."""
    header, sections = read_layout(template)
    kinds = [magic for magic, _ in sections]
    if kinds != [b"lyt1", b"txl1", b"mat1", b"pan1", b"pas1", b"pic1", b"pae1",
                 b"grp1", b"cnt1"]:
        raise ValueError(f"modèle de layout inattendu : {kinds}")
    parts = dict(sections)

    lyt = parts[b"lyt1"]
    lyt1 = lyt[:4] + lyt[4:12] + struct.pack(">ff", SIZE, SIZE) + _string(PART_LAYOUT)

    names = [TEXTURES[OFFLINE], TEXTURES[ONLINE]]
    strings = [n.encode("ascii") + b"\0" for n in names]
    table, offset = b"", 4 * len(names)
    for raw in strings:
        table += struct.pack(">I", offset)
        offset += len(raw)
    txl = struct.pack(">HH", len(names), 0) + table + b"".join(strings)
    txl1 = txl + b"\0" * (-len(txl) % 4)

    mat = parts[b"mat1"]
    count, first = struct.unpack_from(">H", mat, 0)[0], struct.unpack_from(">I", mat, 4)[0]
    if count != 1 or first != 0x10:
        raise ValueError("matériau du modèle inattendu")
    material = bytearray(mat[first - 8:])
    if len(material) != 0x48 or struct.unpack_from(">I", material, 0x24)[0] != 0x15:
        raise ValueError("matériau du modèle inattendu")
    material[0x1c:0x24] = b"\0\0\0\0\xff\xff\xff\xff"    # no tint (the model is yellow)
    materials = []
    for index, name in enumerate((OFFLINE, ONLINE)):
        entry = bytearray(material)
        entry[:0x1c] = _name(name, 0x1c)
        struct.pack_into(">H", entry, 0x28, index)       # texture map 0: texture index
        materials.append(bytes(entry))
    # Offsets from the section start: header, count, then the offset table.
    first = 8 + 4 + 4 * len(materials)
    mat1 = (struct.pack(">HH", len(materials), 0)
            + struct.pack(">II", first, first + len(materials[0])) + b"".join(materials))

    root = _pane(parts[b"pan1"], size=(SIZE, SIZE))
    picture = parts[b"pic1"]
    if struct.unpack_from(">H", picture, 0x5c)[0] != 0:
        raise ValueError("image du modèle inattendue")
    pictures = []
    for index, name in enumerate((OFFLINE, ONLINE)):
        entry = bytearray(_pane(picture, name, visible=(name == OFFLINE), size=(SIZE, SIZE)))
        struct.pack_into(">H", entry, 0x5c, index)       # material index
        pictures.append((b"pic1", bytes(entry)))

    out = [(b"lyt1", lyt1), (b"txl1", txl1), (b"mat1", mat1), (b"pan1", root),
           (b"pas1", b""), *pictures, (b"pae1", b""), (b"grp1", parts[b"grp1"])]
    return write_layout(header, out)


# --- the HUD screen ------------------------------------------------------------

def add_part(screen: bytes) -> tuple[bytes, dict]:
    """MainScreen_00 with Pa_APStatus_00 after the last child of N_All_00."""
    header, sections = read_layout(screen)
    names = [pane_name(data) if magic in (b"pan1", b"prt1", b"pic1") else None
             for magic, data in sections]
    if PART_PANE in names:
        raise ValueError(f"{PART_PANE} déjà présent")
    model = next(data for (magic, data), name in zip(sections, names)
                 if magic == b"prt1" and name == "Pa_Weather_00")
    # A part with no property: pane block, count 0, magnification, layout name.
    if len(model) != PANE_BLOCK - 8 + 12 + 16 or struct.unpack_from(">I", model, 0x4c)[0]:
        raise ValueError("part modèle inattendue")
    last = names.index(PARENT_LAST)
    if sections[last + 1][0] != b"pae1":
        raise ValueError(f"{PARENT_LAST} n'est plus le dernier enfant de son parent")
    part = (_pane(model[:0x4c], PART_PANE, visible=True, position=POSITION,
                  size=(SIZE, SIZE)) + model[0x4c:0x58] + _string(PART_LAYOUT))
    sections = sections[:last + 1] + [(b"prt1", part)] + sections[last + 1:]
    return write_layout(header, sections), {"part": PART_PANE, "layout": PART_LAYOUT,
                                           "after": PARENT_LAST, "position": POSITION}


# --- textures ------------------------------------------------------------------

def _padded(value: int, step: int = 32) -> int:
    return (value + step - 1) // step * step


# Macro tile of tile mode 4 at 32 bpp: 32 pixels wide (8 x 4 banks), 16 rows
# (8 x 2 pipes). Measured on the 8 vanilla ^l textures: 36x36 is 64x48.
MACRO_WIDTH, MACRO_HEIGHT = 32, 16


def read_flim(raw: bytes) -> tuple[int, int, bytes]:
    """(width, height, RGBA8 rows) of an RGBA8 sRGB tile-mode-4 texture."""
    imag = len(raw) - 0x14
    if raw[-0x28:-0x24] != b"FLIM" or raw[imag:imag + 4] != b"imag":
        raise ValueError("pas un FLIM")
    width, height, _align = struct.unpack_from(">HHH", raw, imag + 8)
    fmt, flags = raw[imag + 14], raw[imag + 15]
    if fmt != FORMAT_RGBA8_SRGB or flags & 0x1f != TILE_MODE:
        raise ValueError(f"format {fmt}/{flags:#x} non géré")
    swizzle = flags >> 5
    pitch, rows = _padded(width, MACRO_WIDTH), _padded(height, MACRO_HEIGHT)
    out = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            at = addr_macro_tiled(x, y, 32, pitch, rows, TILE_MODE, swizzle & 1, swizzle >> 1)
            out[4 * (y * width + x):4 * (y * width + x) + 4] = raw[at:at + 4]
    return width, height, bytes(out)


def write_flim(width: int, height: int, rgba: bytes, swizzle: int = SWIZZLE) -> bytes:
    if len(rgba) != width * height * 4:
        raise ValueError("pixels RGBA incomplets")
    pitch, rows = _padded(width, MACRO_WIDTH), _padded(height, MACRO_HEIGHT)
    image = bytearray(pitch * rows * 4)
    for y in range(height):
        for x in range(width):
            at = addr_macro_tiled(x, y, 32, pitch, rows, TILE_MODE, swizzle & 1, swizzle >> 1)
            image[at:at + 4] = rgba[4 * (y * width + x):4 * (y * width + x) + 4]
    footer = (b"FLIM\xfe\xff" + struct.pack(">HIIHH", 0x14, 0x05020000,
                                             len(image) + 0x28, 1, 0)
              + b"imag" + struct.pack(">IHHHBBI", 0x10, width, height, 0x800,
                                      FORMAT_RGBA8_SRGB, TILE_MODE | swizzle << 5, len(image)))
    return bytes(image) + footer


def logo_rgba(icon_raw: bytes) -> tuple[int, int, bytes]:
    """The 512 px logo of the project icon (its header says pitch 96, the
    pixels are laid out with the width as pitch: measured when the logo was
    found, 25/09)."""
    from tools.bitemico import Icone
    import oead
    icon = Icone(oead.yaz0.decompress(icon_raw) if icon_raw[:4] == b"Yaz0" else icon_raw)
    icon.pitch = icon.width
    return icon.width, icon.height, icon.lire_rgba()


def shrink(width: int, height: int, rgba: bytes, size: int) -> bytes:
    """Box filter, alpha weighted (no dark fringe on transparent edges)."""
    step = width // size
    if step * size != width or width != height:
        raise ValueError("réduction entière d'une image carrée seulement")
    out = bytearray(size * size * 4)
    for y in range(size):
        for x in range(size):
            r = g = b = a = 0
            for yy in range(y * step, (y + 1) * step):
                row = yy * width
                for xx in range(x * step, (x + 1) * step):
                    p = 4 * (row + xx)
                    alpha = rgba[p + 3]
                    r += rgba[p] * alpha
                    g += rgba[p + 1] * alpha
                    b += rgba[p + 2] * alpha
                    a += alpha
            at = 4 * (y * size + x)
            if a:
                out[at:at + 4] = bytes((r // a, g // a, b // a, a // (step * step)))
    return bytes(out)


def grey(rgba: bytes, dim: float = 0.55) -> bytes:
    """The offline logo: desaturated and darker, same shape and alpha."""
    out = bytearray(rgba)
    for p in range(0, len(out), 4):
        level = int((0.299 * out[p] + 0.587 * out[p + 1] + 0.114 * out[p + 2]) * dim)
        out[p:p + 3] = bytes((level, level, level))
    return bytes(out)


def textures(icon_raw: bytes) -> dict[str, bytes]:
    width, height, rgba = logo_rgba(icon_raw)
    small = shrink(width, height, rgba, TEXTURE_SIZE)
    return {f"timg/{TEXTURES[ONLINE]}": write_flim(TEXTURE_SIZE, TEXTURE_SIZE, small),
            f"timg/{TEXTURES[OFFLINE]}": write_flim(TEXTURE_SIZE, TEXTURE_SIZE, grey(small))}


def patch_archive(raw_sarc: bytes, icon_raw: bytes) -> tuple[bytes, dict]:
    """Common.sblarc (decompressed SARC) with the indicator added."""
    import oead
    archive = oead.Sarc(raw_sarc)
    writer = oead.SarcWriter.from_sarc(archive)
    added = [f"blyt/{PART_LAYOUT}.bflyt", *(f"timg/{t}" for t in TEXTURES.values())]
    if any(archive.get_file(name) is not None for name in added):
        raise ValueError("indicateur déjà présent dans l'archive")
    screen, detail = add_part(bytes(archive.get_file(SCREEN).data))
    writer.files[SCREEN] = screen
    writer.files[f"blyt/{PART_LAYOUT}.bflyt"] = part_layout(bytes(archive.get_file(TEMPLATE).data))
    for name, raw in textures(icon_raw).items():
        writer.files[name] = raw
    return bytes(writer.write()[1]), {**detail, "added": added}
