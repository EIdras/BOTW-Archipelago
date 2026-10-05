"""The game's interface textures (BFLIM, Wii U), decoded: icons for the tracker.

The layouts' textures are in Pack/Bootup.pack > Layout/Common.sblarc > timg/*.bflim.
A Wii U BFLIM is the image data, then a 0x28-byte footer: "FLIM" and an "imag"
block (width, height, alignment, format, then a byte with the tile mode in its
5 low bits and the GX2 swizzle >> 8 in its 3 high ones, then the image size).
The pitch is not stored: it is AddrLib's alignment for the tile mode (1D tiled
thin1, mode 2: 8 micro tiles wide at least; 2D tiled thin1, mode 4: a macro
tile of 32 x 16 elements, wider for small elements). Many of these icons are
masks the game colours itself (one or two channels): they come out white.
"""
from __future__ import annotations

from pathlib import Path
import struct
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.bitemico import addr_macro_tiled  # noqa: E402

ARCHIVE = "Layout/Common.sblarc"            # inside Pack/Bootup.pack
# FLIM formats: (bits per element, 4x4 blocks).
FORMATS = {1: ("A8", 8, False), 3: ("LA8", 16, False), 9: ("RGBA8", 32, False),
           12: ("BC1", 64, True), 14: ("BC3", 128, True), 15: ("BC4L", 64, True),
           16: ("BC4A", 64, True), 17: ("BC5", 128, True), 20: ("RGBA8", 32, False),
           21: ("BC1", 64, True), 23: ("BC3", 128, True)}


def footer(data: bytes) -> dict:
    flim = data[-0x28:]
    if flim[:4] != b"FLIM" or flim[0x14:0x18] != b"imag":
        raise ValueError("not a Wii U BFLIM")
    _size, width, height, _align, fmt, packed, size = struct.unpack(">IHHHBBI", flim[0x18:0x2C])
    return {"width": width, "height": height, "format": fmt, "tile": packed & 0x1F,
            "swizzle": packed >> 5, "size": size}


def _micro_index(x, y, bpp):
    """AddrLib's position of an element in its 8x8 micro tile (thin)."""
    if bpp == 8:
        bits = (x & 1, (x >> 1) & 1, (x >> 2) & 1, (y >> 1) & 1, y & 1, (y >> 2) & 1)
    elif bpp == 16:
        bits = (x & 1, (x >> 1) & 1, (x >> 2) & 1, y & 1, (y >> 1) & 1, (y >> 2) & 1)
    elif bpp == 32:
        bits = (x & 1, (x >> 1) & 1, y & 1, (x >> 2) & 1, (y >> 1) & 1, (y >> 2) & 1)
    elif bpp == 64:
        bits = (x & 1, y & 1, (x >> 1) & 1, (x >> 2) & 1, (y >> 1) & 1, (y >> 2) & 1)
    elif bpp == 128:
        bits = (y & 1, x & 1, (x >> 1) & 1, (x >> 2) & 1, (y >> 1) & 1, (y >> 2) & 1)
    else:
        raise ValueError(f"{bpp} bits per element")
    return sum(bit << index for index, bit in enumerate(bits))


def _align(value: int, step: int) -> int:
    return (value + step - 1) // step * step


def addresses(columns: int, rows: int, bpp: int, tile: int, swizzle: int) -> np.ndarray:
    """Byte offset of each element (rows, columns)."""
    y, x = np.mgrid[0:rows, 0:columns]
    if tile == 2:                                   # 1D tiled thin1
        pitch = _align(columns, max(8, 256 // bpp))
        micro = 64 * bpp // 8
        return ((bpp * _micro_index(x & 7, y & 7, bpp)) // 8
                + micro * ((x >> 3) + (y >> 3) * (pitch >> 3)))
    if tile == 4:                                   # 2D tiled thin1
        pitch = _align(columns, max(32, 32 * (256 // bpp // 8)))
        height = _align(rows, 16)
        if bpp in (32, 64):
            return addr_macro_tiled(x, y, bpp, pitch, height, 4, swizzle & 1, (swizzle >> 1) & 3)
        return _macro_tiled(x, y, bpp, pitch, swizzle & 1, (swizzle >> 1) & 3)
    raise ValueError(f"tile mode {tile}")


def _macro_tiled(x, y, bpp, pitch, pipe_swizzle, bank_swizzle):
    """tools/bitemico.addr_macro_tiled for the element sizes it does not take."""
    pipes, banks, group_bits = 2, 4, 8
    elem = (bpp * _micro_index(x & 7, y & 7, bpp)) // 8
    pipe = ((y >> 3) ^ (x >> 3)) & 1
    bank = (((y // 32) ^ (x >> 3)) & 1) | ((((y // 16) ^ (x >> 4)) & 1) << 1)
    bank_pipe = ((pipe + pipes * bank) ^ (pipe_swizzle + pipes * bank_swizzle)) % (pipes * banks)
    pipe, bank = bank_pipe % pipes, bank_pipe // pipes
    macro_bytes = bpp * 16 * 32 // 8
    offset = ((x // 32) + (pitch // 32) * (y // 16)) * macro_bytes
    total = elem + (offset >> 3)
    mask = (1 << group_bits) - 1
    return (bank << 9) | (pipe << 8) | (total & mask) | ((total & ~mask) << 3)


def _bc4(blocks: np.ndarray) -> np.ndarray:
    """(rows, columns, 8) -> (rows*4, columns*4) values."""
    words = blocks.astype(np.int32)
    r0, r1 = words[..., 0], words[..., 1]
    bits = np.zeros(blocks.shape[:2], dtype=np.uint64)
    for index in range(6):
        bits |= blocks[..., 2 + index].astype(np.uint64) << np.uint64(8 * index)
    palette = [r0, r1]
    six = r0 > r1
    for step in range(1, 7):
        palette.append(np.where(six, ((7 - step) * r0 + step * r1) // 7,
                                ((5 - step) * r0 + step * r1) // 5 if step < 5 else 0))
    palette[6] = np.where(six, palette[6], 0)
    palette[7] = np.where(six, palette[7], 255)
    palette = np.stack(palette, 2)
    rows, columns = blocks.shape[:2]
    out = np.zeros((rows * 4, columns * 4), dtype=np.uint8)
    for py in range(4):
        for px in range(4):
            index = ((bits >> np.uint64(3 * (py * 4 + px))) & np.uint64(7)).astype(np.int64)
            out[py::4, px::4] = np.take_along_axis(palette, index[..., None], 2)[..., 0]
    return out


def _bc1_colours(blocks: np.ndarray) -> np.ndarray:
    from tools.maptex import decode_bc1
    return decode_bc1(blocks)


def decode(data: bytes) -> np.ndarray:
    """A BFLIM as RGBA (height, width, 4)."""
    info = footer(data)
    name, bpp, block = FORMATS.get(info["format"], (None, 0, False))
    if name is None:
        raise ValueError(f"format {info['format']} not supported")
    width, height = info["width"], info["height"]
    columns, rows = ((width + 3) // 4, (height + 3) // 4) if block else (width, height)
    raw = np.frombuffer(data[:info["size"]], dtype=np.uint8)
    size = bpp // 8
    elements = raw[addresses(columns, rows, bpp, info["tile"], info["swizzle"])[..., None]
                   + np.arange(size)]
    rgba = np.zeros((rows * (4 if block else 1), columns * (4 if block else 1), 4), dtype=np.uint8)
    if name == "A8":
        rgba[..., :3], rgba[..., 3] = 255, elements[..., 0]
    elif name == "LA8":
        rgba[..., :3] = elements[..., 0:1]
        rgba[..., 3] = elements[..., 1]
    elif name == "RGBA8":
        rgba[:] = elements
    elif name == "BC1":
        rgba[..., :3], rgba[..., 3] = _bc1_colours(elements), 255
    elif name == "BC3":
        rgba[..., :3] = _bc1_colours(elements[..., 8:])
        rgba[..., 3] = _bc4(elements[..., :8])
    elif name == "BC4A":
        rgba[..., :3], rgba[..., 3] = 255, _bc4(elements)
    elif name == "BC4L":
        rgba[..., :3], rgba[..., 3] = _bc4(elements)[..., None], 255
    elif name == "BC5":
        rgba[..., :3] = _bc4(elements[..., :8])[..., None]
        rgba[..., 3] = _bc4(elements[..., 8:])
    return rgba[:height, :width]


def textures(content: Path) -> dict[str, bytes]:
    """{name without folder and extension: BFLIM} of the common layout archive."""
    import oead
    from botw_patch.resources import unpack
    boot = oead.Sarc(unpack((Path(content) / "Pack/Bootup.pack").read_bytes()))
    common = oead.Sarc(unpack(bytes(boot.get_file(ARCHIVE).data)))
    return {Path(member.name).name[:-len(".bflim")]: bytes(member.data)
            for member in common.get_files() if member.name.startswith("timg/")}
