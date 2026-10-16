from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path

from _vault.listing import VaultDirectory

SF_DATALESS = 0x40000000
NO_FLAGS = 0
STUB_NAME = re.compile(r"^\.(?P<name>.+)\.icloud$")


class ICloudFolder:
    def __init__(self, notes_directory: Path | None = None,
                 lstat: Callable[[Path], os.stat_result] = os.lstat) -> None:
        self._notes_directory = notes_directory
        self._lstat = lstat

    def conflict_copies(self, directory: Path) -> list[Path]:
        return VaultDirectory(directory, self._notes_directory).conflict_copies()

    def not_downloaded(self, path: Path) -> bool:
        return self._is_stub(path) or self._stub_of(path).exists() or self._is_dataless(path)

    @staticmethod
    def _is_stub(path: Path) -> bool:
        return STUB_NAME.match(path.name) is not None

    @staticmethod
    def _stub_of(path: Path) -> Path:
        return path.with_name(f".{path.name}.icloud")

    def _is_dataless(self, path: Path) -> bool:
        try:
            flags = getattr(self._lstat(path), "st_flags", NO_FLAGS)
        except FileNotFoundError:
            return False
        return bool(flags & SF_DATALESS)
