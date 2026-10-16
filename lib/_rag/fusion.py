from __future__ import annotations

RRF_RANK_OFFSET = 60


class ReciprocalRankFusion:
    def __init__(self, offset: int = RRF_RANK_OFFSET) -> None:
        self._offset = offset

    def fused(self, rankings: list[list[str]]) -> list[tuple[str, float]]:
        scores: dict[str, float] = {}
        for ranking in rankings:
            for rank, chunk_id in enumerate(ranking):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (self._offset + rank)
        return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
