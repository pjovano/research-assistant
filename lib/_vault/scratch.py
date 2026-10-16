from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from _vault.naming import nfc
from _vault.reviewed import ReviewedBasenames

KEYED_SUFFIXES = (".entries.json", ".suggested.json")
INGEST_ENTRY = "ingest"
BACKFILL_ENTRY = "backfill"
RUN_LOCK_NAME = "ingest-run.json"
ENGINE_COSTS_NAME = "engine-costs.json"
FIXED_NAMES = frozenset({"engine-run.json", "engine-reaper.json", "engine-prefetch.json", "engine-turn.lock",
                         "engine-waiting", RUN_LOCK_NAME, ENGINE_COSTS_NAME, "zotero", "talks", "trials",
                         "regressions", "health", BACKFILL_ENTRY, INGEST_ENTRY})
RENDER_PREFIX = "page-"
RENDER_SUFFIX = ".png"
RENDER_NAME = f"{RENDER_PREFIX}{{number:04d}}{RENDER_SUFFIX}"
GLYPHS_DIRECTORY = "glyphs"
PIXELS_CACHE_NAME = "pixels.json"
OCCURRENCES_CACHE_NAME = "occurrences.json"
FONT_REPAIR_CACHE_NAMES = (GLYPHS_DIRECTORY, PIXELS_CACHE_NAME, OCCURRENCES_CACHE_NAME)


@dataclass(frozen=True)
class ScratchEntry:
    path: Path

    @property
    def key(self) -> str:
        name = self.path.name
        for suffix in KEYED_SUFFIXES:
            if name.endswith(suffix):
                return nfc(name.removesuffix(suffix))
        return nfc(name)

    @property
    def is_fixed(self) -> bool:
        return self.path.name in FIXED_NAMES

    def size(self) -> int:
        if self.path.is_dir():
            return sum(file.stat().st_size for file in self.path.rglob("*") if file.is_file())
        return self.path.stat().st_size

    def as_dict(self) -> dict:
        return {"entry": self.path.name, "key": self.key, "bytes": self.size()}

    def delete(self) -> None:
        if self.path.is_dir():
            shutil.rmtree(self.path)
        else:
            self.path.unlink()


class ScratchEntries:
    def __init__(self, scratch_dir: Path, stem: str) -> None:
        self._scratch_dir = scratch_dir
        self._stem = stem

    def paths(self) -> list[Path]:
        return self._paths_for(self._stem)

    def rename_to(self, basename: str) -> None:
        for source, target in zip(self.paths(), self._paths_for(basename)):
            if source.exists() and not target.exists():
                source.rename(target)

    def _paths_for(self, stem: str) -> list[Path]:
        return [self._scratch_dir / stem] + [self._scratch_dir / f"{stem}{suffix}" for suffix in KEYED_SUFFIXES]


class ScratchSweep:
    LABEL = "stale"

    def __init__(self, scratch_dir: Path, held_keys: set[str]) -> None:
        self._scratch_dir = scratch_dir
        self._held_keys = held_keys

    def entries(self) -> list[ScratchEntry]:
        if not self._scratch_dir.exists():
            return []
        entries = (ScratchEntry(path) for path in sorted(self._scratch_dir.iterdir()))
        return [entry for entry in entries if not entry.is_fixed and entry.key not in self._held_keys]

    def delete(self, entries: list[ScratchEntry]) -> None:
        for entry in entries:
            entry.delete()


@dataclass(frozen=True)
class ReviewedWorkCache:
    path: Path

    def rebuildable(self) -> list[ScratchEntry]:
        renders = self.path.glob(f"{RENDER_PREFIX}*{RENDER_SUFFIX}")
        font_repair_caches = (self.path / name for name in FONT_REPAIR_CACHE_NAMES)
        return [ScratchEntry(path) for path in sorted([*renders, *font_repair_caches]) if path.exists()]

    def size(self) -> int:
        return sum(entry.size() for entry in self.rebuildable())

    def as_dict(self) -> dict:
        return {"entry": self.path.name, "key": nfc(self.path.name), "bytes": self.size()}

    def delete(self) -> None:
        for entry in self.rebuildable():
            entry.delete()


class ReviewedSweep:
    LABEL = "rebuildable"

    def __init__(self, scratch_dir: Path, reviewed: ReviewedBasenames) -> None:
        self._scratch_dir = scratch_dir
        self._reviewed = reviewed

    def entries(self) -> list[ReviewedWorkCache]:
        if not self._scratch_dir.exists():
            return []
        reviewed_keys = self._reviewed.keys()
        work_dirs = (path for path in sorted(self._scratch_dir.iterdir()) if path.is_dir())
        caches = (ReviewedWorkCache(path) for path in work_dirs if nfc(path.name) in reviewed_keys)
        return [cache for cache in caches if cache.rebuildable()]

    def delete(self, caches: list[ReviewedWorkCache]) -> None:
        for cache in caches:
            cache.delete()
