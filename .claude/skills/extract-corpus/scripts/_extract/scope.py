from __future__ import annotations

from pathlib import Path

import pagetext

from _extract.edgelines import RecurringEdgeLines
from _extract.enginelabels import CachedLabels, LabelledRun
from _extract.failures import UsageFailure
from _extract.firstlines import LayerFirstLines
from _extract.indexruns import IndexRuns
from _extract.layer import TextLayer
from _extract.matter import MatterPages
from _extract.outline import Heading, Outline
from _extract.paths import CorpusFile
from _extract.renders import JudgingRenders
from _extract.request import ExtractionRequest
from _extract.spans import ExcludedSpans, ScopePoints

MAX_SCOPE_LEVEL = 2
OPENING_PAGES = 3
CLOSING_PAGES = 3
WORK_FIELDS = ("title", "author", "year", "orig_year", "type")


class ScopeMissing(UsageFailure, ValueError):
    pass


class PageOutsideThePdf(UsageFailure, ValueError):
    pass


class ScopeListing:
    def __init__(self, pdf_path: Path, note: CorpusFile, named_pages: tuple[int, ...] = ()) -> None:
        self._pdf_path = pdf_path
        self._note = note
        self._named_pages = named_pages
        self._layer = TextLayer(pdf_path)
        self._headings = Outline(pdf_path).headings()
        self._first_lines = LayerFirstLines(self._layer)
        self._edge_lines = RecurringEdgeLines(self._layer)

    def as_dict(self) -> dict:
        meta = self._note.frontmatter()
        sections = self._sections()
        runs = self._pre_labelled_runs()
        pages = self._judged_pages(sections, runs or [])
        renders = JudgingRenders(self._pdf_path, self._layer).by_page(pages)
        return {"work": {field: meta.get(field) for field in WORK_FIELDS},
                "sections": [self._section(heading, last) for heading, last in sections],
                "pre_labelled": None if runs is None else [run.as_dict() for run in runs],
                "pages": [self._page(page, renders) for page in pages]}

    def _pre_labelled_runs(self) -> list[LabelledRun] | None:
        engine_runs = CachedLabels(self._pdf_path, self._layer.page_count()).runs()
        index_runs = IndexRuns(self._first_lines, self._headings).runs()
        if engine_runs is None and not index_runs:
            return None
        return sorted((engine_runs or []) + index_runs, key=lambda run: (run.first_page, run.label))

    def _judged_pages(self, sections: list[tuple[Heading, int]], runs: list[LabelledRun]) -> list[int]:
        run_edges = [page for run in runs for page in (run.first_page, run.last_page)]
        marked_pages = run_edges + MatterPages(self._first_lines, sections).all() + self._checked_named_pages()
        return JudgedPages(sections, self._layer.page_count(), marked_pages).all()

    def _checked_named_pages(self) -> list[int]:
        page_count = self._layer.page_count()
        outside = [page for page in self._named_pages if not 1 <= page <= page_count]
        if outside:
            raise PageOutsideThePdf(f"{self._pdf_path.name} has {page_count} file pages; no file page {outside[0]}")
        return list(self._named_pages)

    def _sections(self) -> list[tuple[Heading, int]]:
        page_count = self._layer.page_count()
        return [(heading, self._last_page(self._headings, index, page_count))
                for index, heading in enumerate(self._headings) if heading.level <= MAX_SCOPE_LEVEL]

    @staticmethod
    def _last_page(headings: list[Heading], index: int, page_count: int) -> int:
        level = headings[index].level
        later = (heading.file_page for heading in headings[index + 1:] if heading.level <= level)
        return max(headings[index].file_page, next(later, page_count + 1) - 1)

    @staticmethod
    def _section(heading: Heading, last_page: int) -> dict:
        return {"entry": f"{heading.file_page}: {heading.title}", "level": heading.level,
                "first_page": heading.file_page, "last_page": last_page}

    def _page(self, file_page: int, renders: dict[int, str]) -> dict:
        return {"file_page": file_page, "folio": pagetext.printed_page_label(self._pdf_path, file_page),
                "render": renders.get(file_page),
                "lines": self._edge_lines.stripped([line.text for line in self._layer.lines(file_page) if line.text.strip()])}


class JudgedPages:
    def __init__(self, sections: list[tuple[Heading, int]], page_count: int, marked_pages: list[int]) -> None:
        self._openings = [heading.file_page for heading, _last in sections]
        self._page_count = page_count
        self._marked_pages = marked_pages

    def all(self) -> list[int]:
        return sorted(set(self._before_the_first_section() + self._openings + self._marked_pages + self._closing()))

    def _before_the_first_section(self) -> list[int]:
        last = self._openings[0] if self._openings else OPENING_PAGES
        return list(range(1, min(last, self._page_count) + 1))

    def _closing(self) -> list[int]:
        return list(range(max(1, self._page_count - CLOSING_PAGES + 1), self._page_count + 1))


class GivenScope:
    def __init__(self, request: ExtractionRequest) -> None:
        self._request = request

    def spans(self, pdf_path: Path) -> ExcludedSpans:
        if not self._request.scope_given:
            raise ScopeMissing(f"no scope given for {pdf_path.name}: pass --exclude START RESUME for each excluded "
                               "span, or --exclude-nothing; run scope first to list the pages to judge")
        return ScopePoints(TextLayer(pdf_path)).spans(list(self._request.excluded))
