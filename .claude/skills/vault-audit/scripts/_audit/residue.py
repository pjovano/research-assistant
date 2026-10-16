from __future__ import annotations

import time
from pathlib import Path

import vault

from _audit.scope import REPOSITORY_ROOT

ORPHAN_PATTERNS = ("*.tmp", "*.bak", "*~", "*.part", "*.partial")
SECONDS_PER_DAY = 86400
BYTES_PER_MEGABYTE = 1048576


class Residue:
    def __init__(self, scratch: Path = vault.SCRATCH_DIR, corpus: Path = vault.CORPUS_DIR) -> None:
        self._scratch = scratch
        self._corpus = corpus

    def report(self) -> dict:
        return {"scratch": DirectoryPile(self._scratch).summary(),
                "conflict_copies": vault.library_conflict_copies(),
                "corpus_without_pdf": self._corpus_without_pdf(),
                "bytecode_directories": self._bytecode(),
                "orphans": self._orphans(),
                "inbox_files": sorted(path.name for path in vault.INBOX_DIR.glob("*") if path.is_file())}

    def _corpus_without_pdf(self) -> list[str]:
        held = vault.HeldBasenames((vault.LIBRARY_DIR, vault.VOLUMES_DIR)).keys()
        notes = vault.list_markdown(self._corpus)
        return sorted(vault.basename_of(path) for path in notes if vault.basename_of(path) not in held)

    @staticmethod
    def _bytecode() -> list[str]:
        found = REPOSITORY_ROOT.rglob("__pycache__")
        return sorted(str(path.relative_to(REPOSITORY_ROOT)) for path in found)

    @staticmethod
    def _orphans() -> list[str]:
        root = vault.VAULT_ROOT
        found = {path for pattern in ORPHAN_PATTERNS for path in root.rglob(pattern) if path.is_file()}
        return sorted(str(path.relative_to(root)) for path in found)


class DirectoryPile:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def summary(self) -> dict:
        files = [path for path in self._directory.rglob("*") if path.is_file()] if self._directory.exists() else []
        return {"path": self._label(), "files": len(files), "megabytes": self._megabytes(files),
                "oldest_days": self._oldest_days(files)}

    def _label(self) -> str:
        return self._directory.name

    @staticmethod
    def _megabytes(files: list[Path]) -> float:
        return round(sum(path.stat().st_size for path in files) / BYTES_PER_MEGABYTE, 1)

    @staticmethod
    def _oldest_days(files: list[Path]) -> int:
        if not files:
            return 0
        oldest = min(path.stat().st_mtime for path in files)
        return int((time.time() - oldest) / SECONDS_PER_DAY)
