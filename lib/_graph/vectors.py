from __future__ import annotations

import math
from typing import Protocol


class VectorSource(Protocol):
    def vectors_of(self, basename: str) -> list[list[float]]: ...


class StoredCentroids:
    def __init__(self, source: VectorSource) -> None:
        self._source = source

    def centroid(self, basename: str) -> list[float] | None:
        vectors = self._source.vectors_of(basename)
        if not vectors:
            return None
        return [sum(column) / len(vectors) for column in zip(*vectors)]


class NoVectors:
    def centroid(self, basename: str) -> list[float] | None:
        return None


def cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norms = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norms if norms else 0.0
