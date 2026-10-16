from __future__ import annotations

import functools
import re

MIN_HYPHENATED_HEAD_LETTERS = 2
_JOINED_WORD_RE = re.compile(r"[^\W\d_]{2,}-[^\W\d_]{2,}")
_WORD_RE = re.compile(r"[^\W\d_]+")
_BROKEN_WORD_RE = re.compile(r"[^\W\d_]+-[ \t]*\n\s*[^\W\d_]+")
_LINE_END_RE = re.compile(r"[^\W\d_]+-$")
_LINE_START_RE = re.compile(r"^[^\W\d_]+")
_COMPOUND_LINE_START_RE = re.compile(r"^[^\W\d_]+-[^\W\d_]")
_URL_LINE_END_RE = re.compile(r"(?:://|www\.)\S*-$", re.IGNORECASE)


class Hyphens:
    def __init__(self, layer) -> None:
        self._layer = layer

    def keeps_hyphen(self, before: str, after: str) -> bool:
        breaks_a_url = _URL_LINE_END_RE.search(before) is not None
        is_compound = (_follows_too_few_letters_to_hyphenate(before) or self._opens_a_capitalised_word(before, after)
                       or self._joins_two_words_of_a_compound(before, after))
        return breaks_a_url or is_compound or self._joins_a_hyphenated_word(before, after)

    def _joins_a_hyphenated_word(self, before: str, after: str) -> bool:
        halves = _halves(before, after)
        return halves is not None and "-".join(halves) in self._words.hyphenated

    def _opens_a_capitalised_word(self, before: str, after: str) -> bool:
        halves = _halves(before, after)
        is_capitalised = halves is not None and before[-2].islower() and after[:1].isupper()
        return is_capitalised and "".join(halves) not in self._words.whole

    def _joins_two_words_of_a_compound(self, before: str, after: str) -> bool:
        halves = _halves(before, after)
        if halves is None or _COMPOUND_LINE_START_RE.match(after) is None:
            return False
        printed = self._words.whole
        return all(half in printed for half in halves) and "".join(halves) not in printed

    @functools.cached_property
    def _words(self) -> _WorkWords:
        return _WorkWords([self._layer.text(page) for page in range(1, self._layer.page_count() + 1)])


class _WorkWords:
    def __init__(self, page_texts: list[str]) -> None:
        self.hyphenated = {match.group(0).casefold() for text in page_texts for match in _JOINED_WORD_RE.finditer(text)}
        unbroken = [_BROKEN_WORD_RE.sub(" ", text) for text in page_texts]
        self.whole = {match.group(0).casefold() for text in unbroken for match in _WORD_RE.finditer(text)}


def _halves(before: str, after: str) -> tuple[str, str] | None:
    head = _LINE_END_RE.search(before)
    tail = _LINE_START_RE.match(after)
    if head is None or tail is None:
        return None
    return head.group(0).rstrip("-").casefold(), tail.group(0).casefold()


def _follows_too_few_letters_to_hyphenate(before: str) -> bool:
    head = _LINE_END_RE.search(before)
    return head is not None and len(head.group(0).rstrip("-")) < MIN_HYPHENATED_HEAD_LETTERS
