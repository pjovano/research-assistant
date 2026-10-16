from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import pagetext
from notation import delimited_spans, without_notation
from page_marker import PageMarker

STATUS_KEPT = "kept"
STATUS_DOUBTFUL = "doubtful"
STATUS_OMITTED = "omitted"
REASON_TRANSCRIBED = "worker transcription"
REASON_UNREADABLE = "worker verdict unreadable"
REASON_PASSED = "page checks passed"
REASON_NO_LAYER = "no text layer and no output: pass --force-ocr"
REASON_EMPTY_OUTPUT = "the engine produced no text for a page whose text layer has text"
REASON_EMPTY_PIXELS = "the engine read no text from the page's pixels"
REASON_WIDE_LETTER_IN_NOTATION = "a notation span holds a wide letter, which no notation writes"
SOURCE_LAYER = "text layer"
SOURCE_PIXELS = "pixels"
SOURCE_EXCLUDED = "excluded by the scope"
SOURCE_WORKER = "worker transcription"
SOURCE_NONE = "none"
MIN_LAYER_CHARS_FOR_RATIO = 200
MIN_LAYER_CHARS_FOR_EMPTY = 100
MIN_LENGTH_RATIO = 0.5
MAX_LENGTH_RATIO = 2.5
REPEAT_WINDOW_CHARS = 120
REPEAT_STRIDE_CHARS = 40
REPEAT_SAMPLE_CHARS = 40
MAX_REPEATS = 3
_EMPHASIS_RE = re.compile(r"[*_]+")
_TABLE_MARKUP_RE = re.compile(r"^\s*\|(?:\s*:?-{3,}:?\s*\|)+\s*$|\||</?(?:table|tr|th|td)\b[^>]*>",
                              re.MULTILINE | re.IGNORECASE)
_DIGIT_RE = re.compile(r"\d")
_DIGIT_STAND_IN = "0"
_GATE_FAILS = (pagetext.VERDICT_POOR, pagetext.VERDICT_UNAVAILABLE)
_WHITESPACE_RE = re.compile(r"\s+")
_LETTER_CATEGORY = "L"
_WIDE_WIDTHS = ("W", "F")


@dataclass(frozen=True)
class PageVerdict:
    file_page: int
    status: str
    reason: str
    text: str

    @property
    def is_doubtful(self) -> bool:
        return self.status == STATUS_DOUBTFUL


@dataclass(frozen=True)
class CheckedPage:
    file_page: int
    output: str
    layer_text: str
    source: str = SOURCE_LAYER

    @classmethod
    def transcribed(cls, file_page: int, text: str) -> CheckedPage:
        return cls(file_page, text, "", SOURCE_WORKER)

    @property
    def passing_reason(self) -> str:
        return REASON_TRANSCRIBED if self.source == SOURCE_WORKER else REASON_PASSED


@dataclass(frozen=True)
class _MeasuredPage:
    page: CheckedPage
    prose: str
    failure: str | None

    @property
    def file_page(self) -> int:
        return self.page.file_page

    def verdict(self, gate_failure: str | None = None) -> PageVerdict:
        reason = self.failure or gate_failure
        if reason:
            return PageVerdict(self.file_page, STATUS_DOUBTFUL, reason, self.page.output)
        return PageVerdict(self.file_page, STATUS_KEPT, self.page.passing_reason, self.page.output)


class PageChecks:
    def __init__(self, classifier: pagetext.PageClassifier | None = None) -> None:
        self._classifier = classifier

    def verdict(self, file_page: int, output: str, layer_text: str) -> PageVerdict:
        [verdict] = self.verdicts([CheckedPage(file_page, output, layer_text)])
        return verdict

    def verdicts(self, pages: list[CheckedPage]) -> list[PageVerdict]:
        checked = [self._checked(page) for page in pages]
        gated = [page for page in checked if page.failure is None]
        failures = dict(zip((page.file_page for page in gated), self._gate_failures(gated)))
        return [page.verdict(failures.get(page.file_page)) for page in checked]

    def _checked(self, page: CheckedPage) -> _MeasuredPage:
        prose = self._prose_only(page.output)
        text = _PageText(page.layer_text.strip(), page.output, prose, page.source)
        return _MeasuredPage(page, prose, self._failure(text))

    def _gate_failures(self, gated: list[_MeasuredPage]) -> list[str | None]:
        measured = pagetext.assess_all([page.prose for page in gated], classifier=self._classifier)
        return [f"quality gate: {quality.reason}" if quality.verdict in _GATE_FAILS else None
                for quality in measured]

    def _failure(self, page: _PageText) -> str | None:
        for check in (self._no_layer, self._no_pixel_reading, self._wide_letter_in_notation, self._empty_output,
                      self._repetition, self._length_ratio):
            reason = check(page)
            if reason:
                return reason
        return None

    @staticmethod
    def _no_layer(page: _PageText) -> str | None:
        if page.source == SOURCE_NONE and not page.prose.strip():
            return REASON_NO_LAYER
        return None

    @staticmethod
    def _no_pixel_reading(page: _PageText) -> str | None:
        if page.source == SOURCE_PIXELS and not page.prose.strip():
            return REASON_EMPTY_PIXELS
        return None

    @staticmethod
    def _wide_letter_in_notation(page: _PageText) -> str | None:
        spans = [span for span in delimited_spans(page.output) if any(_is_wide_letter(char) for char in span)]
        return f"{REASON_WIDE_LETTER_IN_NOTATION}: {spans[0]!r}" if spans else None

    def _empty_output(self, page: _PageText) -> str | None:
        if len(page.layer) >= MIN_LAYER_CHARS_FOR_EMPTY and not page.prose.strip():
            return REASON_EMPTY_OUTPUT
        return None

    def _repetition(self, page: _PageText) -> str | None:
        flat = _WHITESPACE_RE.sub(" ", page.prose)
        counted = _DIGIT_RE.sub(_DIGIT_STAND_IN, flat)
        for start in range(0, max(len(flat) - REPEAT_WINDOW_CHARS, 0), REPEAT_STRIDE_CHARS):
            if counted.count(counted[start:start + REPEAT_WINDOW_CHARS]) > MAX_REPEATS:
                return f"repeated passage: {flat[start:start + REPEAT_SAMPLE_CHARS]!r}"
        return None

    def _length_ratio(self, page: _PageText) -> str | None:
        layer, prose = _visible(page.layer), _visible(page.prose)
        if len(layer) < MIN_LAYER_CHARS_FOR_RATIO:
            return None
        ratio = len(prose) / len(layer)
        if MIN_LENGTH_RATIO <= ratio <= MAX_LENGTH_RATIO:
            return None
        return f"output length is {ratio:.2f} of the text layer, outside [{MIN_LENGTH_RATIO}, {MAX_LENGTH_RATIO}]"

    def _prose_only(self, output: str) -> str:
        without_markup = _TABLE_MARKUP_RE.sub(" ", without_notation(output))
        stripped = _EMPHASIS_RE.sub(" ", PageMarker.stripped(without_markup))
        return "".join(" " if unicodedata.category(char).startswith("S") else char for char in stripped)


def _is_wide_letter(char: str) -> bool:
    return unicodedata.category(char).startswith(_LETTER_CATEGORY) and unicodedata.east_asian_width(char) in _WIDE_WIDTHS


def _visible(text: str) -> str:
    return _WHITESPACE_RE.sub("", text)


@dataclass(frozen=True)
class _PageText:
    layer: str
    output: str
    prose: str
    source: str
