# The Archipelago item's 3D model

The model of the Archipelago item is built on amber's (`Item_Ore_F`): its skeleton, material and shaders are kept,
its mesh and textures are replaced. It becomes the file `Model/AP_Item` of the pack; the game's amber keeps its own.
It is shown in Beedle's shops and on the village stalls.

It is a jewel made of the logo (`game/preview.png`, about 1,200 triangles, 59 cm wide and 52 cm high): the six
pieces as cut gems, engraved on both faces, set in gold and held by bent arms between a crystal and a spiked ring. It
stands on its origin, so that it reads from a stall's counter as from the ground.

## Folders (`assets/models/ap_item/`)

| Folder | Content | Rule |
|---|---|---|
| root | `reference.webp` (the logo), `build_ap_item.py` | the source |
| `game/` | what is imported into Switch Toolbox: `ap_item.fbx`, 5 PNG textures, `ap_item.blend` | made by `build_ap_item.py` |
| `wiiu/` | the exports: `AP_Item.sbfres`, `AP_Item.Tex1.sbfres`, `AP_Item.Tex2.sbfres` | what the game uses |

Amber's files (`Model/Item_Ore_F.sbfres`, `.Tex1`, `.Tex2`, in the base game) are not provided: they are game files.
To rebuild the model, extract copies from your own game. Building the pack does not need them: it only keeps their
digests (`MODEL_REFERENCE`, in `botw_patch/shops.py`).

## The three rules

1. **Meters, Y up, standing on the origin.** Blender writes its FBX files in centimeters: exported with the defaults,
   the 59 cm jewel becomes 59 m wide in the game. `game/ap_item.fbx` is already right (scale 0.01, axes converted
   in the vertices, y from 0 to 0.516). By hand in Blender: *Export → FBX*, "Selected Objects", **Scale 0.01**,
   **Apply Transform** checked, and the bottom of the object at z = 0.
2. **Textures at the original's dimensions.** A 512 px texture in place of a 256 px one keeps the original's mipmap
   sizes: the game shows garbage (orange rings, grey stains) and Switch Toolbox crashes when displaying it. Amber's
   sizes: `_Alb` 256, `_Bright_Alb` 128, `_Nrm` 128, `_Emm` 128, `_Spm` 64.
3. **Replace all 5 textures, in Tex1 and in Tex2.** Otherwise amber's relief, reflections and glow apply to the
   jewel. `game/` provides its own: `_Nrm` grooves the engravings, `_Spm` makes the gems and the crystal shine, `_Emm`
   makes them glow a little in their colour (how strongly the game's shader shows each is checked in the game).

## Rebuilding the model

1. Source: edit `reference.webp`, then rebuild `game/` with Blender in the background, without a window (the output
   folder must contain `reference.webp`):

   ```
   blender --background --factory-startup --python assets\models\ap_item\build_ap_item.py -- assets\models\ap_item\game
   ```

2. **Switch Toolbox**, on **copies** of amber's files:
   - `Item_Ore_F.sbfres`: *Models → Item_Ore_F → Meshes*, right-click the mesh → *Replace* → `game/ap_item.fbx`; keep
     the original material and format, **scale 1** in the import window;
   - `Item_Ore_F.Tex1.sbfres`, then `Item_Ore_F.Tex2.sbfres`: *Textures*, right-click → *Replace* for each one:
     `_Alb` ← `ap_item_albedo.png`, `_Bright_Alb` ← `ap_item_Bright_Alb.png`, `_Nrm` ← `ap_item_Nrm.png`,
     `_Emm` ← `ap_item_Emm.png`, `_Spm` ← `ap_item_Spm.png`; the suggested format, generated mipmaps;
   - save into `wiiu/` as `AP_Item.sbfres`, `AP_Item.Tex1.sbfres`, `AP_Item.Tex2.sbfres`. Do not rename the textures
     or the model **inside** the files: the material looks them up by these names.
3. **The shops' icon**, the jewel's render (`game/ap_item_icon.png`, 512 px) in the project's icon format; the HUD and
   the "Archipelago" key item keep the logo (`assets/wiiu/Item_AP.sbitemico`):

   ```
   venv\Scripts\python tools\bitemico.py --replace assets\wiiu\Item_AP.sbitemico assets\models\ap_item\game\ap_item_icon.png assets\wiiu\Item_AP_Jewel.sbitemico --pitch 512
   ```

4. **Check without starting the game**: building the resources checks the model (`botw_patch.shop_items.check_model`),
   for example with `venv\Scripts\python -m unittest tests.test_resources_from_source`. It refuses, with the reason: a
   format or model name different from amber's, a texture whose layout (dimensions, mipmaps, data sizes) is not the
   original's, Tex1 and Tex2 that disagree, a model outside 10 cm – 1 m, or one that goes below its origin.
5. **Test** in a seed with shops or stalls.

## Internal names: renamed automatically

A BFRES file carries its own name, its model's and its textures', whatever the file's name. Left as `Item_Ore_F`,
they make the game show **amber's textures** on the medallion, even though Switch Toolbox shows the right ones. The
build therefore renames them `AP_Item_00` (same length: no offset moves) in the three files, then checks that the game
finds every name in its lookup tables. The game's files become `Model/AP_Item_00.*`. **Nothing to do in Switch
Toolbox**: keep amber's names and export to `wiiu/AP_Item*.sbfres`.

Lookup tables (checked on amber and `TitleBG.pack`): a bit tree, references decreasing from the root, bit `ref & 7`
(least significant first) of byte `ref >> 3` counted from the start of the name; a single-entry table tests the
highest set bit of the name. Renaming amber to `AP_Item_00` and back to `Item_Ore_F` gives the original file back,
byte for byte.

## Known differences written by Switch Toolbox (accepted)

Seen on the five textures after saving with the tool:

- `Tex2` is saved with an image size of 0: that file only carries the mipmaps (the image is in `Tex1`, as the
  original's size shows). Accepted by the check, noted `toolbox_tex2_image_size_zero`;
- `Tex1`: a different swizzle parameter (`0x20000` → `0xf0000` for `_Alb`), an encoding choice of the tool,
  consistent with its data.

Neither has a visible effect in the game. The model's position when held in Link's hands is off; it does not matter,
since a bought Archipelago item is removed from the pouch at once and is never held in normal play.
