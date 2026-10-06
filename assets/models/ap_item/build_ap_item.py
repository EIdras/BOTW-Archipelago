"""Build the Archipelago item model from its reference image, headless.

    blender --background --factory-startup --python build_ap_item.py -- <folder>

A jewel made of the logo: its six pieces, cut out of reference.webp, become cut
gems (a crown of facets and a flat table, on both sides) set in gold, held by
six bent arms between a small crystal at the centre and a ring with spikes. It
stands on its origin, its faces towards the actor's front and back, so that it
reads from a stall's counter as from the ground.

The texture is one atlas (the template's 256 px): a cell per piece, painted in
the piece's own colour (lighter in the middle) with its engraving, sampled from
the full-size reference (the outline band and the paint's scratches left out;
the yellow piece, scratched over its drawing, takes its mirror twin's, the green
one: the logo is symmetric); a band below with the gold and the crystal. Each
face of a gem is projected
flat onto its cell, so the engraving runs from facet to facet nearly to the
edge. The companions: _Nrm grooves the engraving, _Spm makes the gems and the
crystal shine, _Emm makes them glow a little in their colour.

Outputs, in <folder>: ap_item.blend, ap_item.fbx, ap_item_albedo.png (256 px),
ap_item_{Bright_Alb,Nrm,Spm,Emm}.png at the template's sizes, preview.png, and
ap_item_icon.png (512 px, transparent), the shops' icon.
The FBX is written in metres, standing on its origin, ready for Switch Toolbox.
"""
import colorsys
import math
import os
import sys

import bmesh
import bpy
import numpy as np

FOLDER = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
REFERENCE = os.path.join(FOLDER, "reference.webp")
GRID = 256                  # cut-out resolution, cells across the image
WIDTH = 0.30                # metres, the logo's size (the ring and spikes come around it)
TEXTURE = 256               # the texture of the template (amber) is 256 px: same layout, same mipmaps
OUTLINE_POINTS = 32         # at most, per piece, from the cut-out
MATERIAL = "Mt_Body"        # the template material (amber), so Switch Toolbox matches it by name

# The jewel (metres). A gem: its outline (12 points) at RIM from the middle
# plane, its crown at CROWN of the outline and CROWN_Z, its table at TABLE and
# TABLE_Z; the same on the back.
GEM_POINTS = 12
RIM, CROWN, CROWN_Z, TABLE, TABLE_Z = 0.005, 0.87, 0.022, 0.66, 0.032
RING_SEGMENTS = 24
SCALE = 1.5                 # the whole jewel, measured on a stall: smaller, it was lost among the goods
SPIKES = ((0.034, 0.0085), (0.027, 0.0075))      # (length, half width), long and short in turn

# The atlas: a band of BAND rows below (gold, crystal), then
# 3 x 2 cells of CELL px, one per piece.
BAND, CELL, MARGIN, SUPERSAMPLE = 16, (85, 120), 2, 4
GOLD, CRYSTAL = (0.98, 0.74, 0.22), (0.82, 0.93, 1.0)
ENGRAVING = (1.0, 0.94, 0.74)
GLOW = 0.12                 # emission, of the gems' and the engraving's colour (0.3 was too much in the game)
GOLD_UV, CRYSTAL_UV = (8 / TEXTURE, 8 / TEXTURE), (24 / TEXTURE, 8 / TEXTURE)
# The engraving's colour in the reference, and how far from it a pixel may be.
LINE_COLOUR, LINE_DISTANCE = (0.88, 0.745, 0.46), 0.16
# The template's other textures: name suffix -> size in px.
COMPANIONS = {"Bright_Alb": 128, "Nrm": 128, "Spm": 64, "Emm": 128}
ICON = 512                  # px, the size of the project's icon file


def load_reference():
    image = bpy.data.images.load(REFERENCE)
    w, h = image.size
    pixels = np.array(image.pixels[:], dtype=np.float32).reshape(h, w, 4)
    return image, pixels


def dilate(m):
    out = m.copy()
    out[1:] |= m[:-1]; out[:-1] |= m[1:]; out[:, 1:] |= m[:, :-1]; out[:, :-1] |= m[:, 1:]
    return out


def erode(m):
    return ~dilate(~m)


def repeat(step, m, times):
    for _ in range(times):
        m = step(m)
    return m


def box_count(m, k):
    """Number of set pixels in the k x k window around each pixel."""
    p = np.pad(m.astype(np.int32), k // 2)
    c = np.pad(p.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    return c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]


def piece_mask(pixels):
    rgb, alpha = pixels[..., :3], pixels[..., 3]
    mask = (alpha > 0.5) & (rgb.min(axis=2) < 0.90)
    return erode(dilate(mask)), rgb


def cells(mask):
    h, w = mask.shape
    size = max(w, h) / GRID
    nx, ny = int(w / size), int(h / size)
    keep = np.zeros((ny, nx), dtype=bool)
    for j in range(ny):
        for i in range(nx):
            block = mask[int(j * size):int((j + 1) * size), int(i * size):int((i + 1) * size)]
            keep[j, i] = block.mean() > 0.5
    return keep, size, w, h


def build_mesh(keep, size, w, h):
    """The pieces' outlines, in metres, centred on the image's middle."""
    ny, nx = keep.shape
    bm = bmesh.new()
    verts = {}
    scale = WIDTH / max(w, h)

    def vert(i, j):
        if (i, j) not in verts:
            x, y = i * size, j * size          # image space, rows from the bottom
            verts[(i, j)] = bm.verts.new(((x - w / 2) * scale, (y - h / 2) * scale, 0.0))
        return verts[(i, j)]

    for j in range(ny):
        for i in range(nx):
            if keep[j, i]:
                bm.faces.new((vert(i, j), vert(i + 1, j), vert(i + 1, j + 1), vert(i, j + 1)))
    bm.verts.ensure_lookup_table()
    # soften the staircase of the cut-out: smooth the outline only, in plane
    for _ in range(12):
        boundary = [v for v in bm.verts if v.is_boundary]
        bmesh.ops.smooth_vert(bm, verts=boundary, factor=0.5,
                              use_axis_x=True, use_axis_y=True, use_axis_z=False)
    bmesh.ops.dissolve_faces(bm, faces=list(bm.faces))
    outlines = [np.array([(v.co.x, v.co.y) for v in face.verts]) for face in bm.faces]
    bm.free()
    return [simplify(outline) for outline in outlines], scale


def douglas_peucker(points, eps):
    """Indices kept on an open polyline."""
    keep, stack = {0, len(points) - 1}, [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, ab, seg = points[i], points[j] - points[i], points[i + 1:j]
        n = np.linalg.norm(ab)
        d = (np.abs(np.cross(ab, seg - a)) / n) if n > 1e-12 else np.linalg.norm(seg - a, axis=1)
        k = int(np.argmax(d))
        if d[k] > eps:
            keep.add(i + 1 + k)
            stack += [(i, i + 1 + k), (i + 1 + k, j)]
    return sorted(keep)


def simplify(loop):
    """Fewest outline points keeping the shape (corners stay): Douglas-Peucker
    on the two halves of the closed loop, tolerance raised until OUTLINE_POINTS."""
    loop = np.roll(loop, -int(np.argmax(np.linalg.norm(loop - loop.mean(axis=0), axis=1))), axis=0)
    far = int(np.argmax(np.linalg.norm(loop - loop[0], axis=1)))
    eps = 0.0003
    while True:
        first = douglas_peucker(loop[:far + 1], eps)
        second = [(far + k) % len(loop)
                  for k in douglas_peucker(np.vstack([loop[far:], loop[:1]]), eps)]
        kept = sorted(set(first) | set(second))
        if len(kept) <= OUTLINE_POINTS:
            pts = loop[kept]
            area = np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1])
            return pts if area > 0 else pts[::-1]
        eps *= 1.25


def resample(pts, n):
    """n points evenly spread along a closed outline, counter-clockwise."""
    seg = np.linalg.norm(np.roll(pts, -1, axis=0) - pts, axis=1)
    cum = np.concatenate([[0], np.cumsum(seg)])
    out = []
    for t in np.linspace(0, cum[-1], n, endpoint=False):
        i = np.searchsorted(cum, t, side="right") - 1
        f = (t - cum[i]) / seg[i] if seg[i] else 0
        out.append(pts[i] + f * (pts[(i + 1) % len(pts)] - pts[i]))
    out = np.array(out)
    area = np.sum(out[:, 0] * np.roll(out[:, 1], -1) - np.roll(out[:, 0], -1) * out[:, 1])
    return out if area > 0 else out[::-1]


def inside(poly, xs, ys):
    """Points (xs, ys) inside the polygon (even-odd rule)."""
    res = np.zeros(xs.shape, bool)
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        res ^= ((y1 > ys) != (y2 > ys)) & (xs < (x2 - x1) * (ys - y1) / (y2 - y1 + 1e-12) + x1)
    return res


def hue_of(rgb):
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn + 1e-9
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6
    return h, d / (mx + 1e-9), mx


def is_yellow(hue):
    return 0.10 < hue < 0.18


def gem_colour(hue, value):
    """A clean, saturated colour of the piece's hue; yellow, a lemon-gold."""
    base = np.array((1.0, 0.86, 0.15)) if is_yellow(hue) else np.array(colorsys.hsv_to_rgb(hue, 0.82, 1.0))
    return base * value


def engravings(rgb, polys):
    """Per piece: its hue and its engraving (a mask, full size)."""
    h_, w_ = rgb.shape[:2]
    ys, xs = np.mgrid[0:h_, 0:w_] + 0.5
    hue, sat, val = hue_of(rgb)
    pale = (np.linalg.norm(rgb - np.array(LINE_COLOUR), axis=-1) < LINE_DISTANCE) & (rgb[..., 2] > 0.33)
    pieces, hues, lines = [], [], []
    for poly in polys:
        mask = inside(poly, xs, ys)
        sel = mask & ~pale & (sat > 0.3) & (val > 0.2)
        hist, edges = np.histogram(hue[sel], bins=72, range=(0, 1))
        k = int(np.argmax(hist))
        hues.append((edges[k] + edges[k + 1]) / 2)
        line = pale & repeat(erode, mask, 22)                    # the outline band left out
        line = repeat(dilate, repeat(erode, line, 3), 3)         # thin scratches go, lines stay
        lines.append(line & (box_count(line, 41) >= 220))        # lone specks go
        pieces.append(mask)
    # The yellow piece's drawing is scratched over: its mirror twin's (the logo
    # is symmetric about the image's vertical middle).
    centres = [poly.mean(axis=0) for poly in polys]
    for k, hk in enumerate(hues):
        if is_yellow(hk):
            twin = int(np.argmin([np.linalg.norm(c - (w_ - centres[k][0], centres[k][1])) for c in centres]))
            lines[k] = np.fliplr(lines[twin]) & pieces[k]
    return hues, lines


def paint(rgb, polys):
    """The atlas and its companions (TEXTURE px), and where each piece lies in it."""
    T = TEXTURE
    hues, lines = engravings(rgb, polys)
    albedo = np.zeros((T, T, 3), np.float32)
    shine, glow, depth = np.zeros_like(albedo), np.zeros_like(albedo), np.zeros((T, T), np.float32)
    places = []
    cw, ch = CELL
    for k, (poly, hue, line) in enumerate(zip(polys, hues, lines)):
        for _ in range(3):                         # the stroke's weight at the cell's scale
            line = dilate(line)
        centre_ref = poly.mean(axis=0)
        lo, hi = poly.min(axis=0), poly.max(axis=0)
        size, mid = hi - lo, (lo + hi) / 2
        upright = min((cw - 2 * MARGIN) / size[0], (ch - 2 * MARGIN) / size[1])
        turned = min((ch - 2 * MARGIN) / size[0], (cw - 2 * MARGIN) / size[1])
        rotated, s = turned > upright, max(upright, turned)
        col, row = k % 3, k // 3
        centre = np.array((col * cw + cw / 2, BAND + row * ch + ch / 2))
        place = {"rotated": rotated, "scale": s, "mid": mid, "centre": centre}
        places.append(place)
        x0, y0 = col * cw, BAND + row * ch
        ys, xs = np.mgrid[y0:y0 + ch, x0:x0 + cw]
        cover = np.zeros(xs.shape, np.float32)
        for sy in range(SUPERSAMPLE):
            for sx in range(SUPERSAMPLE):
                p = from_cell(place, np.stack([xs + (sx + 0.5) / SUPERSAMPLE, ys + (sy + 0.5) / SUPERSAMPLE], -1))
                cover += line[np.clip(p[..., 1].astype(int), 0, line.shape[0] - 1),
                              np.clip(p[..., 0].astype(int), 0, line.shape[1] - 1)]
        cover /= SUPERSAMPLE ** 2
        reach = np.linalg.norm(poly - centre_ref, axis=-1).max()
        radius = np.linalg.norm(from_cell(place, np.stack([xs + 0.5, ys + 0.5], -1)) - centre_ref, axis=-1) / reach
        colour = gem_colour(hue, 1.0) * (1.0 - 0.22 * np.clip(radius, 0, 1) ** 1.6)[..., None]
        a = cover[..., None]
        albedo[y0:y0 + ch, x0:x0 + cw] = colour * (1 - a) + np.array(ENGRAVING) * a
        shine[y0:y0 + ch, x0:x0 + cw] = 0.95 * (1 - a) + 0.55 * a
        glow[y0:y0 + ch, x0:x0 + cw] = colour * GLOW * (1 - a) + np.array(ENGRAVING) * GLOW * a
        depth[y0:y0 + ch, x0:x0 + cw] = -cover
    albedo[:BAND, :16], shine[:BAND, :16] = GOLD, 0.65
    albedo[:BAND, 16:32], shine[:BAND, 16:32], glow[:BAND, 16:32] = CRYSTAL, 1.0, np.array(CRYSTAL) * 2 * GLOW
    # the grooves: a soft depth, then its slopes (tangent space, +Z out)
    for _ in range(2):
        depth = (depth + np.roll(depth, 1, 0) + np.roll(depth, -1, 0) + np.roll(depth, 1, 1) + np.roll(depth, -1, 1)) / 5
    dx = (np.roll(depth, -1, 1) - np.roll(depth, 1, 1)) / 2
    dy = (np.roll(depth, -1, 0) - np.roll(depth, 1, 0)) / 2
    normal = np.stack([-dx * 2.5, -dy * 2.5, np.ones_like(dx)], -1)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    return {"albedo": albedo, "Spm": shine, "Emm": glow, "Nrm": normal}, places


def from_cell(place, q):
    """Atlas pixels -> reference pixels."""
    q = np.asarray(q) - place["centre"]
    if place["rotated"]:
        q = np.stack([q[..., 1], -q[..., 0]], -1)
    return place["mid"] + q / place["scale"]


def to_cell(place, p):
    """Reference pixels -> atlas UV."""
    q = (np.asarray(p) - place["mid"]) * place["scale"]
    if place["rotated"]:
        q = np.array((-q[1], q[0]))
    return (place["centre"] + q) / TEXTURE


def jewel(outlines, places, scale, w, h):
    """The jewel, lying in the XY plane, centred on the origin."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")

    def face(verts, uvs, smooth=False):
        f = bm.faces.new(verts)
        for loop, u in zip(f.loops, uvs):
            loop[uv].uv = tuple(u)
        f.smooth = smooth

    def ref(p):                                    # metres -> reference pixels
        return np.array((p[0] / scale + w / 2, p[1] / scale + h / 2))

    centres = []
    for pts, place in zip(outlines, places):
        pts = resample(pts, GEM_POINTS)
        c = pts.mean(axis=0)
        centres.append(c)
        crown, table = c + CROWN * (pts - c), c + TABLE * (pts - c)
        n = len(pts)
        rims = {}
        for sign in (1, -1):
            e = [bm.verts.new((p[0], p[1], sign * RIM)) for p in pts]
            m = [bm.verts.new((p[0], p[1], sign * CROWN_Z)) for p in crown]
            t = [bm.verts.new((p[0], p[1], sign * TABLE_Z)) for p in table]
            for i in range(n):
                j = (i + 1) % n
                for ra, rb, pa, pb in ((e, m, pts, crown), (m, t, crown, table)):
                    quad = [ra[i], ra[j], rb[j], rb[i]]
                    uvs = [to_cell(place, ref(p)) for p in (pa[i], pa[j], pb[j], pb[i])]
                    face(quad if sign > 0 else quad[::-1], uvs if sign > 0 else uvs[::-1])
            uvs = [to_cell(place, ref(p)) for p in table]
            face(t if sign > 0 else t[::-1], uvs if sign > 0 else uvs[::-1])
            rims[sign] = e
        for i in range(n):                         # the gold setting around the gem
            j = (i + 1) % n
            face([rims[1][j], rims[1][i], rims[-1][i], rims[-1][j]], [GOLD_UV] * 4, smooth=True)
    radius = max(np.linalg.norm(o, axis=1).max() for o in outlines) + 0.004
    angles = sorted(math.atan2(c[1], c[0]) for c in centres)
    gaps = [angles[k] + ((angles[(k + 1) % 6] - angles[k]) % (2 * math.pi)) / 2 for k in range(6)]
    for g in gaps:                                 # arms, tapered and bent the same way
        d = np.array((math.cos(g), math.sin(g)))
        side = np.array((-d[1], d[0]))
        rings = []
        for r, bend, hw, ht in ((0.020, 0.0, 0.0060, 0.0085), ((0.02 + radius) / 2, 0.006, 0.0045, 0.0070),
                                (radius + 0.004, 0.0, 0.0035, 0.0060)):
            p = r * d + bend * side
            rings.append([bm.verts.new((*(p + s * hw * side), z * ht)) for s, z in ((1, 0), (0, 1), (-1, 0), (0, -1))])
        for a, b in zip(rings, rings[1:]):
            for k in range(4):
                face([a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]], [GOLD_UV] * 4, smooth=True)
        face(rings[0][::-1], [GOLD_UV] * 4)
    # the crystal at the centre
    corners = {s: [bm.verts.new((0.026 * math.cos(math.pi * k / 3), 0.026 * math.sin(math.pi * k / 3), s * 0.010))
                   for k in range(6)] for s in (1, -1)}
    tips = {s: bm.verts.new((0, 0, s * 0.024)) for s in (1, -1)}
    for k in range(6):
        l = (k + 1) % 6
        face([corners[1][k], corners[-1][k], corners[-1][l], corners[1][l]], [CRYSTAL_UV] * 4)
        face([corners[1][k], corners[1][l], tips[1]], [CRYSTAL_UV] * 3)
        face([corners[-1][l], corners[-1][k], tips[-1]], [CRYSTAL_UV] * 3)
    # the ring: a diamond section, thicker where the arms hold it
    ring = []
    for k in range(RING_SEGMENTS):
        a = 2 * math.pi * k / RING_SEGMENTS
        d = np.array((math.cos(a), math.sin(a)))
        swell = max(0.0, max(math.cos((a - g + math.pi) % (2 * math.pi) - math.pi) for g in gaps)) ** 12
        wd, th = 0.006 + 0.004 * swell, 0.0065 + 0.0035 * swell
        ring.append([bm.verts.new((*(r * d), z)) for r, z in ((radius, 0), (radius + wd, th),
                                                              (radius + 2 * wd, 0), (radius + wd, -th))])
    for k in range(RING_SEGMENTS):
        a, b = ring[k], ring[(k + 1) % RING_SEGMENTS]
        for s in range(4):
            face([a[s], b[s], b[(s + 1) % 4], a[(s + 1) % 4]], [GOLD_UV] * 4, smooth=True)
    for n, g in enumerate(gaps):                   # spikes, long and short in turn
        d = np.array((math.cos(g), math.sin(g)))
        side = np.array((-d[1], d[0]))
        length, hw = SPIKES[n % 2]
        base = [bm.verts.new((*((radius + 0.016) * d + s * hw * side), z * 0.0065))
                for s, z in ((1, 0), (0, 1), (-1, 0), (0, -1))]
        tip = bm.verts.new((*((radius + 0.016 + length) * d), 0))
        for k in range(4):
            face([base[k], base[(k + 1) % 4], tip], [GOLD_UV] * 3)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method="BEAUTY", ngon_method="BEAUTY")
    return bm


def stand(bm):
    """Upright, faces along Y, resting on the origin (a BOTW item sits at y >= 0)."""
    for v in bm.verts:
        x, y, z = v.co
        v.co = (x * SCALE, -z * SCALE, y * SCALE)
    low = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= low


def save(name, data, size, non_colour=False):
    """A PNG of `data` (TEXTURE px, RGB) at `size` px, averaged down."""
    k = TEXTURE // size
    small = data.reshape(size, k, size, k, 3).mean(axis=(1, 3))
    if name.endswith("_Nrm"):
        small = small / np.linalg.norm(small, axis=-1, keepdims=True) * 0.5 + 0.5
    img = bpy.data.images.new(name, size, size, alpha=False)
    if non_colour:
        img.colorspace_settings.name = "Non-Color"     # before the pixels: it regenerates the image
    img.pixels[:] = np.concatenate([small, np.ones((size, size, 1), np.float32)], -1).astype(np.float32).ravel()
    img.filepath_raw = os.path.join(FOLDER, f"{name}.png")
    img.file_format = "PNG"
    img.save()
    return img


def material(tex):
    mat = bpy.data.materials.new(MATERIAL)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    shader = nodes.get("Principled BSDF")
    node = nodes.new("ShaderNodeTexImage")
    node.image = tex
    mat.node_tree.links.new(node.outputs["Color"], shader.inputs["Base Color"])
    shader.inputs["Roughness"].default_value = 0.2
    return mat


def icon(obj):
    """The shops' icon: the jewel from the front, on nothing (ICON px, as
    assets/wiiu/Item_AP.sbitemico; tools/bitemico.py --replace makes the icon file)."""
    scene = bpy.context.scene
    cam = bpy.data.objects.new("icon_camera", bpy.data.cameras.new("icon_camera"))
    scene.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(obj.dimensions.x, obj.dimensions.z) * 1.04
    cam.location = (0.0, -1.0, obj.dimensions.z / 2)
    cam.rotation_euler = (math.radians(90), 0.0, 0.0)
    scene.camera = cam
    # lit from the front and evenly, as the game's icons are
    fill = bpy.data.objects.new("icon_light", bpy.data.lights.new("icon_light", "SUN"))
    fill.data.energy = 2.5
    fill.rotation_euler = (math.radians(70), 0.0, math.radians(-15))
    scene.collection.objects.link(fill)
    scene.world.color = (0.75, 0.75, 0.78)
    scene.render.film_transparent = True
    scene.render.resolution_x = scene.render.resolution_y = 2 * ICON
    scene.render.filepath = os.path.join(FOLDER, "ap_item_icon_big.png")
    bpy.ops.render.render(write_still=True)
    big = bpy.data.images.load(scene.render.filepath)
    px = np.array(big.pixels[:], dtype=np.float32).reshape(2 * ICON, 2 * ICON, 4)
    small = px.reshape(ICON, 2, ICON, 2, 4).mean(axis=(1, 3))
    rgb = np.where(small[..., 3:] > 0, small[..., :3] / np.maximum(small[..., 3:], 1e-6), 0)   # unpremultiplied edges
    out = bpy.data.images.new("ap_item_icon", ICON, ICON, alpha=True)
    out.pixels[:] = np.concatenate([rgb, small[..., 3:]], -1).astype(np.float32).ravel()
    out.filepath_raw = os.path.join(FOLDER, "ap_item_icon.png")
    out.file_format = "PNG"
    out.save()
    os.remove(scene.render.filepath)
    bpy.data.objects.remove(fill)
    scene.world.color = (0.35, 0.37, 0.4)
    scene.render.film_transparent = False


def preview(obj):
    scene = bpy.context.scene
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    scene.collection.objects.link(cam)
    cam.location = (0.33, -0.99, 0.28)
    cam.rotation_euler = (math.radians(90), 0.0, math.radians(18))
    scene.camera = cam
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(50), math.radians(-20), math.radians(-30))
    scene.collection.objects.link(sun)
    scene.world = bpy.data.worlds.new("world")
    scene.world.color = (0.35, 0.37, 0.4)
    scene.view_settings.view_transform = "Standard"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = 768
    scene.render.filepath = os.path.join(FOLDER, "preview.png")
    bpy.ops.render.render(write_still=True)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image, pixels = load_reference()
    mask, rgb = piece_mask(pixels)
    keep, size, w, h = cells(mask)
    outlines, scale = build_mesh(keep, size, w, h)
    polys = [np.array([(x / scale + w / 2, y / scale + h / 2) for x, y in o]) for o in outlines]
    textures, places = paint(rgb, polys)
    bm = jewel(outlines, places, scale, w, h)
    stand(bm)
    mesh = bpy.data.meshes.new("ap_item")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("ap_item", mesh)
    bpy.context.scene.collection.objects.link(obj)
    albedo = save("ap_item_albedo", textures["albedo"], TEXTURE)
    save("ap_item_Bright_Alb", textures["albedo"], COMPANIONS["Bright_Alb"])
    save("ap_item_Nrm", textures["Nrm"], COMPANIONS["Nrm"], non_colour=True)
    save("ap_item_Spm", textures["Spm"], COMPANIONS["Spm"], non_colour=True)
    save("ap_item_Emm", textures["Emm"], COMPANIONS["Emm"])
    mesh.materials.append(material(albedo))
    preview(obj)
    icon(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    # Blender writes FBX coordinates in centimetres (x100), which Switch Toolbox
    # reads as metres; converting the axes into the vertices keeps that x100
    # even without unit scaling, so scale by 0.01. Checked on the file: metres,
    # Y up, resting on y = 0.
    bpy.ops.export_scene.fbx(filepath=os.path.join(FOLDER, "ap_item.fbx"),
                             use_selection=True, apply_unit_scale=False, global_scale=0.01,
                             # the textures are replaced by hand in Switch Toolbox: none copied
                             bake_space_transform=True, path_mode="STRIP", embed_textures=False)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(FOLDER, "ap_item.blend"))
    print("AP_ITEM", {"triangles": len(mesh.polygons), "vertices": len(mesh.vertices),
                      "outline_points": [len(o) for o in outlines],
                      "size_m": [round(d, 3) for d in obj.dimensions]})


main()
