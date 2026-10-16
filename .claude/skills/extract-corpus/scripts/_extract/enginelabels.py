from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from _extract.blocks import DocumentBlocks, PageBlocks
from _extract.cache import MarkerCache
from _extract.engine import MODE_FORCED_OCR, MODE_TEXT_LAYER

CONTENTS_KIND = "TableOfContents"
BIBLIOGRAPHY_KIND = "Bibliography"
BLANK_LABEL = "blank"
LABELLED_KINDS = (CONTENTS_KIND, BIBLIOGRAPHY_KIND)


@dataclass(frozen=True)
class LabelledRun:
    first_page: int
    last_page: int
    label: str

    def as_dict(self) -> dict:
        return {"first_page": self.first_page, "last_page": self.last_page, "label": self.label}

    def extended_to(self, file_page: int) -> LabelledRun:
        return LabelledRun(self.first_page, file_page, self.label)


class EngineLabels:
    def __init__(self, blocks: DocumentBlocks) -> None:
        self._pages = blocks.pages

    def runs(self) -> list[LabelledRun]:
        found = [run for label in (*LABELLED_KINDS, BLANK_LABEL) for run in self._runs_of(label)]
        return sorted(found, key=lambda run: (run.first_page, run.label))

    def _runs_of(self, label: str) -> list[LabelledRun]:
        runs: list[LabelledRun] = []
        for page in self._pages:
            if self._carries(page, label):
                self._extend(runs, page.file_page, label)
        return runs

    @staticmethod
    def _carries(page: PageBlocks, label: str) -> bool:
        if label == BLANK_LABEL:
            return not page.content
        return bool(page.of_kind(label))

    @staticmethod
    def _extend(runs: list[LabelledRun], file_page: int, label: str) -> None:
        if runs and runs[-1].last_page + 1 == file_page:
            runs[-1] = runs[-1].extended_to(file_page)
        else:
            runs.append(LabelledRun(file_page, file_page, label))


class CachedLabels:
    def __init__(self, pdf_path: Path, page_count: int) -> None:
        self._pdf_path = pdf_path
        self._all_pages = list(range(1, page_count + 1))

    def runs(self) -> list[LabelledRun] | None:
        for mode in (MODE_TEXT_LAYER, MODE_FORCED_OCR):
            payload = MarkerCache(self._pdf_path, mode).load(self._all_pages)
            if payload is not None:
                return EngineLabels(DocumentBlocks.from_json(payload, self._all_pages)).runs()
        return None
