from __future__ import annotations

import difflib
import os
import random
from dataclasses import dataclass, replace
from multiprocessing import get_context
from pathlib import Path
from typing import Callable

import vault

from _extract.acceptance import unlinked
from _extract.regressbaseline import REGRESSIONS_DIR_NAME, CorpusReference
from _extract.build import ConversionNotCached, CorpusBuild, DoubtfulPagesRemain
from _extract.cache import MarkerCache
from _extract.engine import MODE_FORCED_OCR, MODE_TEXT_LAYER
from _extract.layer import TextLayer
from _extract.paths import CorpusFile, LibraryPdfs
from _extract.records import ExtractionRecords
from _extract.request import ExtractionRequest
from _extract.wordchanges import WordChanges

SAMPLE_SIZE = 12
CORES_LEFT_FREE = 1
DEFAULT_JOBS = max(1, (os.cpu_count() or 1) - CORES_LEFT_FREE)
_START_METHOD = "spawn"
_WORKS_PER_TASK = 1
DIFF_SUFFIX = ".diff"
STATE_UNCHANGED = "unchanged"
STATE_CHANGED = "changed"
STATE_DOUBTFUL = "doubtful"
STATE_NO_BASELINE = "no-baseline"
_DIFF_HEADER_PREFIXES = ("---", "+++")
_ENCODING = "utf-8"

Builder = Callable[[Path, CorpusFile, ExtractionRequest], CorpusBuild]
Chooser = Callable[[list[Path], int], list[Path]]


class CachedConversion:
    def holds(self, pdf_path: Path) -> bool:
        request = ExtractionRecords().request_of(vault.basename_of(pdf_path))
        mode = MODE_FORCED_OCR if request.force_ocr else MODE_TEXT_LAYER
        all_pages = list(range(1, TextLayer(pdf_path).page_count() + 1))
        return MarkerCache(pdf_path, mode).holds(all_pages)


@dataclass(frozen=True)
class SampleChoice:
    cached: Callable[[Path], bool] = CachedConversion().holds
    chooser: Chooser = random.sample


class RegressionSample:
    def __init__(self, reviewed: list[Path], size: int, choice: SampleChoice = SampleChoice()) -> None:
        self._reviewed = reviewed
        self._size = size
        self._cached = choice.cached
        self._chooser = choice.chooser

    def chosen(self) -> list[Path]:
        cached = [pdf for pdf in self._reviewed if self._cached(pdf)]
        uncached = [pdf for pdf in self._reviewed if pdf not in cached]
        taken = self._chooser(cached, min(len(cached), self._size))
        filled = self._chooser(uncached, min(len(uncached), self._size - len(taken)))
        return sorted(taken) + sorted(filled)

    def as_dict(self, chosen: list[Path]) -> dict:
        cached = sum(1 for pdf in chosen if self._cached(pdf))
        return {"reviewed": len(self._reviewed), "cached": cached, "random": len(chosen) - cached}


class ReviewedWorks:
    def all(self) -> list[Path]:
        return [pdf for pdf in LibraryPdfs().all() if self.marks(pdf)]

    @staticmethod
    def marks(pdf_path: Path) -> bool:
        note = CorpusFile(pdf_path)
        return note.path.is_file() and note.reviewed() is not None


class RegressionCheck:
    def __init__(self, builder: Builder, jobs: int = 1, reference: CorpusReference | None = None) -> None:
        self._builder = builder
        self._jobs = jobs
        self._reference = reference or CorpusReference()

    def run(self, pdf_paths: list[Path]) -> list[dict]:
        if self._runs_in_parallel(pdf_paths):
            return self._run_in_parallel(pdf_paths)
        return [self.checked(pdf_path) for pdf_path in pdf_paths]

    def _runs_in_parallel(self, pdf_paths: list[Path]) -> bool:
        return self._jobs > 1 and len(pdf_paths) > 1

    def _run_in_parallel(self, pdf_paths: list[Path]) -> list[dict]:
        from_cache = CachedRebuildPool(self, self._jobs).checked(pdf_paths)
        return [checked if checked is not None else self.checked(pdf_path)
                for pdf_path, checked in zip(pdf_paths, from_cache)]

    def checked(self, pdf_path: Path) -> dict:
        note = CorpusFile(pdf_path).require_note()
        return self._compared(pdf_path, note, self._request_of(note))

    def checked_from_cache(self, pdf_path: Path) -> dict | None:
        note = CorpusFile(pdf_path).require_note()
        try:
            return self._compared(pdf_path, note, replace(self._request_of(note), cache_only=True))
        except ConversionNotCached:
            return None

    @staticmethod
    def _request_of(note: CorpusFile) -> ExtractionRequest:
        return ExtractionRecords().request_of(note.basename)

    def _compared(self, pdf_path: Path, note: CorpusFile, request: ExtractionRequest) -> dict:
        try:
            rendered = self._builder(pdf_path, note, request).rendered()
        except DoubtfulPagesRemain as remaining:
            return {"work": note.basename, "state": STATE_DOUBTFUL,
                    "doubtful_pages": [verdict.file_page for verdict in remaining.verdicts]}
        self._reference.keep(note, rendered.text)
        stored = self._reference.stored(note)
        if stored is None:
            return {"work": note.basename, "state": STATE_NO_BASELINE}
        return BodyComparison(note, rendered.text, stored).as_dict()


class CachedRebuildPool:
    def __init__(self, check: RegressionCheck, jobs: int) -> None:
        self._check = check
        self._jobs = jobs

    def checked(self, pdf_paths: list[Path]) -> list[dict | None]:
        processes = min(self._jobs, len(pdf_paths))
        with get_context(_START_METHOD).Pool(processes, initializer=VaultPaths.current().restore) as pool:
            return pool.map(self._check.checked_from_cache, pdf_paths, chunksize=_WORKS_PER_TASK)


class VaultPaths:
    def __init__(self, paths: dict[str, Path]) -> None:
        self._paths = paths

    @classmethod
    def current(cls) -> VaultPaths:
        return cls({name: getattr(vault, name) for name in vault.RESOLVED_PATH_NAMES})

    def restore(self) -> None:
        for name, path in self._paths.items():
            setattr(vault, name, path)


class BodyComparison:
    def __init__(self, note: CorpusFile, rebuilt: str, stored: str | None = None) -> None:
        self._note = note
        self._stored = unlinked(note.body()) if stored is None else stored
        self._rebuilt = rebuilt.strip()

    def as_dict(self) -> dict:
        if self._stored == self._rebuilt:
            return {"work": self._note.basename, "state": STATE_UNCHANGED}
        diff = self._diff_lines()
        return {"work": self._note.basename, "state": STATE_CHANGED, "diff": str(self._written(diff)),
                "changed_lines": sum(1 for line in diff if self._is_change(line)),
                "word_changes": WordChanges(self._stored, self._rebuilt).count()}

    def _diff_lines(self) -> list[str]:
        return list(difflib.unified_diff(self._stored.splitlines(), self._rebuilt.splitlines(),
                                         fromfile="accepted", tofile="rebuilt", lineterm=""))

    @staticmethod
    def _is_change(line: str) -> bool:
        return line[:1] in "+-" and not line.startswith(_DIFF_HEADER_PREFIXES)

    def _written(self, diff: list[str]) -> Path:
        path = vault.SCRATCH_DIR / REGRESSIONS_DIR_NAME / f"{self._note.basename}{DIFF_SUFFIX}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(diff) + "\n", encoding=_ENCODING)
        return path
