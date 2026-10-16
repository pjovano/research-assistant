from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass

from _pagetext.classifier import LABEL_UNAVAILABLE, ClassifierUnavailable, ClassifierVerdict, PageClassifier

MIN_CHARS_FOR_ASSESSMENT = 200
MIN_TOKENS_FOR_ASSESSMENT = 50
MIN_CHARS_PER_PAGE = 100
MIN_ALPHA_RATIO = 0.55
MAX_REPLACEMENT_RATIO = 0.01
RATIO_PRECISION = 3

VERDICT_GOOD = "good"
VERDICT_POOR = "poor"
VERDICT_EMPTY = "empty"
VERDICT_UNAVAILABLE = "unavailable"

_TOKEN_RE = re.compile(r"[^\W\d_]+")
_WHITESPACE_RE = re.compile(r"\s")
_REPLACEMENT_CHARACTER = "�"
_CONTROL_CATEGORY = "Cc"
_PUNCTUATION_CATEGORY = "P"


@dataclass
class Quality:
    chars: int
    tokens: int
    alpha_ratio: float
    replacement_ratio: float
    classifier_label: str
    classifier_score: float | None
    verdict: str
    reason: str

    @property
    def is_good(self) -> bool:
        return self.verdict == VERDICT_GOOD

    @property
    def is_empty(self) -> bool:
        return self.verdict == VERDICT_EMPTY

    def as_dict(self) -> dict:
        return asdict(self)


class _Characters:
    def __init__(self, text: str) -> None:
        self._inked = _WHITESPACE_RE.sub("", text)

    @property
    def count(self) -> int:
        return len(self._inked)

    @property
    def alpha_ratio(self) -> float:
        judged = [c for c in self._inked if not self._is_neutral(c)]
        return sum(c.isalpha() for c in judged) / max(len(judged), 1)

    @property
    def replacement_ratio(self) -> float:
        return sum(self._is_damaged(c) for c in self._inked) / max(self.count, 1)

    def _is_neutral(self, character: str) -> bool:
        return character.isdigit() or unicodedata.category(character).startswith(_PUNCTUATION_CATEGORY)

    def _is_damaged(self, character: str) -> bool:
        return character == _REPLACEMENT_CHARACTER or unicodedata.category(character) == _CONTROL_CATEGORY


class _HardSignals:
    def __init__(self, text: str) -> None:
        self._characters = _Characters(text)

    @property
    def alpha_ratio(self) -> float:
        return self._characters.alpha_ratio

    @property
    def replacement_ratio(self) -> float:
        return self._characters.replacement_ratio

    def failures(self) -> list[str]:
        checks = (
            (self.alpha_ratio < MIN_ALPHA_RATIO,
             f"alphabetic character ratio {self.alpha_ratio:.3f} < {MIN_ALPHA_RATIO}"),
            (self.replacement_ratio > MAX_REPLACEMENT_RATIO,
             f"replacement character ratio {self.replacement_ratio:.3f} > {MAX_REPLACEMENT_RATIO}"),
        )
        return [reason for failed, reason in checks if failed]


class _Verdict:
    def __init__(self, failures: list[str], unavailable_cause: str | None = None) -> None:
        self._failures = failures
        self._unavailable_cause = unavailable_cause

    @property
    def name(self) -> str:
        if self._failures:
            return VERDICT_POOR
        if self._unavailable_cause is not None:
            return VERDICT_UNAVAILABLE
        return VERDICT_GOOD

    @property
    def reason(self) -> str:
        notes = list(self._failures)
        if self._unavailable_cause is not None:
            notes.append(f"classifier unavailable: {self._unavailable_cause}")
        return "; ".join(notes) or "text layer reads as natural-language prose"


class QualityMeasure:
    def __init__(self, text: str, pages: int) -> None:
        self._text = text
        self._pages = max(pages, 1)
        self._signals = _HardSignals(text)
        self._tokens = len(_TOKEN_RE.findall(text))
        self._chars = _Characters(text).count

    @property
    def text(self) -> str:
        return self._text

    def settled(self) -> Quality | None:
        return self._sparse_quality() if self._is_too_sparse() else None

    def judged(self, classified: ClassifierVerdict) -> Quality:
        failures = self._signals.failures()
        if classified.is_bad:
            failures.append(f"classifier reads the page as bad (p={classified.score:.3f})")
        return self._quality(classified.label, round(classified.score, RATIO_PRECISION), _Verdict(failures))

    def unclassified(self, cause: str) -> Quality:
        return self._quality(LABEL_UNAVAILABLE, None, _Verdict(self._signals.failures(), cause))

    def _is_too_sparse(self) -> bool:
        too_few_chars = self._chars < MIN_CHARS_FOR_ASSESSMENT
        too_few_tokens = self._tokens < MIN_TOKENS_FOR_ASSESSMENT
        too_thin = self._chars / self._pages < MIN_CHARS_PER_PAGE
        return too_few_chars or too_few_tokens or too_thin

    def _sparse_quality(self) -> Quality:
        failures = self._signals.failures() if self._chars else []
        if failures:
            return self._quality(LABEL_UNAVAILABLE, None, _Verdict(failures))
        return self._empty()

    def _empty(self) -> Quality:
        return Quality(self._chars, self._tokens, 0.0, 0.0, LABEL_UNAVAILABLE, None, VERDICT_EMPTY,
                       "little or no extractable text")

    def _quality(self, label: str, score: float | None, verdict: _Verdict) -> Quality:
        return Quality(self._chars, self._tokens,
                       round(self._signals.alpha_ratio, RATIO_PRECISION),
                       round(self._signals.replacement_ratio, RATIO_PRECISION),
                       label, score, verdict.name, verdict.reason)


class QualityBatch:
    def __init__(self, texts: list[str], pages: int, classifier: PageClassifier) -> None:
        self._measures = [QualityMeasure(text, pages) for text in texts]
        self._classifier = classifier

    def results(self) -> list[Quality]:
        settled = [measure.settled() for measure in self._measures]
        pending = [index for index, quality in enumerate(settled) if quality is None]
        for index, quality in zip(pending, self._classified(pending)):
            settled[index] = quality
        return settled

    def _classified(self, pending: list[int]) -> list[Quality]:
        if not pending:
            return []
        measures = [self._measures[index] for index in pending]
        try:
            verdicts = self._classifier.judge_all([measure.text for measure in measures])
        except ClassifierUnavailable as failure:
            return [measure.unclassified(str(failure)) for measure in measures]
        return [measure.judged(verdict) for measure, verdict in zip(measures, verdicts)]


_SHARED_CLASSIFIER = PageClassifier()


class QualityAssessment:
    @staticmethod
    def assess(text: str, *, pages: int = 1, classifier: PageClassifier | None = None) -> Quality:
        [quality] = assess_all([text], pages=pages, classifier=classifier)
        return quality

    @staticmethod
    def assess_all(texts: list[str], *, pages: int = 1, classifier: PageClassifier | None = None) -> list[Quality]:
        return QualityBatch(texts, pages, classifier or _SHARED_CLASSIFIER).results()


assess = QualityAssessment.assess
assess_all = QualityAssessment.assess_all
