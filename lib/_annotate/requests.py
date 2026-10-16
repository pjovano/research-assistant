from __future__ import annotations

from dataclasses import dataclass, field

from .notes import Note
from .spans import WordSpan

ADDED = "added"
MERGED = "merged"
SKIPPED = "skipped"
RECTANGLE = "rectangle"
UNRESOLVED_END = "…"


@dataclass(frozen=True)
class AnnotationRequest:
    page: int
    start: int
    end: int
    note: Note
    rect: tuple | None = None
    colour: tuple | None = None
    end_page: int | None = None
    further: tuple[tuple[int, int], ...] = ()

    @property
    def spans(self) -> tuple[tuple[int, int], ...]:
        return ((self.start, self.end), *self.further)

    @property
    def is_rectangle(self) -> bool:
        return self.rect is not None

    @property
    def is_cross_page(self) -> bool:
        return self.end_page is not None

    @property
    def page_label(self) -> str:
        if self.is_cross_page:
            return f"p{self.page}–{self.end_page}"
        return f"p{self.page}"


@dataclass(frozen=True)
class AnnotationDecision:
    request: AnnotationRequest
    action: str
    covered_text: str = ""
    detail: str = ""
    quads: list = field(default_factory=list)
    target: object | None = None
    span: WordSpan | None = None
    continuation: "AnnotationDecision | None" = None

    @property
    def writes(self) -> bool:
        return self.action in (ADDED, MERGED, RECTANGLE)

    @property
    def page(self) -> int:
        return self.span.page if self.span is not None else self.request.page

    @property
    def halves(self) -> list["AnnotationDecision"]:
        if self.continuation is None:
            return [self]
        return [self, self.continuation]


class DecisionReport:
    def __init__(self, decisions: list[AnnotationDecision]) -> None:
        self._decisions = decisions

    @property
    def decisions(self) -> list[AnnotationDecision]:
        return list(self._decisions)

    @property
    def writes(self) -> bool:
        return any(decision.writes for decision in self._decisions)

    def counts(self) -> dict[str, int]:
        tally: dict[str, int] = {}
        for decision in self._decisions:
            tally[decision.action] = tally.get(decision.action, 0) + 1
        return tally

    def rendered(self) -> str:
        lines = [self._line(d) for d in self._decisions]
        return "\n".join(lines + ["", self._summary()])

    def _line(self, decision: AnnotationDecision) -> str:
        request = decision.request
        head = f"{request.page_label} [{self._range(decision)}] {self._action(decision)}"
        detail = self._detail(decision)
        return f"{head}\n    text: {self._text(decision)}\n    note: {request.note.rendered}" + \
               (f"\n    detail: {detail}" if detail else "")

    def _range(self, decision: AnnotationDecision) -> str:
        request = decision.request
        if not request.is_cross_page:
            return " + ".join(f"{start}:{end}" for start, end in request.spans)
        if decision.continuation is None:
            return f"{request.start}:{UNRESOLVED_END} | {UNRESOLVED_END}:{request.end}"
        return " | ".join(f"{half.span.start}:{half.span.end}" for half in decision.halves)

    def _action(self, decision: AnnotationDecision) -> str:
        actions = []
        for half in decision.halves:
            if half.action.upper() not in actions:
                actions.append(half.action.upper())
        return "+".join(actions)

    def _text(self, decision: AnnotationDecision) -> str:
        return " ".join(half.covered_text for half in decision.halves if half.covered_text)

    def _detail(self, decision: AnnotationDecision) -> str:
        return "; ".join(self._half_detail(half) for half in decision.halves if half.detail)

    @staticmethod
    def _half_detail(half: AnnotationDecision) -> str:
        extended = half.action == MERGED and half.quads
        return f"{half.detail}; highlight extended over the passage" if extended else half.detail

    def _summary(self) -> str:
        counts = self.counts()
        return " ".join(f"{action}={count}" for action, count in sorted(counts.items()))
