from __future__ import annotations

import html
import re
from dataclasses import dataclass

from _extract.arrowstacks import ArrowCommand
from _extract.enginemath import MATH_ELEMENT_RE
from _extract.notationguard import AGREED, CORRECTED, FLAGGED, FormulaRegions, NotationGuard, NotationVerdict


@dataclass(frozen=True)
class _Checked:
    file_page: int
    engine_latex: str
    layer_region: str
    verdict: NotationVerdict

    def entry(self) -> str:
        prefix = f"file p. {self.file_page}: {self.verdict.status} {self.engine_latex}"
        change = f" to {self.verdict.latex}" if self.verdict.status == CORRECTED else ""
        return f"{prefix}{change} (text layer: {self.layer_region})"


@dataclass(frozen=True)
class LayerFormulas:
    html: str
    arrow_stack: str | None = None
    drawn: bool = True


class NotationLog:
    def __init__(self) -> None:
        self._checked: dict[_Checked, None] = {}

    def record(self, checked: _Checked) -> None:
        if checked.verdict.status != AGREED:
            self._checked[checked] = None

    def entries(self) -> list[str]:
        return [checked.entry() for checked in self._checked]


class GuardedMath:
    def __init__(self, log: NotationLog) -> None:
        self._guard = NotationGuard()
        self._log = log

    def checked(self, file_page: int, engine_html: str, layer_html: str) -> str:
        return self.checked_against(file_page, engine_html, LayerFormulas(layer_html))

    def checked_against(self, file_page: int, engine_html: str, layer: LayerFormulas) -> str:
        regions = iter(FormulaRegions(engine_html, layer.html).regions())
        block = _BlockCheck(self._guard, file_page, layer)
        return MATH_ELEMENT_RE.sub(lambda element: self._element(block, element, next(regions)), engine_html)

    def _element(self, block: _BlockCheck, element: re.Match, layer_region: str) -> str:
        engine_latex = html.unescape(element.group("latex"))
        verdict = block.verdict(engine_latex, layer_region)
        self._log.record(_Checked(block.file_page, engine_latex, layer_region, verdict))
        latex = element.group("latex") if verdict.latex == engine_latex else html.escape(verdict.latex, quote=False)
        return f"<math{element.group('attributes')}>{latex}</math>"


class _BlockCheck:
    def __init__(self, guard: NotationGuard, file_page: int, layer: LayerFormulas) -> None:
        self._guard = guard
        self.file_page = file_page
        self._arrow_stack = layer.arrow_stack
        self._layer_drawn = layer.drawn

    def verdict(self, engine_latex: str, layer_region: str) -> NotationVerdict:
        verdict = self._restacked(engine_latex, layer_region) or self._guard.checked(engine_latex, layer_region)
        return verdict if self._may_take(verdict) else NotationVerdict(FLAGGED, engine_latex)

    def _may_take(self, verdict: NotationVerdict) -> bool:
        return self._layer_drawn or verdict.status != CORRECTED

    def _restacked(self, engine_latex: str, layer_region: str) -> NotationVerdict | None:
        restacked = None if self._arrow_stack is None else ArrowCommand(engine_latex).replaced(self._arrow_stack)
        if restacked is None:
            return None
        verdict = self._guard.checked(restacked, layer_region)
        return None if verdict.status == FLAGGED else NotationVerdict(CORRECTED, verdict.latex)
