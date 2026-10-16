from __future__ import annotations

import re
from dataclasses import dataclass

from _extract.headings import NO_KEY, HeadingText, is_a_bare_roman_numeral, past_enumerator, shape_of
from _extract.runningheads import CandidatePlace, HeadPrinting, OpenedHeadings, RepeatedTitles, RunningHeads

__all__ = ["CandidateBlock", "CandidatePlace", "HeadingCandidate", "HeadingStyles", "OpenedHeadings", "RunningHeads"]

FRAGMENT_OPENERS = frozenset({
    "and", "but", "or", "so", "thus", "hence", "then", "yet", "nor", "und", "aber", "oder", "also", "denn", "et",
    "mais", "ou", "donc",
})
_TRAILING_COLON_RE = re.compile(r":\s*$")


class HeadingStyles:
    def __init__(self) -> None:
        self._keys: set[tuple] = set()

    def learn(self, key: tuple | None) -> None:
        if key is not None and key != NO_KEY:
            self._keys.add(key)

    def is_listed(self, key: tuple | None) -> bool:
        return key is not None and key in self._keys


@dataclass(frozen=True)
class CandidateBlock:
    reading: HeadingText
    key: tuple | None
    place: CandidatePlace


class HeadingCandidate:
    def __init__(self, block: CandidateBlock, running_heads: RunningHeads) -> None:
        self._text = block.reading.text.strip()
        self._display_lettering = block.reading.is_display_lettering
        self._key = block.key
        self._running_heads = running_heads
        self._printing = HeadPrinting(self._text, (block.key or NO_KEY)[0], block.place)

    def is_heading(self, opened: OpenedHeadings, styles: HeadingStyles, work_title: str) -> bool:
        if styles.is_listed(self._key):
            return True
        return not (self.repeats_running_head(opened, work_title) or self._reads_as_fragment())

    def repeats_running_head(self, opened: OpenedHeadings, work_title: str) -> bool:
        return self._running_heads.is_running_head(self._printing, RepeatedTitles(opened, work_title))

    def introduces_what_follows(self) -> bool:
        return _TRAILING_COLON_RE.search(self._text) is not None

    def _reads_as_fragment(self) -> bool:
        if self.introduces_what_follows() or self._opens_mid_sentence():
            return True
        shape = shape_of(self._text)
        first_word = shape.split(" ")[0] if shape else ""
        return first_word in FRAGMENT_OPENERS

    def _opens_mid_sentence(self) -> bool:
        opens_lowercase = past_enumerator(self._text)[:1].islower()
        return opens_lowercase and not self._display_lettering and not is_a_bare_roman_numeral(self._text)
