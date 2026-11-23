"""Updates: the project's releases on GitHub, downloaded and installed side by
side with the version that runs (botw_launcher/versions.py).

Two kinds of releases:
  * up to 0.3.x, one zip for each system, named
    BOTW-Archipelago-<version>-<System>.zip, holding one folder, the release
    (their botw.apworld beside it is the world alone). An older seed is
    played with one: installed side by side, it opens its own launcher;
  * since, botw.apworld alone (tools/build_release.py): the world and this
    window, opened by Archipelago, which loads one version of a world at a
    time. Updating replaces the botw.apworld Archipelago loaded (BOTW_AP_APWORLD,
    set by botw_world/client) by the newer one; Archipelago is then restarted. Installing it is unpacking that folder as
<data>/versions/<version>; the launcher then restarts as that version.

What a release plays (core/worlds.py) is read from the first bytes of its zip
or its apworld, its release.json, without downloading the rest, once for each release.
Only the release list and those bytes are read from GitHub; nothing about the
player is sent.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
import logging
from pathlib import Path
import shutil
import ssl
import struct
import sys
from typing import Callable
import urllib.request
import zipfile

from botw_client import compatibility
from botw_client.paths import DATA, RELEASE_MARKER, ROOT
from botw_client.version import VERSION, parse

from .. import versions
from . import worlds

logger = logging.getLogger(__name__)
REPOSITORY = "EIdras/BOTW-Archipelago"
RELEASES_API = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=30"
RELEASES_PAGE = f"https://github.com/{REPOSITORY}/releases"
SYSTEM = {"win32": "Windows", "linux": "Linux"}.get(sys.platform, sys.platform)
DOWNLOADS = DATA / "downloads"
STATEMENTS = DATA / "releases.json"     # what each release plays, read once from its zip
HEAD = 4096             # bytes read at the start of a zip: its release.json fits
TIMEOUT = 15            # seconds, for each network read
CHUNK = 1 << 18
APWORLD = "botw.apworld"
APWORLD_VARIABLE = "BOTW_AP_APWORLD"    # the botw.apworld Archipelago loaded this window from
GAME = "Breath of the Wild"

Progress = Callable[[int, int, str], None]      # done, total, what is being done
Fetch = Callable[[str], bytes]


@dataclass(frozen=True)
class Release:
    version: str
    title: str
    notes: str
    page: str
    prerelease: bool
    asset_name: str
    asset_url: str
    asset_size: int
    asset_sha256: str       # "" when GitHub gives none
    plays: dict | None = None   # its release.json's statement, once read (with_statements)
    kind: str = "zip"           # "zip": up to 0.3.x, installed side by side; "apworld": since


def _context() -> ssl.SSLContext:
    # A new Windows trusts few roots of its own: certifi's are added, as for the room.
    context = ssl.create_default_context()
    try:
        import certifi
        context.load_verify_locations(certifi.where())
    except (ImportError, OSError):
        pass
    return context


def _open(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "BOTW-Archipelago-launcher",
                                                   "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(request, timeout=TIMEOUT, context=_context())


def fetch(url: str) -> bytes:
    with _open(url) as response:
        return response.read()


def fetch_range(url: str, start: int, length: int) -> bytes:
    """`length` bytes of a file from `start`, never more, even from a server
    that answers with the whole file."""
    request = urllib.request.Request(url, headers={"User-Agent": "BOTW-Archipelago-launcher",
                                                   "Accept": "application/octet-stream",
                                                   "Range": f"bytes={start}-{start + length - 1}"})
    with urllib.request.urlopen(request, timeout=TIMEOUT, context=_context()) as response:
        if response.status != 206 and start:
            raise OSError("the server does not send parts of a file")
        return response.read(length)


def read_statement(url: str, fetch_range: Callable[[str, int, int], bytes] = fetch_range) -> dict | None:
    """What a release plays, read from its zip's first entry, release.json,
    stored uncompressed (as releases up to 0.3.x zipped it). None when the zip
    does not start with it: a release from before the statement.
    OSError when the zip cannot be read."""
    head = fetch_range(url, 0, HEAD)
    if len(head) < 30 or head[:4] != b"PK\x03\x04":
        raise OSError("the release's file is not a zip")
    flags, method = struct.unpack_from("<HH", head, 6)
    size = struct.unpack_from("<I", head, 18)[0]
    name_length, extra_length = struct.unpack_from("<HH", head, 26)
    name = head[30:30 + name_length].decode("utf-8", "replace")
    if method != zipfile.ZIP_STORED or flags & 0x08 or name.count("/") != 1 or not name.endswith(
            "/" + RELEASE_MARKER):
        return None
    start = 30 + name_length + extra_length
    data = head[start:start + size]
    if len(data) < size:
        data = fetch_range(url, start, size)
    try:
        said = json.loads(data)[compatibility.KEY]
    except (ValueError, KeyError, TypeError):
        return None
    return said if isinstance(said, dict) else None


def with_statements(found: list[Release], fetch_range: Callable[[str, int, int], bytes] = fetch_range,
                    cache: Path | None = None) -> list[Release]:
    """The releases with what they play: kept from an earlier read, else read
    from their zip. Not for the releases before worlds.DECLARED_SINCE, which
    state nothing (worlds.legacy); a release not read stays without."""
    cache = STATEMENTS if cache is None else cache
    try:
        known = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        known = {}
    known = known if isinstance(known, dict) else {}
    stated, changed = [], False
    for release in found:
        key = f"{release.asset_name}:{release.asset_size}:{release.asset_sha256}"
        entry = known.get(release.version)
        if parse(release.version) < parse(worlds.DECLARED_SINCE):
            stated.append(release)
            continue
        if not (isinstance(entry, dict) and entry.get("asset") == key):
            try:
                entry = {"asset": key, "plays": read_statement(release.asset_url, fetch_range)}
            except Exception as exc:        # never the update check's failure: a side read
                logger.warning("what version %s plays could not be read: %s", release.version, exc)
                stated.append(release)
                continue
            known[release.version], changed = entry, True
        stated.append(replace(release, plays=entry.get("plays")))
    if changed:
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(known, indent=1) + "\n", encoding="utf-8")
        except OSError as exc:
            logger.warning("the releases' statements are not kept: %s", exc)
    return stated


def asset_name(version: str) -> str:
    return f"BOTW-Archipelago-{version}-{SYSTEM}.zip"


def _release(entry: dict) -> Release | None:
    """A GitHub release this system can install, None otherwise (a draft, a tag
    that is not a version, no file for this system). A release with a zip is of
    the zips' time, whose botw.apworld is the world alone: never an update."""
    try:
        version = entry["tag_name"].lstrip("v")
        parse(version)
        names = {asset["name"]: asset for asset in entry["assets"]}
    except (KeyError, ValueError, AttributeError, TypeError):
        return None
    zips = [name for name in names if name.startswith("BOTW-Archipelago-") and name.endswith(".zip")]
    if zips:
        kind, asset = "zip", names.get(asset_name(version))
    else:
        kind, asset = "apworld", names.get(APWORLD)
    if asset is None:
        return None
    if entry.get("draft"):
        return None
    digest = str(asset.get("digest") or "")
    return Release(version, entry.get("name") or version, entry.get("body") or "", entry.get("html_url", ""),
                   bool(entry.get("prerelease")), asset["name"], asset["browser_download_url"],
                   int(asset.get("size", 0)), digest.removeprefix("sha256:") if digest.startswith("sha256:") else "",
                   kind=kind)


def releases(fetch: Fetch = fetch) -> list[Release]:
    """The installable releases, the newest first. OSError when GitHub cannot be read."""
    try:
        entries = json.loads(fetch(RELEASES_API))
    except ValueError as exc:
        raise OSError(f"GitHub's answer could not be read: {exc}") from exc
    found = [release for release in map(_release, entries if isinstance(entries, list) else [])
             if release is not None]
    return sorted(found, key=lambda release: parse(release.version), reverse=True)


def newer(found: list[Release], prereleases: bool = False, than: str = VERSION) -> Release | None:
    """The update to offer: the newest botw.apworld above `than`."""
    return next((release for release in found if release.kind == "apworld"
                 and parse(release.version) > parse(than) and (prereleases or not release.prerelease)), None)


def usable(found: list[Release], than: str = VERSION) -> list[Release]:
    """The releases that can play a seed for this version: the zips' (installed
    side by side), and the botw.apworld newer than this one (an update)."""
    return [release for release in found if release.kind == "zip" or parse(release.version) > parse(than)]


def named(found: list[Release], version: str) -> Release | None:
    """The release of one version: the one an older seed needs."""
    return next((release for release in found if release.version == version), None)


def download(release: Release, progress: Progress = lambda *_: None, folder: Path = DOWNLOADS) -> Path:
    """Download a release's file, checked against the size and the digest GitHub gives."""
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / release.asset_name
    partial = target.with_suffix(".part")
    digest = hashlib.sha256()
    done = 0
    with _open(release.asset_url) as response, partial.open("wb") as stream:
        while chunk := response.read(CHUNK):
            stream.write(chunk)
            digest.update(chunk)
            done += len(chunk)
            progress(done, release.asset_size, f"Downloading version {release.version}")
    if release.asset_size and done != release.asset_size:
        partial.unlink(missing_ok=True)
        raise OSError(f"The download is incomplete ({done} of {release.asset_size} bytes): try again.")
    if release.asset_sha256 and digest.hexdigest() != release.asset_sha256:
        partial.unlink(missing_ok=True)
        raise OSError("The downloaded file is not the one GitHub published: try again.")
    partial.replace(target)
    return target


def install(archive: Path, progress: Progress = lambda *_: None, folder: Path | None = None) -> versions.Installed:
    """Unpack a release's zip as an installed version, next to the others. The
    version is the one its release.json states, whatever the file is named."""
    folder = versions.VERSIONS if folder is None else folder
    staging = folder / f".incoming-{archive.stem}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        with zipfile.ZipFile(archive) as bundle:
            members = bundle.infolist()
            for count, member in enumerate(members, 1):
                if not (staging / member.filename).resolve().is_relative_to(staging.resolve()):
                    raise ValueError(f"unsafe path in the release's zip: {member.filename}")
                bundle.extract(member, staging)
                if count % 200 == 0 or count == len(members):
                    progress(count, len(members), "Installing")
        roots = [entry for entry in staging.iterdir() if entry.is_dir()]
        if len(roots) != 1:
            raise ValueError("the zip is not a BOTW Archipelago release")
        release = roots[0]
        version = json.loads((release / RELEASE_MARKER).read_text(encoding="utf-8"))["version"]
        parse(version)
        if not any((release / entry).is_file() for entry in (versions.ENTRY, versions.CONSOLE_ENTRY)):
            raise ValueError(f"version {version} has no launcher")
        target = folder / version
        if target.resolve() == ROOT.resolve():
            raise ValueError(f"version {version} is the one running")
        if target.exists():
            shutil.rmtree(target)
        release.rename(target)
    except (OSError, KeyError, zipfile.BadZipFile) as exc:
        raise ValueError(f"the release could not be installed: {exc}") from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    (target / versions.COMPLETE).write_text(json.dumps({"version": version}) + "\n", encoding="utf-8")
    archive.unlink(missing_ok=True)
    return versions.Installed(version, target)


# ---- botw.apworld ------------------------------------------------------------

def installed_apworld(environ=None) -> Path | None:
    """The botw.apworld Archipelago loaded this window from: None from a source
    checkout or a world folder, which an update does not replace."""
    import os
    path = (os.environ if environ is None else environ).get(APWORLD_VARIABLE, "")
    return Path(path) if path.endswith(".apworld") and Path(path).is_file() else None


def check_apworld(path: Path, version: str) -> None:
    """A botw.apworld of `version` with its window: ValueError otherwise."""
    try:
        with zipfile.ZipFile(path) as world:
            names = set(world.namelist())
            game = json.loads(world.read("botw/archipelago.json"))["game"]
            stated = json.loads(world.read(f"botw/{RELEASE_MARKER}"))["version"]
            broken = world.testzip()
    except (OSError, KeyError, ValueError, TypeError, zipfile.BadZipFile) as exc:
        raise ValueError(f"the downloaded botw.apworld cannot be read: {exc}") from exc
    if broken or game != GAME or stated != version or not {"botw/__init__.py", "botw/client/payload.zip"} <= names:
        raise ValueError(f"the downloaded file is not the botw.apworld of version {version}")


def install_apworld(release: Release, target: Path, progress: Progress = lambda *_: None,
                    folder: Path = DOWNLOADS) -> Path:
    """Replace `target`, the botw.apworld Archipelago loads, by the release's,
    once downloaded and checked; the one replaced is kept in `folder`. Nothing
    left beside `target` ends in .apworld: Archipelago would load it too."""
    if release.kind != "apworld":
        raise ValueError(f"version {release.version} is not a botw.apworld")
    downloaded = download(release, progress, folder)
    check_apworld(downloaded, release.version)
    progress(1, 1, "Installing")
    shutil.copy2(target, folder / f"botw-{VERSION}.apworld.previous")
    incoming = target.with_name(target.name + ".incoming")
    try:
        shutil.copy2(downloaded, incoming)
        incoming.replace(target)
    except OSError as exc:
        incoming.unlink(missing_ok=True)
        raise OSError(f"{target} could not be replaced ({exc}). The new one is {downloaded}: install it with the "
                      "Archipelago Launcher's Install APWorld, once Archipelago is closed.") from exc
    downloaded.unlink(missing_ok=True)
    return target
