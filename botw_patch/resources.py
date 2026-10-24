"""Resource IO and platform-aware RSTB accounting for generated overlays."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
import oead
import rstb


def unpack(data: bytes) -> bytes:
    return bytes(oead.yaz0.decompress(data)) if data[:4] == b"Yaz0" else data


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def vanilla_digest(data: bytes) -> str:
    """digest() of a game resource as the European version's file names it, from
    any supported version (botw_client/regions.py): what the build's pins compare."""
    from botw_client.regions import vanilla_digest
    return vanilla_digest(data)


def canonical(name: str) -> str:
    path = Path(name)
    ext = path.suffix
    return path.with_suffix("." + ext[2:]).as_posix() if ext.startswith(".s") and ext != ".sarc" else path.as_posix()


class ResourceBuilder:
    def __init__(self, content, platform: str = "wiiu"):
        """content: a content folder, or the game's files (botw_patch/game_files.py)."""
        from .game_files import GameFiles
        if platform not in {"wiiu", "switch"}:
            raise ValueError(f"unknown platform: {platform}")
        self.game = GameFiles.of(content)
        self.content = self.game.content
        self.platform = platform
        self.big_endian = platform == "wiiu"
        self.outputs: dict[str, bytes] = {}
        self.changes: list[dict] = []
        self.table_path = "System/Resource/ResourceSizeTable.product.srsizetable"
        self.table = rstb.ResourceSizeTable(unpack(self.read(self.table_path)), self.big_endian)
        self.calculator = rstb.SizeCalculator()

    def read(self, name: str) -> bytes:
        return self.game.read(name)

    def account(self, name: str, data: bytes, original: bytes | None = None):
        key = canonical(name)
        computed = self.calculator.calculate_file_size_with_ext(
            data, self.big_endian, Path(name).suffix)
        old = self.table.get_size(key) if self.table.is_in_table(key) else 0
        if not computed:
            # Serialized growth cannot predict allocations of parsed AAMP and
            # other complex structures. Require a type-aware implementation.
            raise ValueError(f"no validated allocation for complex resource {key}")
        growth = max(0, len(unpack(data)) - len(unpack(original))) if original else 0
        self.table.set_size(key, max(old + ((growth + 31) & ~31), computed))

    def patch_archive(self, name: str, transforms: dict, *, new_members=()):
        """Transform members of an archive. A member listed in `new_members`
        must not exist yet: its transform receives None and creates it."""
        source = self.outputs[name] if name in self.outputs else self.read(name)
        raw = unpack(source)
        sarc = oead.Sarc(raw)
        if sarc.get_endianness() != (oead.Endianness.Big if self.big_endian else oead.Endianness.Little):
            raise ValueError(f"archive platform mismatch: {name}")
        writer = oead.SarcWriter.from_sarc(sarc)
        from .game_files import guard, own_member
        for member, transform in transforms.items():
            guard(name, member)
            existing = sarc.get_file(member)
            if (existing is None) != (member in new_members):
                raise ValueError(f"{name}: {member} " + (
                    "already exists" if existing is not None else "is missing"))
            previous = None if existing is None else bytes(existing.data)
            replacement, detail = transform(previous)
            writer.files[member] = replacement
            # Growth is measured from the larger of a pack's member and the game's own.
            own = own_member(name, member)
            baseline = own if own is not None and previous is not None and \
                len(own) > len(unpack(previous)) else previous
            self.account(member, replacement, baseline)
            self.changes.append({"archive": name, "member": member,
                                 "before_sha256": None if previous is None else digest(previous),
                                 "after_sha256": digest(replacement), "edits": detail})
        result = bytes(writer.write()[1])
        if source[:4] == b"Yaz0":
            result = bytes(oead.yaz0.compress(result))
        self.account(name, result, source)
        self.outputs[name] = result

    def finish(self) -> dict[str, bytes]:
        stream = io.BytesIO()
        self.table.write(stream, self.big_endian)
        self.outputs[self.table_path] = bytes(oead.yaz0.compress(stream.getvalue()))
        return dict(self.outputs)
