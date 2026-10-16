from __future__ import annotations

import math
from dataclasses import dataclass

from .embedding import OllamaEmbedder


@dataclass(frozen=True)
class CheckPair:
    foreign: str
    english: str
    language: str


BLOCKING_PAIRS = (
    CheckPair("Das Sein ist das unbestimmte Unmittelbare", "Being is the indeterminate immediate", "German"),
    CheckPair("La liberté consiste à pouvoir faire tout ce qui ne nuit pas à autrui",
              "Liberty consists in the freedom to do everything which injures no one else", "French"),
    CheckPair("Cogito, ergo sum", "I think, therefore I am", "Latin"),
)
ADVISORY_PAIRS = (
    CheckPair("τὸ ὂν λέγεται πολλαχῶς", "Being is said in many ways", "Greek"),
)
UNRELATED_PASSAGES = ("The train leaves at seven tomorrow morning",)
PASSES = "passes"
PASSAGE = "passage"


def cosine_similarity(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    norms = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norms if norms else 0.0


@dataclass(frozen=True)
class CheckPassages:
    blocking: tuple = BLOCKING_PAIRS
    advisory: tuple = ADVISORY_PAIRS
    unrelated: tuple = UNRELATED_PASSAGES


class EmbeddingCheck:
    def __init__(self, embedder: OllamaEmbedder, passages: CheckPassages = CheckPassages()) -> None:
        self._embedder = embedder
        self._blocking = passages.blocking
        self._advisory = passages.advisory
        self._passages = self._listed(passages.blocking + passages.advisory, passages.unrelated)
        self._vectors: dict[str, list[float]] = {}

    def report(self) -> dict:
        self._vectors = dict(zip(self._passages, self._embedder.embed(self._passages)))
        blocking = self._verdicts(self._blocking)
        advisory = self._verdicts(self._advisory)
        return {"passages": blocking + advisory,
                "advisory_languages": [pair.language for pair in self._advisory],
                "advisory_failures": [verdict[PASSAGE] for verdict in advisory if not verdict[PASSES]],
                PASSES: all(verdict[PASSES] for verdict in blocking)}

    @staticmethod
    def _listed(pairs: tuple, unrelated: tuple) -> list[str]:
        return [passage for pair in pairs for passage in (pair.foreign, pair.english)] + list(unrelated)

    def _verdicts(self, pairs: tuple) -> list[dict]:
        return [self._verdict(passage, other, pair.language) for pair in pairs
                for passage, other in ((pair.foreign, pair.english), (pair.english, pair.foreign))]

    def _verdict(self, passage: str, counterpart: str, language: str) -> dict:
        pair_similarity = self._similarity(passage, counterpart)
        others = [other for other in self._passages if other not in (passage, counterpart)]
        closest = max(others, key=lambda other: self._similarity(passage, other))
        closest_similarity = self._similarity(passage, closest)
        return {PASSAGE: passage, "pair": counterpart, "language": language, "pair_similarity": pair_similarity,
                "closest_other": closest, "closest_other_similarity": closest_similarity,
                PASSES: pair_similarity > closest_similarity}

    def _similarity(self, left: str, right: str) -> float:
        return cosine_similarity(self._vectors[left], self._vectors[right])
