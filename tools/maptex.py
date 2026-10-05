"""The game's map, from the player's own files: UI/MapTex/MainField of the base game.

Each map section (Z, A..K x 0..9, 1000 x 1000 world units each, the MainField
spanning x -6000..6000 and z -5000..5000) is a Yaz0 BFRES with one Wii U
texture: BC1 (format 0x431), tile mode 4 (2D tiled thin1, tools/bitemico.py
for the addressing). Four layers: MapTex (2000 px a section), MapTex1 (560),
MapTex2 (200), MapTex3 (90). A section also has variants (suffixes _0, _16...,
other states of the place); the plain name is used. Nothing of the game goes
into the repository: the tracker pack builds its map from these files.
"""
from __future__ import annotations

from pathlib import Path
import struct
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from botw_patch.resources import unpack  # noqa: E402
from tools.bitemico import addr_macro_tiled, write_png  # noqa: E402

COLUMNS = "ZABCDEFGHIJK"
ROWS = 10
SECTION = 1000                  # world units
ORIGIN = (-6000.0, -5000.0)     # world x, z of the map's top-left corner
BC1 = 0x31                      # low byte of the GX2 format (0x431: sRGB)
FOLDER = "UI/MapTex/MainField"


def surface(raw: bytes) -> dict:
    at = raw.find(b"FTEX")
    if at < 0:
        raise ValueError("no FTEX block")
    (_dim, width, height, _depth, _mips, fmt, _aa, _use, size, _ptr, _msize, _mptr,
     tile, swizzle, _align, pitch) = struct.unpack(">16I", raw[at + 4:at + 68])
    # BFRES v4: the image's offset is relative, at FTEX + 0xB0.
    data = at + 0xB0 + struct.unpack(">i", raw[at + 0xB0:at + 0xB4])[0]
    if fmt & 0xFF != BC1 or tile != 4:
        raise ValueError(f"unsupported texture: format {fmt:#x}, tile mode {tile}")
    return {"width": width, "height": height, "pitch": pitch, "swizzle": swizzle,
            "data": raw[data:data + size]}


def bc1_blocks(texture: dict) -> np.ndarray:
    """The 8-byte BC1 blocks in raster order: (rows, columns, 8)."""
    columns, rows = (texture["width"] + 3) // 4, (texture["height"] + 3) // 4
    y, x = np.mgrid[0:rows, 0:columns]
    swizzle = texture["swizzle"]
    address = addr_macro_tiled(x, y, 64, texture["pitch"], rows, 4,
                               (swizzle >> 8) & 1, (swizzle >> 9) & 3)
    data = np.frombuffer(texture["data"], dtype=np.uint8)
    return data[address[..., None] + np.arange(8)]


def _rgb565(value: np.ndarray) -> np.ndarray:
    r, g, b = (value >> 11) & 31, (value >> 5) & 63, value & 31
    return np.stack([r * 255 // 31, g * 255 // 63, b * 255 // 31], -1).astype(np.int32)


def decode_bc1(blocks: np.ndarray) -> np.ndarray:
    rows, columns, _ = blocks.shape
    words = blocks.astype(np.uint32)
    c0 = words[..., 0] | words[..., 1] << 8
    c1 = words[..., 2] | words[..., 3] << 8
    bits = words[..., 4] | words[..., 5] << 8 | words[..., 6] << 16 | words[..., 7] << 24
    p0, p1 = _rgb565(c0), _rgb565(c1)
    four = (c0 > c1)[..., None]
    p2 = np.where(four, (2 * p0 + p1) // 3, (p0 + p1) // 2)
    # The 3-colour blocks' fourth entry is transparent: the mean colour instead.
    p3 = np.where(four, (p0 + 2 * p1) // 3, (p0 + p1) // 2)
    palette = np.stack([p0, p1, p2, p3], 2)
    image = np.zeros((rows * 4, columns * 4, 3), dtype=np.uint8)
    for py in range(4):
        for px in range(4):
            index = (bits >> (2 * (py * 4 + px))) & 3
            image[py::4, px::4] = np.take_along_axis(
                palette, index[..., None, None].repeat(3, -1), 2)[:, :, 0]
    return image


def decode(raw: bytes) -> np.ndarray:
    texture = surface(unpack(raw))
    return decode_bc1(bc1_blocks(texture))[:texture["height"], :texture["width"]]


def assemble(content: Path, layer: str = "MapTex2") -> np.ndarray:
    """The whole map from one layer, sections side by side (RGB)."""
    tiles = {}
    for column, letter in enumerate(COLUMNS):
        for row in range(ROWS):
            path = Path(content) / FOLDER / f"{layer}_{letter}-{row}.sbmaptex"
            tiles[column, row] = decode(path.read_bytes())
    size = tiles[0, 0].shape[0]
    image = np.zeros((ROWS * size, len(COLUMNS) * size, 3), dtype=np.uint8)
    for (column, row), tile in tiles.items():
        image[row * size:(row + 1) * size, column * size:(column + 1) * size] = tile
    return image


def pixel(x: float, z: float, scale: float) -> tuple[int, int]:
    """Map pixel of a world position, `scale` pixels per world unit."""
    return round((x - ORIGIN[0]) * scale), round((z - ORIGIN[1]) * scale)


def save_png(image: np.ndarray, path: Path) -> None:
    height, width, _ = image.shape
    alpha = np.full((height, width, 1), 255, dtype=np.uint8)
    write_png(path, width, height, np.concatenate([image, alpha], 2).tobytes())
