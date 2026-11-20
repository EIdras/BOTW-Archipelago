# Linux support

> Design for adding Linux support (feature request [#1](https://github.com/EIdras/BOTW-Archipelago/issues/1)).

Breath of the Wild for Archipelago targets Windows today: a release bundles a portable Python and a
`.cmd` launcher, the client talks to Cemu through `kernel32`, and the launcher and tests assume PowerShell.
Cemu itself is a cross-platform emulator, so the game side of the integration already runs unchanged under
Cemu on Linux. This document is the plan for the **host side**: everything the OS touches between Python and
the emulator.

## Scope and requirements

Linux support targets the same setup the feature request assumes: Cemu runs as the AppImage (the user's binary is
`~/Cemu/Cemu-2.6-x86_64.AppImage`, and the launcher asks the user where it is on first launch), and it adds Linux
equivalents in each area the Windows path handles differently:

- **Python install** — use the system Linux Python 3.x and a venv (pipx or a first-launch bootstrap that builds
  one from `requirements-player.txt`), instead of using a bundled Python binary.
- **Memory access** (`tools/cemu/winmem.py`), **PID discovery** (`tools/cemu/mailbox.py`), and the **launcher and
  entry scripts** — Linux equivalents, so the client talks to Cemu through `/proc` instead of `kernel32`.
- **The launcher script** — the Windows `.cmd` scripts (`BOTW Archipelago.cmd`, `Play.cmd`, `run-tests.cmd`) get
  Linux equivalents; the launcher itself can stay entirely in Python.
- **Tests** — Linux equivalents / `os.name` guards for the platform-specific cases.
- **Release packaging** — a `-Linux.zip` with a venv and a Linux CI job.
- **Documentation** — note that Linux is supported (the AppImage, the XDG data folder, the launch steps).

This document is the technical design behind those areas: it turns each into concrete code-level changes, resolves
the Linux-specific details the requirement list cannot (the AppImage's two-process layout, the XDG data dir, the
isolated-profile launch), and states the order and the remaining open questions.

## The one fact that bounds the work

The guest side of the project is platform-independent, and stays so. Cemu maps the game the same way on every
OS, so on Linux nothing below has to change:

- the guest addresses, the `MEM2` map (`tools/cemu/guest.py`), and the `in_guest`/`in_heap` plausibility checks;
- the code-cave span (`0x01800000`), the RPX probe bytes, and the PPC assembly of `native/cemu/*.asm`;
- the patch-build pipeline (`tools/build_native_from_source.py`) and every pack builder;
- the Archipelago world (`botw_world/`), the client logic (`botw_client/`), and the `Cave` of
  `tools/cemu/mailbox.py`, which reads and writes the cave through a `Process` without caring which OS owns it.

Linux support is therefore the layer **between** Python and Cemu: the Python runtime, process discovery,
cross-process memory access, cross-process locking and process identity, the launch and packaging scripts, the
CI, and the documentation. The guiding rule is that the guest side must not move.

## Design principle: one memory interface

Every caller of process memory — `tools/cemu/mailbox.py`, `gdt_index.py`, `livegdt.py`, `findtext.py`,
`say.py`, `saycenter.py`, `saydialog.py`, `disasm.py`, `owned_presentation.py`, and the client through them —
uses the same small `Process` API: `regions(min_size)`, `read(address, size)`, `write(address, data)`,
`close()`, plus the `.h`, `.pid` and `.writable` attributes.

The change is hidden behind one factory so none of those callers sees the OS:

```
Process.for_pid(pid, writable=...) -> Process   # winmem on Windows, linuxmem on Linux
```

`tools/cemu/winmem.py` (the `kernel32` implementation) is untouched. `tools/cemu/linuxmem.py` is the new
Linux equivalent, and `winmem.Process` / `linuxmem.Process` share the same interface by construction. The
`for_pid` factory in `tools/cemu/__init__.py` (or a small `tools/cemu/process.py`) selects the backend by
`sys.platform`. `guest.py` and `mailbox.py` do not change.

## The areas

### 1. Python runtime: bundled binary → system Python + venv

Windows ships a portable Python next to the launcher (`python/python.exe`, opened by `BOTW Archipelago.cmd`).
On Linux there is nothing to bundle: use the system Python 3.x and a venv (a shipped `venv/`, or pipx).

Impact:

- `tools/build_release.py` currently refuses `sys.platform != "win32"` (`build()`), and copies the bundled
  Python (`PYTHON_FILES`, `PYTHON_FOLDERS`, `copy_python`, `copy_packages`). The Linux build produces a
  different artifact: no `python/` folder, a venv or a setup step that creates one, and a `-Linux.zip` archive.
- `requirements-player.txt` pins `oead`, `evfl`, `rstb` (the Wii U format libraries) and `numpy`. **This was
  the make-or-break check, and it is confirmed resolved** (see "Open questions" below): the pinned versions
  ship Linux wheels, so the "system Python + bootstrap" plan stands and no Rust toolchain is needed.

### 2. Memory access: `tools/cemu/winmem.py` → `tools/cemu/linuxmem.py`

Windows uses `kernel32` `OpenProcess` / `VirtualQueryEx` / `ReadProcessMemory` / `WriteProcessMemory`.
Linux exposes the same through `/proc`:

- `regions(min_size)` reads `/proc/<pid>/maps`, yielding `(base, size)` of committed, readable, non-guarded
  regions — the direct analogue of `VirtualQueryEx`.
- `read`/`write` open `/proc/<pid>/mem` and `lseek` + `read`/`write` at the guest-mapped host address.
- `close` closes the fd.

`/proc/<pid>/mem` is writable by any process of the **same user** without `CAP_SYS_PTRACE`, which matches the
current "run as the same user as Cemu" expectation and avoids the stricter `ptrace` scope rules. The factory
keeps the same error contract: an unreadable region returns `None` from `read`, and `open` raises when the
process is not visible.

Testability: this module can be unit-tested without Cemu running, against a real `/proc/self` dump — arm it
first, before the rest.

### 3. PID discovery: `mailbox.cemu_pid()` and `cemu_profile.cemu_running()`

Both call PowerShell `Get-Process Cemu`. Linux uses `/proc`, but the AppImage runs as **two** processes, not
one, and only one holds the game's memory:

- Running the AppImage yields two matches for `pgrep -f Cemu`: the real emulator, whose command line is the
  AppImage path (`/home/ac/Cemu/Cemu-2.6-x86_64.AppImage`), and the FUSE mount shim
  (`/tmp/.mount_*/AppRun.wrapped`), the launcher rather than the emulator.
- The memory to read lives in the emulator, so discovery keeps the `Cemu` match, **prefers the one whose
  command line contains `.AppImage`**, and skips any `/tmp/.mount_*` process. It still honours an explicit
  `BOTW_CEMU_PID`, exactly as `mailbox.cemu_pid()` does today.
- The version number in the name (`2.6`) is irrelevant to the match, so newer releases (`Cemu-2.7-…`) are
  handled the same way. Reading `/proc/*/cmdline` directly (not a `pgrep` string) keeps this testable.

`cemu_profile.cemu_running()` makes the same call; apply the same rule.

### 4. Cemu locations and paths

- `tools/cemu_install.py` falls back to `%APPDATA%\\Cemu`. On Linux Cemu is usually a portable AppImage
  (`portable/` next to the binary); `user_data_of()` already handles a given executable plus a portable folder.
  A non-portable Cemu keeps its two list files in the XDG folders, and on this machine they split: `settings.xml`
  in the **config** dir (`$XDG_CONFIG_HOME/Cemu`, else `~/.config/Cemu`) while `title_list_cache.xml` is in the
  **data** dir (`$XDG_DATA_HOME/Cemu`, else `~/.local/share/Cemu`). `detect()` therefore searches every XDG
  folder Cemu uses (config, then data) for the game list, and `user_data_of()` returns the one that holds
  `settings.xml`.
- `tools/cemu/mailbox.py` sets `DEFAULT_LOG` to `%APPDATA%/Cemu/log.txt`. In a non-portable install Cemu writes
  it to `~/.local/share/Cemu/log.txt`; in the isolated profile it is written into the profile's data folder,
  and `BOTW_CEMU_LOG` overrides both. Make the non-portable default XDG-data-aware.
- The lab tools that read the install (`build_location_positions.py`, `build_names_fr.py`, `build_poptracker.py`,
  `map_regions.py`, `measure_region.py`, …) hardcode
  `AppData/Roaming/Cemu/...` defaults. They are developer tools; point them at XDG on Linux, lower priority.

### 5. Cross-process locking and process identity

- `tools/cemu/owned_presentation.publisher_lock` takes a `kernel32 CreateMutexW` named
  `Local\BOTW_AP_Owner_{pid}` so only one Python publishes to Cemu. On Linux, a lock file
  `<data>/owner_{pid}.lock` with `fcntl.flock` does the same. `botw_client/presentation_store.py` already
  branches on `os.name` for exactly this (`msvcrt` vs `fcntl`), so the pattern exists and is tested — copy it.
- `botw_client/presentation_cemu.process_incarnation` reads `GetProcessTimes` and `GetExitCodeProcess` through a
  `kernel32` handle to detect that Cemu exited. On Linux, read `/proc/<pid>/stat` for the start time and check
  that the directory still exists.

#### The isolated profile and launching Cemu

A play session must run Cemu in the isolated profile (the copies of the update, DLC, saves, accounts and packs
in `tools/cemu_profile.py`), exactly as Windows does. Today `tools/play_session.py` launches
`PROFILE/Cemu.AppImage -m <portable/mlc01> -g <game>` with `cwd=PROFILE`, so Cemu uses the `portable/` folder next to
it. The implemented Linux approach keeps the faithful parallel to Windows: the AppImage is copied into the
profile (as `PROFILE/Cemu.AppImage`) and launched there, so Cemu uses the `portable/` folder next to it. An
alternative — pointing the user's AppImage at the profile with the `WX_CEMU_DATA_DIR` env var (Cemu honours it
on Unix, Cemu PR #316) — was confirmed viable but not used. The session sets `BOTW_CEMU_PID` and `BOTW_CEMU_LOG`
from the launched process, exactly as Windows does.

### 6. Launcher and entry scripts

- The launcher stays Python, as the plan suggests. On first launch it asks for the Cemu AppImage location and
  filters the file dialog to `Cemu*.AppImage`. The follow-on `cemu_install.detect` and `cemu_profile.create`
  are already path-agnostic, and tkinter works on Linux.
- The bootstrap script finds `python3`, then on first launch builds the venv from `requirements-player.txt`
  (the user has internet; no Rust toolchain is required if the deps wheel). It then runs the same Python entry
  (`tools/launcher.py`, `tools/play_session.py`, `unittest`).

### 7. Tests

The existing suite must pass on Linux, and several tests touch platform specifics:

- `test_release.py` (the Windows-only build), `test_cemu_install.py`, `test_launcher.py`,
  `test_presentation_cemu.py`, `test_runtime_process_exit.py`, `test_guest_memory.py`.
- Give the platform-specific ones Linux equivalents or `os.name` guards, and add a Linux CI job that mirrors
  the Windows one.

### 8. Release packaging and CI

- `tools/build_release.py`: branch the win32 and linux paths in `build()`. The Linux artifact is
  `BOTW-Archipelago-<version>-Linux.zip` — a venv (or a script that builds one), not as a bundled Python. The
  Archipelago world (`botw.apworld`, `tools/package_native.py`) is platform-independent and is packaged as-is.
- `.github/workflows/release.yml`: add a `linux-latest` job that installs the player requirements into a venv,
  runs the tests, and builds the Linux zip, next to the existing `windows-latest` job.

### 9. Documentation

- `README.md`: "What you need" and "Limitations" gain a line for Linux and the Cemu AppImage.
- `botw_world/docs/setup_en.md` and `setup_fr.md`, and `troubleshooting_en.md`: add the Linux steps (install the
  AppImage, point the launcher at it, the XDG data folder).

## Suggested order

Work lowest-risk first; each area is independently testable and most do not need Cemu running:

1. `linuxmem.py` + the `for_pid` factory — unblocks everything; unit-tested against `/proc/self`.
2. PID discovery (`/proc`, honouring `BOTW_CEMU_PID`) and the XDG log path.
3. XDG paths in `cemu_install.py` and `mailbox.DEFAULT_LOG`.
4. Locking and process identity (copy the `presentation_store.py` pattern).
5. Launch scripts and the launcher's file filter.
6. Tests and the Linux CI job.
7. Release packaging (`build_release.py` branch, `-Linux.zip`).
8. Documentation.

## Resolved questions

All brainstorming questions are now answered (system Python + a first-launch bootstrap script, since the user
has internet and should not need a Rust toolchain; the AppImage runs as two processes so discovery prefers the
`.AppImage` command line and skips `/tmp/.mount_*`; non-portable logs land in `~/.local/share/Cemu/`).

- **Do `oead`, `evfl`, `rstb` actually ship manylinux wheels?** — **CONFIRMED (PyPI).** All three pinned
  versions wheel on Linux, no Rust toolchain:
  - `oead==1.2.9.post4` ships native `manylinux_2_17_x86_64` (glibc) **and** `musllinux_1_2_x86_64` wheels for
    CPython 3.8–3.12 (plus win and pypy). It is the only compiled dependency.
  - `evfl==1.2.0` and `rstb==1.2.2` are pure-Python (`py3-none-any.whl`); `rstb` depends only on `oead ~=1.1`.
  So the bootstrap can `pip install -r requirements-player.txt` into a venv on any Linux and it resolves from
  wheels. (Latest `oead` on PyPI is 1.3.0, which also wheels on Linux, but the pinned 1.2.9.post4 is enough.)
- **What does `WX_CEMU_DATA_DIR` do exactly?** — **CONFIRMED (Cemu PR #316, "non portable mode").** On Unix Cemu
  honours `WX_APPNAME_DATA_DIR`, where APPNAME is the upper-cased `GetAppName()` (`CEMU` → `WX_CEMU_DATA_DIR`), to
  override its data/prefix path. Verified against Cemu 2.6. Smoke-test the exact behaviour on the user's AppImage
  before relying on it for save isolation.
- **Copy the AppImage into the profile, or use the env var?** — **DECIDED: copy.** `tools/play_session.py`
  launches `PROFILE/Cemu.AppImage -m <portable/mlc01> -g <game>` with `cwd=PROFILE`, so Cemu runs from the copied
  AppImage and uses the `portable/` folder next to it — the faithful parallel to Windows, and save isolation
  rides on the same mechanism Windows already has. The `WX_CEMU_DATA_DIR` env-var path (confirmed viable) was
  not used.
- **Which venv tool does the bootstrap use?** — **Recommend stdlib `venv` + `pip`.** It is what
  `.github/workflows/release.yml` already uses, needs no second download, and the pinned deps wheel on it. Use
  `uv` only if first-launch speed becomes a problem.
- **Is the native PPC assembly assembled by a separate, cross-platform toolchain during pack build?** — **CONFIRMED
  NO.** Cemu assembles the delivered `patch_*.asm` files itself at run time (its "Assembly Patching" feature; the
  Cemu Wiki: an `ASM patch_<anything>.asm` file is assembled and written into the guest). The native component is
  PPC machine code produced from platform-independent source, so there is no Windows-only compiler step and the
  Linux player needs no toolchain.
