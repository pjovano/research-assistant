from __future__ import annotations

from typing import Callable

from _extract.box import Box

MAX_SHAPE_ASPECT = 2.5
STROKED_TYPES = frozenset({"s", "fs"})
FILLED_TYPES = frozenset({"f", "fs"})
PAPER_COLOUR_COMPONENT = 1.0

LetteringInside = Callable[[Box], list]


class BulletShapes:
    def __init__(self, lettering_inside: LetteringInside) -> None:
        self._lettering_inside = lettering_inside

    def of(self, page) -> list[Box]:
        inked = (_painted_box(drawing) for drawing in page.get_drawings() if _paints_ink(drawing))
        return [box for box in inked if _is_compact(box) and not self._lettering_inside(box)]


def _paints_ink(drawing: dict) -> bool:
    fill = drawing.get("fill") if drawing["type"] in FILLED_TYPES else None
    stroke = drawing.get("color") if drawing["type"] in STROKED_TYPES else None
    return any(colour is not None and not _is_paper(colour) for colour in (fill, stroke))


def _is_paper(colour: tuple[float, ...]) -> bool:
    return all(component >= PAPER_COLOUR_COMPONENT for component in colour)


def _painted_box(drawing: dict) -> Box:
    rect = drawing["rect"]
    reach = (drawing.get("width") or 0.0) / 2 if drawing["type"] in STROKED_TYPES else 0.0
    return Box(rect.x0 - reach, rect.y0 - reach, rect.x1 + reach, rect.y1 + reach)


def _is_compact(box: Box) -> bool:
    shorter, longer = sorted((box.width, box.height))
    return shorter > 0 and longer <= MAX_SHAPE_ASPECT * shorter
