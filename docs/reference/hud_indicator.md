# Archipelago connection indicator in the HUD

The Archipelago logo at the bottom right of the HUD, beside the minimap: **in color** while the client is connected to the Archipelago
server, **grey** otherwise (no client, connection lost, reconnecting). It hides with the rest of the HUD (menus,
cutscenes).

## How it works

```
Bootup.pack > Layout/Common.sblarc
  blyt/MainScreen_00.bflyt     the HUD: RootPane > N_All_00 > ... > Pa_Time_00
                                                            > Pa_APStatus_00  (added)
  blyt/PaAPStatus_00.bflyt     our layout: RootPane > P_APOffline_00 (grey, visible)
                                                    > P_APOnline_00  (color, hidden)
  timg/Nt_APOffline_00^l.bflim / Nt_APOnline_00^l.bflim   the two logos, 64x64
```

1. **Resources** (`botw_patch/hud_layout.py`, called by `tools/build_resources_from_source.py` for every pack):
   - a part `Pa_APStatus_00` is added as the last child of `N_All_00`, the node that holds the whole HUD, so it
     inherits its visibility;
   - it points to the layout `PaAPStatus_00`, built from the vanilla layout `PaIconChallenge_00` (one picture, one
     material, one texture), with two pictures and two textures;
   - the grey logo is visible by default: without a client, nothing is connected.
2. **Client** (`botw_client/hud_indicator.py`, called by the runtime at most twice a second):
   - it finds our two pictures in memory: UI manager at `0x1047E650`, its screen table, each screen's layout, the
     pane tree, the pane name at `+0x80`;
   - it writes the visible bit (`+0x44`, bit 0) of each picture according to `ap.connected`. It writes only when the
     state changes, and checks the names before writing: when a load has rebuilt the screen, it looks the panes up
     again (at most every 2 s);
   - when the client stops cleanly, it sets the logo back to grey.
3. The names shared by both sides are in `botw_client/hud_protocol.py`.

No code hook and no per-frame write: one byte is written when the state changes. The game never rewrites these bits
(measured over 10 s in the HUD screen, `0x25`).

## Changing the settings

Everything is at the top of `botw_patch/hud_layout.py`:

| Setting | Constant | Current value |
|---|---|---|
| Position (center of the logo, 1280×720 frame, origin at the center of the screen, y up) | `POSITION` | `(609.0, -302.0)`: bottom right, beside the minimap |
| Displayed size (pixels of the 1280×720 frame) | `SIZE` | `26.4` |
| Texture resolution (an integer divisor of 512) | `TEXTURE_SIZE` | `64` |
| Grey of the offline logo (0 = black, 1 = light grey) | `dim` parameter of `grey()` | `0.55` |
| Parent in the HUD | `PARENT_LAST` (the part is inserted after this sibling) | `Pa_Time_00`, under `N_All_00` |

Useful landmarks: the hearts are around (-434, 310), the champions' abilities at x = -557 (y from 40 to 190), the
temperature gauge around (392, -222), the noise meter at (392, -262), the clock at (342, -279). The minimap is not
in this layout (it is `AppMap_00`, placed by the game's code): its place is found by eye.

**Placing it live**: `lab/tools/cemu/hud_place.py` (laboratory) moves and resizes the logo in a running game and
prints the values to write here. Measured: the pane keeps its translation at `+0x1c`, its scale at `+0x34`, its flags
at `+0x44`, and its global matrix at `+0x48`, which the game recomputes only when bit `0x10` of the flags is up.

**Changing the logo**: both textures are made from `assets/wiiu/Item_AP.sbitemico` (the project's 512 px logo, also
used for the item icon in windows and shops). Changing this file changes them all. Its digest is checked by
`tools/build_resource_base_from_source.py` (`ICON_SHA256`) and by `tests/test_resource_base_from_source.py`, to be
updated with it.

**After a change**:

```bat
venv\Scripts\python -m unittest tests.test_hud_layout tests.test_hud_indicator
venv\Scripts\python tools\play_seed.py <seed.zip>
```

The reference digests of `tests/test_resources_from_source.py` and `tests/test_pack_from_source.py` change with the
resources: update them (see [development](../development.md#reproducible-builds)).

## The loading screen icon

The loading screen (`blyt/FadeStatus_00.bflyt`, the same archive) shows, under `N_ParamInOut_00`, one icon per freed
Divine Beast and the Master Cycle Zero. Every Archipelago pack adds the Archipelago logo left of the cycle, as a black
silhouette in the style of those icons ([`botw_patch/loading_icon.py`](../../botw_patch/loading_icon.py)).

- What the game does (read in its code: the screen's setup at `0x02f99510`, its update at `0x02f999d4`): the parts
  `Pa_Ancient_00` to `03` sit at x = 564, 484, 404, 324 and `Pa_DLC_00` at x = 200 (y = 117). Each freed beast makes
  the next slot visible, from `Pa_Ancient_00` on the right, with that beast's picture (so their order follows the
  player's); the other slots are hidden, and the cycle shows once owned. No icon is ever moved: with two beasts, the
  row already has a gap before the cycle.
- The part `Pa_AP_00` is added after `Pa_Ancient_00`, modelled on `Pa_DLC_00` (visible, alpha inherited from its
  parent, so it fades in and out with the others). It is always visible: only Archipelago packs have it. It points
  to `PaFadeIconAP_00`, one picture built from `PaIconChallenge_00` like the HUD's, and its texture
  `Nt_APFade_00^l`, 128×128.
- The silhouette is made at build time from `assets/wiiu/Item_AP.sbitemico`: black, with the pixels lighter than
  their surroundings (the symbols) cut out, then cleaned of the marble's speckles. Integer arithmetic, so every
  machine builds the same texture.

| Setting | Constant | Current value |
|---|---|---|
| Position (center, same frame as above) | `POSITION` | `(144.0, 113.0)`: left of the cycle, above the screen's line |
| Displayed size | `SIZE` | `54.0` |
| Texture resolution | `TEXTURE_SIZE` | `128` |
| Silhouette: how much lighter a pixel must be to be cut out (grey levels), blur radius | `CUT_DELTA`, `BLUR_RADIUS` | `30`, `12` |

Tested by `tests/test_loading_icon.py`.

## Format details (measured)

- FLYT and FLIM 5.2, big-endian. A section is a magic, a size (8-byte header included) and a body. Byte-for-byte round
  trip checked on the 330 `.bflyt` files of `Common.sblarc`.
- Pane block: flags (bit 0 visible), origin, alpha, part scale, name[24], user data[8], translation at `+0x24` of the
  body, size at `+0x44`. Picture: material index at `+0x5c`. Part: property count, magnification, layout name.
  Material: name[28], black and white colors (the template is tinted yellow, ours is not), texture index at `+0x28`.
- `^l` textures are FLIM format 20 (RGBA8 sRGB), tile mode 4, with the GX2 tiling of `tools/bitemico.py`. Width
  rounded up to 32, height to 16. Checked on the 8 vanilla textures of this format.
- Size: `Layout/Common.blarc` grows from 31,418,128 to 31,459,088 bytes (the real growth, added to the vanilla
  margin of the size table).

Alternatives set aside: repurposing an existing HUD part (the player would lose its information), and drawing with a
render hook (native code where resources suffice).
