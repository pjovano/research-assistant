from __future__ import annotations

from _support import LiveTree

LiveTree.activate()

import pagetext


class FakeResult:
    def __init__(self, label: str, score: float, count: int) -> None:
        self.labels = [label] * count
        self.scores = [score] * count


class FakePredictor:
    def __init__(self, label: str, score: float = 0.0) -> None:
        self._label = label
        self._score = score
        self.seen: list[str] = []
        self.calls = 0

    def __call__(self, texts: list[str]) -> FakeResult:
        self.seen.extend(texts)
        self.calls += 1
        return FakeResult(self._label, self._score, len(texts))


def fake_classifier(label: str = "good", score: float = 0.0) -> pagetext.PageClassifier:
    return pagetext.PageClassifier(lambda: FakePredictor(label, score))


def failing_classifier() -> pagetext.PageClassifier:
    def refuse() -> FakePredictor:
        raise ConnectionError("no server on port 0")
    return pagetext.PageClassifier(refuse)
