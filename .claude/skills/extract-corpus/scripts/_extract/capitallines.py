from __future__ import annotations

import dataclasses

from _extract.layer import LayerLine
from _extract.layerlines import sets_a_drop_capital


class DropCapitalLines:
    def __init__(self, lines: list[LayerLine]) -> None:
        self._lines = lines

    def folded(self) -> list[LayerLine]:
        replaced: dict[int, LayerLine | None] = {}
        for capital in self._lines:
            beside = self._beside(capital)
            if _is_dropped_beside(capital, beside):
                replaced[id(capital)] = None
                replaced.update(_opened_by(capital, beside))
        kept = (replaced.get(id(line), line) for line in self._lines)
        return [line for line in kept if line is not None]

    def _beside(self, capital: LayerLine) -> list[LayerLine]:
        box = capital.box
        return sorted((line for line in self._lines
                       if line is not capital and box.top <= line.center[1] <= box.bottom and line.x0 > box.center[0]),
                      key=lambda line: line.y0)


def _is_dropped_beside(capital: LayerLine, beside: list[LayerLine]) -> bool:
    is_one_letter = len(capital.text.strip()) == 1
    return is_one_letter and sets_a_drop_capital(capital.box.height, [line.box.height for line in beside])


def _opened_by(capital: LayerLine, beside: list[LayerLine]) -> dict[int, LayerLine]:
    first, *rest = beside
    opened = dataclasses.replace(first, text=capital.text.strip() + first.text.lstrip(), x0=capital.x0)
    return {id(first): opened, **{id(line): dataclasses.replace(line, x0=capital.x0) for line in rest}}
