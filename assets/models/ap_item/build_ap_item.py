"""Build the Archipelago item model from its reference image, headless.

    blender --background --factory-startup --python build_ap_item.py -- <folder>

The six pieces of the logo are cut out of reference.webp (everything that is
not the white background), extruded into a medallion, and textured with the
image itself on the front; the edge and the back use a gold swatch painted into
a corner of the same texture, so the model has one material and one texture,
as a BOTW item model should. Outputs, in <folder>:
  ap_item.blend, ap_item.fbx, ap_item_albedo.png (256 px), preview.png.
The FBX is written in metres, lying on its origin, ready for Switch Toolbox;
ap_item_{Bright_Alb,Nrm,Spm,Emm}.png replace the template's other textures.
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np

FOLDER = sys.argv[sys.argv.index("--") + 1]
REFERENCE = os.path.join(FOLDER, "reference.webp")
GRID = 256                  # cut-out resolution, cells across the image
WIDTH = 0.30                # metres, overall size of the medallion
THICKNESS = 0.025
TEXTURE = 256               # the texture of the template (amber) is 256 px: same layout, same mipmaps
OUTLINE_POINTS = 32       # at most, per piece: a game asset turns around in a few dozen faces
MATERIAL = "Mt_Body"       # the template material (amber), so Switch Toolbox matches it by name
SWATCH = 24                 # gold swatch, in texture pixels, bottom-left corner


def load_reference():
    image = bpy.data.images.load(REFERENCE)
    w, h = image.size
    pixels = np.array(image.pixels[:], dtype=np.float32).reshape(h, w, 4)
    return image, pixels


def piece_mask(pixels):
    rgb, alpha = pixels[..., :3], pixels[..., 3]
    mask = (alpha > 0.5) & (rgb.min(axis=2) < 0.90)
    # close small gaps, then drop isolated specks (binary shifts, no scipy)
    def dilate(m):
        out = m.copy()
        out[1:] |= m[:-1]; out[:-1] |= m[1:]; out[:, 1:] |= m[:, :-1]; out[:, :-1] |= m[:, 1:]
        return out

    def erode(m):
        return ~dilate(~m)

    return erode(dilate(mask)), rgb


def gold_colour(rgb, mask):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    gold = mask & (r > 0.75) & (g > 0.6) & (b < 0.6) & (r - b > 0.25)
    return np.median(rgb[gold], axis=0)


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
    # one face per piece: its loop is the outline of the piece
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


def medallion(outlines, scale, w, h):
    """Front face textured by the image, back and edge on the gold swatch;
    edges smooth around the rim, sharp at the front and back."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    swatch = (SWATCH / 2 / TEXTURE, SWATCH / 2 / TEXTURE)
    for pts in outlines:
        # resting on its origin, front face up: a BOTW item sits at y >= 0
        top = [bm.verts.new((x, y, THICKNESS)) for x, y in pts]
        bottom = [bm.verts.new((x, y, 0.0)) for x, y in pts]
        front, back = bm.faces.new(top), bm.faces.new(bottom[::-1])
        for loop in front.loops:
            loop[uv].uv = ((loop.vert.co.x / scale + w / 2) / w, (loop.vert.co.y / scale + h / 2) / h)
        faces = [back] + [bm.faces.new((top[(i + 1) % len(pts)], top[i], bottom[i],
                                        bottom[(i + 1) % len(pts)])) for i in range(len(pts))]
        for face in faces:
            for loop in face.loops:
                loop[uv].uv = swatch
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for edge in bm.edges:
        edge.smooth = len(edge.link_faces) == 2 and edge.calc_face_angle() < math.radians(35)
    for face in bm.faces:
        face.smooth = abs(face.normal.z) < 0.5
    bmesh.ops.triangulate(bm, faces=list(bm.faces), quad_method="BEAUTY", ngon_method="BEAUTY")
    return bm


def texture(image, gold):
    tex = bpy.data.images.new("ap_item_albedo", TEXTURE, TEXTURE, alpha=False)
    src = image.copy()
    src.scale(TEXTURE, TEXTURE)
    pixels = np.array(src.pixels[:], dtype=np.float32).reshape(TEXTURE, TEXTURE, 4)
    pixels[..., 3] = 1.0
    pixels[:SWATCH, :SWATCH, :3] = gold
    tex.pixels[:] = pixels.ravel()
    tex.filepath_raw = os.path.join(FOLDER, "ap_item_albedo.png")
    tex.file_format = "PNG"
    tex.save()
    return tex


# The template's other textures, neutral, at their original sizes, so that
# amber's relief, shine and glow do not show on the medallion:
# name suffix -> (size, RGB, from the albedo)
COMPANIONS = {"Bright_Alb": (128, None), "Nrm": (128, (0.5, 0.5, 1.0)),
              "Spm": (64, (0.0, 0.0, 0.0)), "Emm": (128, (0.0, 0.0, 0.0))}


def companion_textures(albedo):
    for suffix, (size, colour) in COMPANIONS.items():
        img = bpy.data.images.new(f"ap_item_{suffix}", size, size, alpha=False)
        if colour is None:
            src = albedo.copy()
            src.scale(size, size)
            img.pixels[:] = src.pixels[:]
        else:
            img.pixels[:] = np.tile(np.array([*colour, 1.0], dtype=np.float32), size * size)
        img.filepath_raw = os.path.join(FOLDER, f"ap_item_{suffix}.png")
        img.file_format = "PNG"
        img.save()


def material(tex):
    mat = bpy.data.materials.new(MATERIAL)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    shader = nodes.get("Principled BSDF")
    node = nodes.new("ShaderNodeTexImage")
    node.image = tex
    mat.node_tree.links.new(node.outputs["Color"], shader.inputs["Base Color"])
    shader.inputs["Roughness"].default_value = 0.55
    return mat


def preview(obj):
    scene = bpy.context.scene
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    scene.collection.objects.link(cam)
    cam.location = (0.0, -0.42, 0.20)
    cam.rotation_euler = (math.radians(66), 0.0, 0.0)
    scene.camera = cam
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(40), math.radians(-20), math.radians(20))
    scene.collection.objects.link(sun)
    scene.world = bpy.data.worlds.new("world")
    scene.world.color = (0.35, 0.37, 0.4)
    obj.rotation_euler = (math.radians(90), 0.0, 0.0)   # standing, facing the camera
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = 768
    scene.render.filepath = os.path.join(FOLDER, "preview.png")
    bpy.ops.render.render(write_still=True)
    obj.rotation_euler = (0.0, 0.0, 0.0)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    image, pixels = load_reference()
    mask, rgb = piece_mask(pixels)
    gold = gold_colour(rgb, mask)
    keep, size, w, h = cells(mask)
    outlines, scale = build_mesh(keep, size, w, h)
    bm = medallion(outlines, scale, w, h)
    mesh = bpy.data.meshes.new("ap_item")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("ap_item", mesh)
    bpy.context.scene.collection.objects.link(obj)
    albedo = texture(image, gold)
    companion_textures(albedo)
    mesh.materials.append(material(albedo))
    preview(obj)
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    # Blender writes FBX coordinates in centimetres (x100), which Switch Toolbox
    # reads as metres (a 28 m medallion); converting the axes into the
    # vertices keeps that x100 even without unit scaling, so scale by 0.01.
    # Checked on the file: metres, Y up, resting on y = 0.
    bpy.ops.export_scene.fbx(filepath=os.path.join(FOLDER, "ap_item.fbx"),
                             use_selection=True, apply_unit_scale=False, global_scale=0.01,
                             # vertices converted to Y-up (BOTW), not left to a node rotation
                             bake_space_transform=True,
                             path_mode="COPY", embed_textures=False)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(FOLDER, "ap_item.blend"))
    print("AP_ITEM", {"triangles": len(mesh.polygons), "vertices": len(mesh.vertices),
                      "outline_points": [len(o) for o in outlines],
                      "gold": [round(float(c), 3) for c in gold],
                      "size_m": [round(d, 3) for d in obj.dimensions]})


main()
