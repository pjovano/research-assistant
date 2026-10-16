from __future__ import annotations

import pymupdf

from .pages import RectContainment
from .notes import OMISSION
from .spans import WordGrid

MERGE_CONTAINMENT_RATIO = 0.5
VERTICES_PER_QUAD = 4


def runs_of(indices: set[int]) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    for index in sorted(indices):
        if runs and runs[-1][1] == index:
            runs[-1] = (runs[-1][0], index + 1)
        else:
            runs.append((index, index + 1))
    return runs


class CoveredWords:
    def __init__(self, grid: WordGrid) -> None:
        self._grid = grid

    def of(self, annotation) -> set[int]:
        rects = self._quad_rects(annotation)
        if not rects:
            return set()
        return {box.index for box in self._grid.boxes if self._is_covered(box, rects)}

    def text_of(self, annotation) -> str:
        return OMISSION.join(self._grid.text(start, end) for start, end in runs_of(self.of(annotation)))

    def _quad_rects(self, annotation) -> list:
        vertices = annotation.vertices or []
        if len(vertices) < VERTICES_PER_QUAD:
            return self._fallback_rects(annotation)
        return [pymupdf.Quad(vertices[start:start + VERTICES_PER_QUAD]).rect
                for start in range(0, len(vertices), VERTICES_PER_QUAD)]

    def _fallback_rects(self, annotation) -> list:
        return [annotation.rect] if annotation.rect else []

    def _is_covered(self, box, rects) -> bool:
        return any(RectContainment().holds(box.rect, rect) for rect in rects)


class OverlapResolver:
    def __init__(self, grid: WordGrid) -> None:
        self._covered = CoveredWords(grid)

    def target(self, proposed: set[int], annotations: list):
        for annotation in annotations:
            if self._containment(proposed, self._covered.of(annotation)) >= MERGE_CONTAINMENT_RATIO:
                return annotation
        return None

    def _containment(self, proposed: set[int], existing: set[int]) -> float:
        if not proposed or not existing:
            return 0.0
        return len(proposed & existing) / min(len(proposed), len(existing))
