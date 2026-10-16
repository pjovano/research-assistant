from __future__ import annotations

from _graph.library import LibraryGraph, ScoredPair

DEFAULT_NEIGHBOURS = 10
SHARED_REFERENCES_SHOWN = 5


class Neighbourhood:
    def __init__(self, graph: LibraryGraph, count: int = DEFAULT_NEIGHBOURS) -> None:
        self._graph = graph
        self._count = count

    def of(self, basename: str) -> dict:
        if not self._graph.holds(basename):
            raise LookupError(f"'{basename}' has no corpus file")
        nearest = self._graph.pairs_of(basename)[:self._count]
        return {"basename": basename, "neighbours": [self._described(pair) for pair in nearest],
                "bibliographies": self._tally(nearest)}

    def _described(self, pair: ScoredPair) -> dict:
        shared = self._graph.shared_references(pair.left, pair.right)
        return {"basename": pair.right, "score": round(pair.score, 4), "signals": pair.signals.as_dict(),
                "shared_references": shared[:SHARED_REFERENCES_SHOWN], "shared_reference_count": len(shared),
                "bibliographies": self._graph.bibliographies_of(pair.right)}

    def _tally(self, nearest: list[ScoredPair]) -> dict[str, float]:
        weights: dict[str, float] = {}
        for pair in nearest:
            for name in self._graph.bibliographies_of(pair.right):
                weights[name] = weights.get(name, 0.0) + pair.score
        return {name: round(weight, 4) for name, weight in sorted(weights.items(), key=lambda item: -item[1])}
