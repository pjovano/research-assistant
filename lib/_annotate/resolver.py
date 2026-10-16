from __future__ import annotations

import pymupdf

from .markers import PageGrids
from .notes import OMISSION, Note, NoteLedger
from .overlap import CoveredWords, OverlapResolver, runs_of
from .pages import PageBody, PageCharacters, PageLayout
from .requests import ADDED, MERGED, RECTANGLE, SKIPPED, AnnotationDecision, AnnotationRequest
from .spans import SpanGeometry, SpanNormalizer, SpanValidator, WordGrid, WordSpan

HIGHLIGHT = pymupdf.PDF_ANNOT_HIGHLIGHT


class PageWorkspace:
    def __init__(self, page, grid: WordGrid | None = None) -> None:
        self._page = page
        self._grid = WordGrid(page) if grid is None else grid
        self._layout = PageLayout(page)
        self._geometry = SpanGeometry(self._grid, PageCharacters(page))
        self._body: PageBody | None = None

    @property
    def page(self):
        return self._page

    @property
    def grid(self) -> WordGrid:
        return self._grid

    @property
    def layout(self) -> PageLayout:
        return self._layout

    @property
    def geometry(self) -> SpanGeometry:
        return self._geometry

    @property
    def body(self) -> PageBody:
        if self._body is None:
            self._body = PageBody(self._grid.boxes, self._layout)
        return self._body

    @property
    def has_text(self) -> bool:
        return len(self._grid) > 0

    def highlights(self) -> list:
        return [a for a in self._page.annots() or [] if self.is_highlight(a)]

    @staticmethod
    def is_highlight(annotation) -> bool:
        return annotation.type[0] == HIGHLIGHT


class DocumentWorkspaces:
    def __init__(self, document, grids: PageGrids | None = None) -> None:
        self._document = document
        self._grids = PageGrids(document) if grids is None else grids
        self._opened: dict[int, PageWorkspace] = {}

    def at(self, page_number: int) -> PageWorkspace:
        if page_number not in self._opened:
            self._opened[page_number] = PageWorkspace(self._document[page_number - 1], self._grids.of(page_number))
        return self._opened[page_number]


class SpanResolver:
    def __init__(self, workspace: PageWorkspace) -> None:
        self._workspace = workspace

    def resolve(self, request: AnnotationRequest) -> AnnotationDecision:
        if not self._workspace.has_text:
            return self._without_text(request)
        normalizer = SpanNormalizer(self._workspace.grid)
        return self._resolve_parts(request, [normalizer.normalized(WordSpan(request.page, start, end))
                                             for start, end in request.spans])

    def resolve_span(self, request: AnnotationRequest, span: WordSpan) -> AnnotationDecision:
        return self._resolve_parts(request, [span])

    def _resolve_parts(self, request: AnnotationRequest, parts: list[WordSpan]) -> AnnotationDecision:
        validator = SpanValidator(self._workspace.grid, self._workspace.layout)
        errors = [error for part in parts for error in validator.errors(part)]
        if errors:
            return AnnotationDecision(request, SKIPPED, detail="; ".join(errors), span=parts[0])
        return self._placed(request, parts)

    def _without_text(self, request: AnnotationRequest) -> AnnotationDecision:
        if not request.is_rectangle:
            return AnnotationDecision(request, SKIPPED,
                                      detail="page has no text layer and no rectangle was given")
        return AnnotationDecision(request, RECTANGLE, covered_text="(no text layer)",
                                  quads=[pymupdf.Rect(request.rect).quad])

    def _placed(self, request: AnnotationRequest, parts: list[WordSpan]) -> AnnotationDecision:
        geometry = self._workspace.geometry
        covered = OMISSION.join(geometry.text(part) for part in parts)
        indices = set().union(*(part.indices for part in parts))
        target = OverlapResolver(self._workspace.grid).target(indices, self._workspace.highlights())
        if target is not None:
            return AnnotationDecision(request, MERGED, covered_text=covered, target=target, span=parts[0],
                                      detail=self._merge_detail(NoteLedger.of(target), request.note),
                                      quads=self._extension(request.page, indices, target))
        return AnnotationDecision(request, ADDED, covered_text=covered, span=parts[0],
                                  quads=[quad for part in parts for quad in geometry.quads(part)])

    def _extension(self, page: int, indices: set[int], target) -> list:
        covered = CoveredWords(self._workspace.grid).of(target)
        if indices <= covered:
            return []
        return [quad for start, end in runs_of(indices | covered)
                for quad in self._workspace.geometry.quads(WordSpan(page, start, end))]

    def _merge_detail(self, ledger: NoteLedger, note: Note) -> str:
        if note.link and ledger.mentions(note.link):
            outcome = "note rewritten" if ledger.appended(note) != ledger.rendered() else "note left unchanged"
            return f"existing highlight already cites {note.link}; {outcome}"
        return f"appended to an existing highlight carrying {len(ledger.entries)} note(s)"
