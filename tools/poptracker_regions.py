"""The regions panel of the PopTracker pack (tools/build_poptracker.py).

A tile a region map, the tiles laid out as Hyrule, and one mini-map of Hyrule
made of a piece a region, each in three states: its map not received (grey),
received but the region out of reach with region_lock (amber, hatched), the
region reached (the game's own colours under a touch of green). Drawn from the
game's map (tools/maptex.py) and its tower areas (tools/map_regions.py): the
pack holds the images, the repository none of the game's.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

S = 4                                       # supersampling, then averaged down
TILE = (60, 50)                             # a tile, (width, height) in pixels
MINI_WIDTH = 272                            # the mini-map, as wide as the item grid
STATES = ("off", "cut", "lit")
GREEN, GREEN_LINE = np.array([90, 200, 110.]), np.array([120, 235, 140.])
AMBER, AMBER_LINE = np.array([200, 120, 60.]), np.array([235, 160, 90.])
BORDER = np.array([128, 133, 145.])
CARD = (30, 32, 38)

# The region at map pixels: lookup(xs, ys) -> array (len(ys), len(xs)) of names (None outside).
Lookup = Callable[[np.ndarray, np.ndarray], np.ndarray]


@dataclass
class Drawn:
    """The panel's images: tiles[region, state], the mini-map's background (the
    start region lit) and its pieces[region, state] = (left, top, RGBA)."""
    tiles: dict
    background: np.ndarray
    pieces: dict


def tower_areas(update: Path, scale: float, origin: tuple[float, float]) -> Lookup:
    """The region at map pixels (`scale` pixels a world unit from `origin`), from
    the tower areas of the update's MapTower.sbeco, each named after its tower."""
    from tools import map_regions

    grid = map_regions.map_towers(update)
    named = map_regions.area_regions(grid)
    rows: dict[int, tuple] = {}

    def lookup(xs, ys):
        out = np.empty((len(ys), len(xs)), dtype=object)
        columns = np.asarray(xs) / scale + origin[0] + 5000
        for i, y in enumerate(ys):
            index = max(0, min(grid.rows - 1, int((y / scale + origin[1] + 4000) / grid.divisor)))
            if index not in rows:
                segments = grid.row(index)
                rows[index] = (np.cumsum([length for _, length in segments]), [value for value, _ in segments])
            edges, values = rows[index]
            found = np.minimum(np.searchsorted(edges, columns, side="right"), len(values) - 1)
            out[i] = [named.get(values[k]) for k in found]
        return out
    return lookup


def _grow(mask: np.ndarray, n: int) -> np.ndarray:
    out = mask.copy()
    for _ in range(n):
        q = np.pad(out, 1)
        out = q[1:-1, 1:-1] | q[:-2, 1:-1] | q[2:, 1:-1] | q[1:-1, :-2] | q[1:-1, 2:]
    return out


def _borders(where: np.ndarray) -> np.ndarray:
    out = np.zeros(where.shape, dtype=bool)
    out[1:] |= where[1:] != where[:-1]
    out[:, 1:] |= where[:, 1:] != where[:, :-1]
    return out


def _rounded(w: int, h: int, radius: float) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w] + 0.5
    return np.hypot(xx - np.clip(xx, radius, w - radius), yy - np.clip(yy, radius, h - radius)) <= radius


def _view(summed: np.ndarray, lookup: Lookup, box: tuple[float, float, float, float], w: int, h: int):
    """(colours, regions) of the map's box (left, top, width, height), at w x h:
    each pixel the mean of the map's pixels it covers (summed: cumulative sums)."""
    left, top, width, height = box
    rows, columns = summed.shape[0] - 1, summed.shape[1] - 1
    xb = np.round(left + np.arange(w + 1) * width / w).astype(int).clip(0, columns)
    yb = np.round(top + np.arange(h + 1) * height / h).astype(int).clip(0, rows)
    total = (summed[yb[1:, None], xb[None, 1:]] - summed[yb[:-1, None], xb[None, 1:]]
             - summed[yb[1:, None], xb[None, :-1]] + summed[yb[:-1, None], xb[None, :-1]])
    area = np.maximum((yb[1:] - yb[:-1])[:, None] * (xb[1:] - xb[:-1])[None, :], 1)
    xs = left + (np.arange(w) + 0.5) * width / w
    ys = top + (np.arange(h) + 0.5) * height / h
    return total / area[..., None], lookup(xs, ys)


def _context(colours, where, width=2, strength=1.0):
    """The map in dark grey, the regions' borders drawn."""
    rgb = colours.mean(2, keepdims=True).repeat(3, 2) * 0.5 + 18
    lines = _grow(_borders(where), width)
    rgb[lines] = rgb[lines] * (1 - strength) + BORDER * strength
    return rgb


def _light(rgb, colours, mask, state):
    """A region in its state, with its edge inside it."""
    h, w = mask.shape
    yy, xx = np.mgrid[0:h, 0:w]
    edge = mask & _grow(~mask, S)
    if state == "cut":
        lit = colours.mean(2, keepdims=True).repeat(3, 2) * 0.45 + AMBER * 0.55
        lit = np.where(((((xx + yy) // (3 * S)) % 2) == 0)[..., None], lit * 0.6, lit)
        rgb[mask], rgb[edge] = lit[mask], AMBER_LINE
    elif state == "lit":
        lit = np.minimum(colours * 1.15, 255) * 0.82 + GREEN * 0.18
        rgb[mask], rgb[edge] = lit[mask], GREEN_LINE
    else:
        rgb[edge] = BORDER * 1.25
    return rgb


def _down(rgb, alpha, w, h) -> np.ndarray:
    """Supersampled colours and coverage (0..1) to an RGBA image of w x h."""
    rgba = np.concatenate([rgb * alpha[..., None], alpha[..., None] * 255.0], 2)
    rgba = rgba.reshape(h, S, w, S, 4).mean((1, 3))
    a = rgba[..., 3:]
    rgba[..., :3] = np.where(a > 0, rgba[..., :3] * 255 / np.maximum(a, 1e-6), 0)
    return np.clip(np.round(rgba), 0, 255).astype(np.uint8)


def _fit(box, aspect):
    """The box (left, top, width, height) grown around its centre to an aspect."""
    left, top, width, height = box
    if width / height < aspect:
        return left - (height * aspect - width) / 2, top, height * aspect, height
    return left, top - (width / aspect - height) / 2, width, width / aspect


_TW, _TH = TILE
_TILE_CARD = _rounded(_TW * S, _TH * S, 6 * S)
_yy, _xx = np.mgrid[0:_TH * S, 0:_TW * S] + 0.5
_TILE_FRAME = _TILE_CARD & (_grow(~_TILE_CARD, 2 * S) | (_xx < 2 * S) | (_xx > (_TW - 2) * S)
                            | (_yy < 2 * S) | (_yy > (_TH - 2) * S))


def _finish_tile(rgb, state) -> np.ndarray:
    """A tile's frame (green reached, amber cut off) or, not received, PopTracker's
    grey (no saturation, 67 % brightness)."""
    if state == "off":
        rgb = rgb.mean(2, keepdims=True).repeat(3, 2) * 0.67
    else:
        rgb[_TILE_FRAME] = AMBER_LINE if state == "cut" else GREEN_LINE
    return _down(rgb, _TILE_CARD.astype(float), _TW, _TH)


def draw(image: np.ndarray, lookup: Lookup, box: tuple[int, int, int, int], regions, start: str) -> Drawn:
    """The panel of the regions, and of the start region (always lit), from the
    whole map (RGB) cut to box (left, top, right, bottom)."""
    summed = np.pad(image.astype(np.float64).cumsum(0).cumsum(1), ((1, 0), (1, 0), (0, 0)))
    left, top, right, bottom = box
    whole = (left, top, right - left, bottom - top)
    colours, where = _view(summed, lookup, _fit(whole, _TW / _TH), _TW * S, _TH * S)
    tiles = {}
    for region in [*regions, start]:
        for state in (("lit",) if region == start else STATES):
            rgb = _light(_context(colours, where, 1, 0.45), colours, where == region,
                         "cut" if state == "cut" else "lit")
            tiles[region, state] = _finish_tile(rgb, state)
    width = MINI_WIDTH
    height = round(width * whole[3] / whole[2])
    colours, where = _view(summed, lookup, whole, width * S, height * S)
    card = _rounded(width * S, height * S, 8 * S)
    background = _down(_light(_context(colours, where), colours, where == start, "lit"), card.astype(float),
                       width, height)
    pieces = {}
    for region in regions:
        mask = (where == region) & card
        ys, xs = np.nonzero(mask)
        x0, y0 = xs.min() // S, ys.min() // S
        x1, y1 = -(-(xs.max() + 1) // S), -(-(ys.max() + 1) // S)
        cut = (slice(y0 * S, y1 * S), slice(x0 * S, x1 * S))
        for state in STATES:
            rgb = _light(_context(colours[cut], where[cut]), colours[cut], mask[cut], state)
            pieces[region, state] = (int(x0), int(y0), _down(rgb, mask[cut].astype(float), x1 - x0, y1 - y0))
    return Drawn(tiles, background, pieces)


def label_tile(label: np.ndarray, state: str) -> np.ndarray:
    """Without the game's map: a tile of the region's label (an RGBA icon), on a
    dark card, framed as a drawn tile."""
    rgb = np.empty((_TH * S, _TW * S, 3))
    rgb[:] = CARD
    big = label.astype(np.float64).repeat(S, 0).repeat(S, 1)
    h, w = big.shape[:2]
    y, x = (_TH * S - h) // 2, (_TW * S - w) // 2
    alpha = big[..., 3:] / 255
    rgb[y:y + h, x:x + w] = big[..., :3] * alpha + rgb[y:y + h, x:x + w] * (1 - alpha)
    return _finish_tile(rgb, state)
