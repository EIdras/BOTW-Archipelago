"""What the player chose in the launcher, kept in the data folder.

The file is shared by every installed version (botw_launcher/versions.py): a
key this version does not know is kept as it is when the settings are saved,
so that an older version never erases what a newer one wrote.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
import json
from pathlib import Path

from botw_client.paths import DATA

PATH = DATA / "launcher" / "settings.json"
LOG_LEVELS = ("ERROR", "WARNING", "INFO", "DEBUG")


@dataclass
class Settings:
    log_level: str = "INFO"         # what the Logs page shows; the log file always holds everything
    check_updates: bool = True      # look for a new release when the launcher starts
    prereleases: bool = False       # pre-releases count as updates
    skipped_version: str = ""       # the update the player said no to: not announced again
    last_seed: str = ""             # the seed selected when the launcher closed
    window_size: list[int] = field(default_factory=lambda: [1080, 720])
    # Keys of other versions, written back untouched.
    unknown: dict = field(default_factory=dict, repr=False)


def load(path: Path | None = None) -> Settings:
    """The saved settings; the defaults for what is missing, unreadable or of another type."""
    path = PATH if path is None else path
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Settings()
    if not isinstance(saved, dict):
        return Settings()
    settings = Settings()
    known = {entry.name for entry in fields(Settings)} - {"unknown"}
    for name in known & saved.keys():
        if type(saved[name]) is type(getattr(settings, name)):
            setattr(settings, name, saved[name])
    if settings.log_level not in LOG_LEVELS:
        settings.log_level = Settings.log_level
    settings.unknown = {name: value for name, value in saved.items() if name not in known}
    return settings


def save(settings: Settings, path: Path | None = None) -> None:
    path = PATH if path is None else path
    values = asdict(settings)
    values = {**values.pop("unknown"), **values}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
