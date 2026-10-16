from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

LABEL_GOOD = "good"
LABEL_BAD = "bad"
LABEL_UNAVAILABLE = "unavailable"


class ClassifierUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ClassifierVerdict:
    label: str
    score: float

    @property
    def is_bad(self) -> bool:
        return self.label == LABEL_BAD


def surya_predictor() -> Callable:
    from surya.ocr_error import OCRErrorPredictor
    return OCRErrorPredictor()


class PageClassifier:
    def __init__(self, predictor_factory: Callable[[], Callable] = surya_predictor) -> None:
        self._predictor_factory = predictor_factory
        self._predictor = None

    def judge(self, text: str) -> ClassifierVerdict:
        [verdict] = self.judge_all([text])
        return verdict

    def judge_all(self, texts: list[str]) -> list[ClassifierVerdict]:
        if not texts:
            return []
        result = self._read(texts)
        self._require_one_reading_per_text(result, len(texts))
        return [ClassifierVerdict(label, float(score)) for label, score in zip(result.labels, result.scores)]

    def _read(self, texts: list[str]):
        try:
            return self._started_predictor()(list(texts))
        except Exception as failure:
            raise ClassifierUnavailable(f"{type(failure).__name__}: {failure}") from failure

    @staticmethod
    def _require_one_reading_per_text(result, expected: int) -> None:
        if len(result.labels) != expected or len(result.scores) != expected:
            raise ClassifierUnavailable(f"{len(result.labels)} readings returned for {expected} pages")

    def _started_predictor(self) -> Callable:
        if self._predictor is None:
            self._predictor = self._predictor_factory()
        return self._predictor
