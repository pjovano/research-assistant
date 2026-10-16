from __future__ import annotations

import math
from dataclasses import dataclass

from _graph.store import CitationRow, held_key
from _graph.vectors import cosine

DIRECT_WEIGHT = 0.35
COUPLING_WEIGHT = 0.30
COCITATION_WEIGHT = 0.15
EMBEDDING_WEIGHT = 0.20
SHARED_AUTHOR_FACTOR = 0.5
NO_SIGNAL = 0.0
FULL_SIGNAL = 1.0


@dataclass(frozen=True)
class Signals:
    direct: float
    coupling: float
    cocitation: float
    embedding: float

    def combined(self) -> float:
        return (DIRECT_WEIGHT * self.direct + COUPLING_WEIGHT * self.coupling
                + COCITATION_WEIGHT * self.cocitation + EMBEDDING_WEIGHT * self.embedding)

    def as_dict(self) -> dict:
        return {"direct": self.direct, "coupling": round(self.coupling, 4), "cocitation": round(self.cocitation, 4),
                "embedding": round(self.embedding, 4)}


class ReferenceSets:
    def __init__(self, rows: list[CitationRow]) -> None:
        self._references: dict[str, set[str]] = {}
        self._citers: dict[str, set[str]] = {}
        for row in rows:
            self._references.setdefault(row.citing, set()).add(row.cited)
            self._citers.setdefault(row.cited, set()).add(row.citing)

    def references_of(self, basename: str) -> set[str]:
        return set(self._references.get(basename, set()))

    def citers_of(self, basename: str) -> set[str]:
        return set(self._citers.get(held_key(basename), set()))

    def cites(self, citing: str, cited: str) -> bool:
        return held_key(cited) in self._references.get(citing, set())

    def shared_references(self, left: str, right: str) -> set[str]:
        return self._references.get(left, set()) & self._references.get(right, set())


class Centroids:
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self._vectors = vectors

    def similarity(self, left: str, right: str) -> float:
        if left not in self._vectors or right not in self._vectors:
            return NO_SIGNAL
        return max(NO_SIGNAL, cosine(self._vectors[left], self._vectors[right]))


class PairSignals:
    def __init__(self, references: ReferenceSets, centroids: Centroids, surnames: dict[str, frozenset[str]]) -> None:
        self._references = references
        self._centroids = centroids
        self._surnames = surnames

    def between(self, left: str, right: str) -> Signals:
        return Signals(self._direct(left, right), self._coupling(left, right), self._cocitation(left, right),
                       self._centroids.similarity(left, right))

    def _direct(self, left: str, right: str) -> float:
        cited = self._references.cites(left, right) or self._references.cites(right, left)
        if not cited:
            return NO_SIGNAL
        return SHARED_AUTHOR_FACTOR if self._share_an_author(left, right) else FULL_SIGNAL

    def _share_an_author(self, left: str, right: str) -> bool:
        return bool(self._surnames.get(left, frozenset()) & self._surnames.get(right, frozenset()))

    def _coupling(self, left: str, right: str) -> float:
        return self._salton(self._references.references_of(left), self._references.references_of(right))

    def _cocitation(self, left: str, right: str) -> float:
        return self._salton(self._references.citers_of(left), self._references.citers_of(right))

    @staticmethod
    def _salton(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return NO_SIGNAL
        return len(left & right) / math.sqrt(len(left) * len(right))
