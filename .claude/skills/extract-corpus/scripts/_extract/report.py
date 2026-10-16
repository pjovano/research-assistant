from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pagetext

from _extract.build import CorpusBuild
from _extract.checks import STATUS_OMITTED, PageVerdict
from _extract.console import FORCE_OCR_FLAG
from _extract.layer import TextLayer
from _extract.outline import Outline
from _extract.paths import CorpusFile
from _extract.ranges import PageRanges
from _extract.renders import PageRenders
from _extract.repairs import FontRepairRecord
from _extract.trial import TrialNote

SCANNED_TEXT_SHARE = 0.2


@dataclass(frozen=True)
class WrittenBody:
    path: Path
    trial: bool
    replaced: bool


def reads_as_scan(layer: TextLayer) -> bool:
    page_count = layer.page_count()
    drawn = sum(layer.has_text(page) and layer.is_drawn(page) for page in range(1, page_count + 1))
    return page_count > 0 and drawn / page_count < SCANNED_TEXT_SHARE


class ProbeReport:
    def __init__(self, pdf_path: Path, note: CorpusFile) -> None:
        self._pdf_path = pdf_path
        self._note = note
        self._layer = TextLayer(pdf_path)

    def as_dict(self) -> dict:
        page_count = self._layer.page_count()
        pages = range(1, page_count + 1)
        with_text = sum(self._layer.has_text(page) for page in pages)
        scanned = reads_as_scan(self._layer)
        return {
            "pdf": self._pdf_path.name,
            "corpus_file": str(self._note.path),
            "note_exists": self._note.path.is_file(),
            "body_exists": self._note.has_body(),
            "reviewed": self._note.reviewed(),
            "trial_exists": TrialNote(self._note).exists(),
            "page_count": page_count,
            "pages_with_text": with_text,
            "scanned": scanned,
            "recommended_flags": [FORCE_OCR_FLAG] if scanned else [],
            "headings": [self._heading(heading) for heading in Outline(self._pdf_path).headings()],
            "font_repairs": FontRepairRecord(self._pdf_path).entries(),
        }

    def _heading(self, heading) -> dict:
        return {"level": heading.level, "title": heading.title, "file_page": heading.file_page}


class DoubtfulReport:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def as_list(self, doubtful: list[PageVerdict]) -> list[dict]:
        pages = [verdict.file_page for verdict in doubtful]
        renders = PageRenders(self._pdf_path).by_page(pages)
        return [{"file_page": verdict.file_page,
                 "folio": pagetext.printed_page_label(self._pdf_path, verdict.file_page),
                 "reason": verdict.reason, "render": renders.get(verdict.file_page)} for verdict in doubtful]


class ExtractReport:
    def __init__(self, build: CorpusBuild, written: WrittenBody) -> None:
        self._build = build
        self._written = written

    def as_dict(self) -> dict:
        verdicts = self._build.verdicts()
        return {
            "written": str(self._written.path),
            "trial": self._written.trial,
            "replaced": self._written.replaced,
            "pages": len(verdicts),
            "omitted_pages": [verdict.file_page for verdict in verdicts if verdict.status == STATUS_OMITTED],
            "read_from_pixels": PageRanges().compact(self._build.pixel_pages()),
            "extraction": self._build.extraction_fields(),
            "footnote_log": self._build.structure().footnote_log(),
            "folio_log": self._build.folio_log(),
            "notation_blocks": self._build.notation_blocks(),
            "notation_log": self._build.structure().notation_log(),
        }
