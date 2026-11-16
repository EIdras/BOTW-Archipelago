# Linux Support — Validation Checklist

Ground truth for testing the Linux support of the BOTW Archipelago player.
It is meant for **two readers**:

- **The human** running the GUI to confirm each step works on Linux.
- **The agent** deciding what is already proven and what a fix or test must cover.

## 0. Read first

- **`docs/linux-support.md`** — the design. This doc is its test counterpart.
- `tools/cemu_profile.py` — the isolated Cemu profile the session runs in.
- `tools/play_session.py` — the session that launches Cemu and checks isolation.
- `tools/cemu_install.py` — finds the installation's config / data / mlc01 dirs.

The whole Linux effort has three fixes. The tests below are grouped around them:

1. **Saved-file location** — Cemu on Linux spreads its data across XDG dirs and the
   portable/base-install folder; the profile must find and isolate the BOTW save.
2. **Settings + shaders + pipeline cache** — the profile must copy the player's
   preferences and the compiled shader / pipeline cache, and must not point back
   at the installation.
3. **Isolation** — a play session must never touch the installation's saves, and
   its own play-account save must be where Cemu writes it.

---

## 1. Prerequisites (real machine, not a checkout)

| Item | Where |
| --- | --- |
| Cemu installed (portable AppImage) | `/home/ac/Cemu/` — holds `Cemu*.AppImage`, `portable/`, `mlc01/`, `Dumpling/` |
| Cemu user data (config + data) | `~/.config/Cemu/` and `~/.local/share/Cemu/` |
| Shader / pipeline cache | `~/.cache/Cemu/shaderCache/` |
| A BOTW save | in the base-install mlc01, see below |
| A slot file for a BOTW Archipelago seed | e.g. `~/Archipelago/output/*.apbotw` |
| The player venv | `./venv/bin/python` (no `python` on PATH) |

### The Cemu Linux data layout (verified on this machine)

This is the ground truth the fixes must match. **Cemu on Linux does not keep
everything in one folder** — it follows the XDG conventions:

| What | Location |
| --- | --- |
| `settings.xml`, `controllerProfiles/`, `gameProfiles/` | `~/.config/Cemu/` (config) |
| `graphicPacks/`, `title_list_cache.xml`, `log.txt`, `memorySearcher/`, `mlc01/` | `~/.local/share/Cemu/` (data) |
| `shaderCache/` (driver, precompiled, transferable) | `~/.cache/Cemu/` (cache) |
| Base-install `mlc01/` (saves + titles) | `/home/ac/Cemu/mlc01/` (next to the binary) |

The **BOTW save** lives at:

```
/home/ac/Cemu/mlc01/usr/save/00050000/101c9400/user/80000001   # the real player save, SOURCE account
```

Note it is **not** in `~/.local/share/Cemu/mlc01` — it is in the base-install
`mlc01` next to the binary. `cemu_install.py` must find that folder.

### The accounts (two-save model)

| Account | Id | Role |
| --- | --- | --- |
| SOURCE | `0x80000001` | the copied real save |
| PLAY | `0x80000003` | the session's own save (new game) |

The session never writes to SOURCE; it plays on PLAY.

---

## 2. Test area 1 — location of saved files

### What the code does

- `cemu_install.py` locates the installation's `mlc01` (the folder that holds the
  BOTW save) — across the XDG data dir **and** the portable/base-install folder.
- `cemu_profile.create()` copies the BOTW save from `install.mlc/usr/save/00050000`
  into the profile's `portable/mlc01/usr/save/00050000`, and derives the PLAY
  account from SOURCE.
- `play_session.py` hashes the SOURCE save before launch and the PLAY save before
  and after, and reports `source_saves_unchanged` at the end.

### Expected

- The profile contains the player's real BOTW save under the **SOURCE** account
  (`.../00050000/101c9400/user/80000001`).
- The session plays on the **PLAY** account (`.../user/80000003`), which the
  profile pre-creates.
- After the session, the SOURCE save is **byte-identical**; the PLAY save has
  changed; **nothing** was written into the installation.

### GUI test

- **A.** Start Cemu from the profile (launcher → Play). The game loads into the
  **real player's save** (existing progress, not a new game). → proves the SOURCE
  save was found and copied to the right location.
- **B.** Play, then **save in-game** (Save at a chest / campfire). Close Cemu.
- **C.** Open the session folder `data/play-seeds/<seed>/sessions/<stamp>/session.json`
  and check `"source_saves_unchanged": true` and that `"play_saves_after"` differs
  from `"play_saves_before"`. → proves the play save went to the profile, not the
  installation.
- **D.** Confirm the installation's `/home/ac/Cemu/mlc01/usr/save/...` is unchanged
  (the real save is still there, still the SOURCE account).

### Automated test to add / rerun

```
./venv/bin/python -m unittest tests.test_launcher ProfileTests
```

`ProfileTests` should assert that, for a built profile:
- `profile.SAVES / "80000001"` exists and matches the recorded `source_save_hashes`
  in `isolation.json`;
- `profile.SAVES / "80000003"` (PLAY) exists (pre-created);
- no path under the profile points back into the installation.

### Known state

**Implemented and verified by inspection** on this machine: the profile's
`portable/mlc01/usr/save/00050000/101c9400` holds both `user/80000001` (real save)
and `user/80000003` (PLAY). The `save_before`/`save_after` logic in
`play_session.py` is correct — it hashes each account folder separately
(`source_saves` / `play_saves`). **No save-path bug.** The area to confirm is that
Cemu actually writes to the PLAY folder when launched from the profile.

---

## 3. Test area 2 — settings, shaders, and pipeline cache copied

### What the code does

- Copies `settings.xml` (rewritten: `mlc_path` → the profile's mlc01, `GraphicPack`
  cleared so it never loads the installation's packs) and `controllerProfiles/`.
- Copies `resources/` and `gameProfiles/` from the executable's folder.
- Copies the shader / pipeline cache into `portable/shaderCache/`.

### Expected

- **Settings:** `settings.xml` in the profile has no path pointing at the
  installation, and `GraphicPack` is empty. Player 1's controller
  (`controllerProfiles/controller0.xml`) is copied.
- **Shaders / pipeline:** the profile's `portable/shaderCache/` contains the same
  compiled data the player already has in `~/.cache/Cemu/shaderCache/` — i.e.
  `driver/nvidia/GLCache/…`, `driver/vk/…`, `precompiled/…`, `transferable/…`
  (the `.bin` / `.toc` files for the game title `00050000101c9400`).
- **Completeness:** Cemu also reads `ui.xml`, `buttons.xml`, `mic.xml`,
  `audio.xml`, `debug.xml`, `sys.xml`, `keymaps/`, and `wluprofiles/`. If the
  player has these, a faithful profile should carry them too.

### GUI test

- **E.** After launching from the profile, open **Options** in Cemu. The controller
  binding for player 1 is already set (not reset). → proves `controllerProfiles/`
  copied.
- **F.** The game runs without recompiling every shader (no long shader-compile
  stall on first load). → proves the shader cache was copied and used.
- **G.** Cemu does not list the player's own graphic packs from the installation
  (they are not loaded from there). → proves `GraphicPack` was cleared.

### Automated test to add / rerun

```
./venv/bin/python -m unittest tests.test_launcher ProfileTests
```

`ProfileTests` should assert that, for a built profile:
- `portable/settings.xml` has no `mlc_path` pointing outside the profile and an
  empty `GraphicPack`;
- `portable/controllerProfiles/controller0.xml` exists;
- `portable/shaderCache/` file set equals the source `~/.cache/Cemu/shaderCache/`
  file set (same relative paths).

### Known state

**Implemented and verified on this machine.** The profile's
`portable/shaderCache/` is an exact mirror of `~/.cache/Cemu/shaderCache/`
(driver/nvidia GLCache, driver/vk, precompiled, transferable — the same six files
for title `00050000101c9400`). `settings.xml` and `controllerProfiles/` are copied
and rewritten. The one gap worth checking: `ui.xml`, `buttons.xml`, `keymaps/`,
`wluprofiles/` are **not** copied — but on this machine the player's config dir
holds only `settings.xml` and `controllerProfiles/`, so there is nothing to lose
yet. If a player has those files, add them to the copy list.

---

## 4. The full GUI flow (run end to end)

Order these; each depends on the previous. Skip to 1, 4, 6, 8 if time is short.

1. **Launch & detection.** Start the launcher. It detects the Cemu installation
   at `/home/ac/Cemu/` and its user data. No error about a missing Cemu.
2. **Profile build.** The launcher builds the isolated profile
   (`data/cemu-validation/`). It should report the profile is ready and list the
   source save it found.
3. **Seed select.** Open the slot file. The seed's slot, player name, and number of
   placements show. Choose it.
4. **Room connection.** Enter the room address (e.g. `127.0.0.1:38281`) and
   connect. The client logs in as the seed's player. *(needs a live server)*
5. **PopTracker.** PopTracker opens and shows the seed's locations/items.
6. **Cemu launches from the profile.** Cemu starts and shows the seed's
   **Archipelago title-screen branding** (the injected patch ran). The game loads
   into the **real player's save**, not a new game. *(this is the key Linux launch
   test)*
7. **Save isolation.** Play, save in-game, close Cemu. Confirm (area 2, test C) that
   the play save landed in the profile and the source save is unchanged.
8. **In-game Archipelago.** Receive at least one delivered item and see it in the
   game / PopTracker. *(needs a live server sending to the room)*
9. **Clean exit.** Cemu and the client exit without errors; the session report is
   written.

---

## 5. Automated tests that run headless

```
# The Linux-specific suites (headless-safe):
./venv/bin/python -m unittest tests.test_launcher tests.test_cemu_install tests.test_linuxmem tests.test_linux_proc

# The full suite (expect 2 pre-existing failures unrelated to this work):
./venv/bin/python -m unittest discover tests
```

- `tests.test_launcher::ProfileTests` — the profile build, save location, and
  settings/shader-copy assertions. **Add here** the assertions from sections 2 and 3.
- `tests.test_cemu_install` — Cemu detection across the XDG dirs. Already passing.
- The 2 failures in `tests.test_player_packs` are **pre-existing** (list ordering)
  and fail identically on the base commit — not caused by this work.

### Not runnable here (why)

World-fill generation tests need an Archipelago source checkout at
`~/Archipelago/worlds/`. `prepare_ap_runtime.py` builds the runtime from that;
without it, those tests skip. Provide the checkout to unblock them.

---

## 6. Summary: what is proven vs. what to confirm

| Area | Status |
| --- | --- |
| Cemu detection across XDG dirs | **Proven** — `test_cemu_install` passes |
| BOTW save found & copied to profile, right location | **Proven by inspection** — confirm via GUI test A |
| PLAY account pre-created, SOURCE untouched | **Proven by inspection** — confirm via GUI test C |
| `settings.xml` rewritten, controller copied | **Proven by inspection** — confirm via GUI test E |
| Shader / pipeline cache copied | **Proven by inspection** — confirm via GUI test F |
| `ui.xml` / `buttons.xml` / `keymaps` / `wluprofiles` | **Not copied** — no-op on this machine; add if a player has them |
| Cemu launches from the profile on Linux | **Needs GUI** — test 6 |
| In-game Archipelago (branding, item delivery) | **Needs GUI + server** — tests 6, 8 |
| World-fill generation | **Blocked** — no AP source checkout |
