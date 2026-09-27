# Archipelago connection indicator in the HUD

The Archipelago logo at the bottom left of the HUD: **in color** while the client is connected to the Archipelago
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
| Position (center of the logo, 1280×720 frame, origin at the center of the screen, y up) | `POSITION` | `(-590.0, -310.0)`: bottom left |
| Displayed size (pixels of the 1280×720 frame) | `SIZE` | `44.0` |
| Texture resolution (an integer divisor of 512) | `TEXTURE_SIZE` | `64` |
| Grey of the offline logo (0 = black, 1 = light grey) | `dim` parameter of `grey()` | `0.55` |
| Parent in the HUD | `PARENT_LAST` (the part is inserted after this sibling) | `Pa_Time_00`, under `N_All_00` |

Useful landmarks: the hearts are around (-434, 310), the champions' abilities at x = -557 (y from 40 to 190), the
temperature gauge around (392, -222).

**Changing the logo**: both textures are made from `assets/wiiu/Item_AP.sbitemico` (the project's 512 px logo, also
used for the item icon in windows and shops). Changing this file changes them all. Its digest is checked by
`tools/build_resource_base_from_source.py` (`ICON_SHA256`) and by `tests/test_resource_base_from_source.py`, to be
updated with it.

**After a change**:

```bat
venv\Scripts\python -m unittest tests.test_hud_layout tests.test_hud_indicator
venv\Scripts\python tools\play_seed.py <seed.zip> --content <content> --rpx U-King.rpx
```

The reference digests of `tests/test_resources_from_source.py` and `tests/test_pack_from_source.py` change with the
resources: update them (see [development](../development.md#reproducible-builds)).

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
