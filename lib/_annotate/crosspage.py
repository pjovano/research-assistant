from __future__ import annotations

from dataclasses import replace

from .pages import VisualLine
from .requests import SKIPPED, AnnotationDecision, AnnotationRequest
from .resolver import DocumentWorkspaces, PageWorkspace, SpanResolver
from .spans import SpanNormalizer, WordSpan


class CrossPageSegments:
    def __init__(self, request: AnnotationRequest, leading: PageWorkspace,
                 trailing: PageWorkspace) -> None:
        self._request = request
        self._leading = leading
        self._trailing = trailing

    def errors(self) -> list[str]:
        missing = self._missing_body()
        if missing:
            return missing
        return self._first_errors() + self._second_errors()

    def first(self) -> WordSpan:
        last_line = self._leading.body.last_line()
        raw = WordSpan(self._request.page, self._request.start, last_line.last_index + 1)
        return SpanNormalizer(self._leading.grid).advanced(raw)

    def second(self) -> WordSpan:
        first_line = self._trailing.body.first_line()
        raw = WordSpan(self._request.end_page, first_line.first_index, self._request.end)
        return SpanNormalizer(self._trailing.grid).retracted(raw)

    def _missing_body(self) -> list[str]:
        errors = []
        if self._leading.body.last_line() is None:
            errors.append(f"first segment: p{self._request.page} has no body text")
        if self._trailing.body.first_line() is None:
            errors.append(f"second segment: p{self._request.end_page} has no body text")
        return errors

    def _first_errors(self) -> list[str]:
        first, last = self._leading.body.first_line(), self._leading.body.last_line()
        start = self._request.start
        if not self._leading_body_holds(start):
            return [f"first segment: start {start} lies outside the body of "
                    f"p{self._request.page} ({self._words(first, last)})"]
        return self._empty_errors("first", self.first(), "start")

    def _second_errors(self) -> list[str]:
        first, last = self._trailing.body.first_line(), self._trailing.body.last_line()
        end = self._request.end
        if not self._trailing_body_holds_end(end):
            return [f"second segment: end {end} lies outside the body of "
                    f"p{self._request.end_page} ({self._words(first, last)})"]
        return self._empty_errors("second", self.second(), "end")

    def _leading_body_holds(self, start: int) -> bool:
        return self._leading.body.first_line().first_index <= start <= self._leading.body.last_line().last_index

    def _trailing_body_holds_end(self, end: int) -> bool:
        return self._trailing.body.first_line().first_index < end <= self._trailing.body.last_line().last_index + 1

    def _empty_errors(self, name: str, span: WordSpan, trimmed_end: str) -> list[str]:
        if span.length > 0:
            return []
        return [f"{name} segment: [{span.start}:{span.end}] on p{span.page} is empty once "
                f"pagination debris is trimmed from its {trimmed_end}"]

    def _words(self, opening: VisualLine, closing: VisualLine) -> str:
        return f"words {opening.first_index}–{closing.last_index}"


class CrossPageResolver:
    def __init__(self, leading: PageWorkspace, trailing: PageWorkspace) -> None:
        self._leading = leading
        self._trailing = trailing

    def resolve(self, request: AnnotationRequest) -> AnnotationDecision:
        segments = CrossPageSegments(request, self._leading, self._trailing)
        errors = segments.errors()
        if errors:
            return AnnotationDecision(request, SKIPPED, detail="; ".join(errors))
        first = SpanResolver(self._leading).resolve_span(request, segments.first())
        second = SpanResolver(self._trailing).resolve_span(request, segments.second())
        return self._paired(request, first, second)

    def _paired(self, request: AnnotationRequest, first: AnnotationDecision,
                second: AnnotationDecision) -> AnnotationDecision:
        if SKIPPED in (first.action, second.action):
            return AnnotationDecision(request, SKIPPED, detail=self._skip_detail(first, second))
        return replace(first, continuation=second)

    def _skip_detail(self, first: AnnotationDecision, second: AnnotationDecision) -> str:
        named = (("first", first), ("second", second))
        return "; ".join(f"{name} segment: {half.detail}" for name, half in named
                         if half.action == SKIPPED)


class RequestResolver:
    def __init__(self, workspaces: DocumentWorkspaces) -> None:
        self._workspaces = workspaces

    def resolve(self, request: AnnotationRequest) -> AnnotationDecision:
        if request.is_cross_page:
            return CrossPageResolver(self._workspaces.at(request.page),
                                     self._workspaces.at(request.end_page)).resolve(request)
        return SpanResolver(self._workspaces.at(request.page)).resolve(request)
