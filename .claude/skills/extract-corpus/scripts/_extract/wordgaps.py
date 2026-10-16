from __future__ import annotations

import statistics
import unicodedata
from dataclasses import dataclass

WORD_GAP_SHARE = 0.14
JUSTIFIED_SPACE_FLOOR_SHARE = WORD_GAP_SHARE / 2
JUSTIFIED_SPACE_TOLERANCE_SHARE = 0.02
MIN_JUSTIFIED_SPACES = 3
MIN_SPACED_WORD_CHARS = 2
DASH_CATEGORY = "Pd"
OVERLAY_CATEGORY = "Mn"


@dataclass(frozen=True)
class Gap:
    width: float
    size: float
    position: int
    beside_a_dash: bool = False

    def exceeds(self, share: float) -> bool:
        return self.width > share * self.size


class WordGaps:
    def __init__(self, chars: list, gaps: list[Gap]) -> None:
        self._letter_gap = statistics.median(gap.width for gap in gaps) if gaps else 0.0
        widened = [gap for gap in gaps if self._is_widened(gap)]
        words = _SpacedWords(chars, {gap.position for gap in widened})
        self._spaces = [gap for gap in widened if not gap.beside_a_dash and words.flank(gap.position)]

    def opens_a_word(self, gap: Gap) -> bool:
        return gap.exceeds(WORD_GAP_SHARE) or self._is_justified_space(gap)

    def _is_justified_space(self, gap: Gap) -> bool:
        return gap in self._spaces and self._matching_spaces(gap) >= MIN_JUSTIFIED_SPACES

    def _matching_spaces(self, gap: Gap) -> int:
        tolerance = JUSTIFIED_SPACE_TOLERANCE_SHARE * gap.size
        return sum(1 for other in self._spaces if abs(other.width - gap.width) <= tolerance)

    def _is_widened(self, gap: Gap) -> bool:
        return gap.width - self._letter_gap > JUSTIFIED_SPACE_FLOOR_SHARE * gap.size


class _SpacedWords:
    def __init__(self, chars: list, gap_positions: set[int]) -> None:
        self._word_of: list[int | None] = []
        self._lengths: list[int] = []
        for position, char in enumerate(chars):
            self._place(char, position in gap_positions)

    def flank(self, position: int) -> bool:
        beside = (self._word_of[position - 1], self._word_of[position])
        return all(word is not None and self._lengths[word] >= MIN_SPACED_WORD_CHARS for word in beside)

    def _place(self, char, opens_after_a_gap: bool) -> None:
        if char.is_blank:
            self._word_of.append(None)
            return
        if opens_after_a_gap or not self._word_of or self._word_of[-1] is None:
            self._lengths.append(0)
        self._word_of.append(len(self._lengths) - 1)
        self._lengths[-1] += 0 if is_overlay(char) else 1


def is_dash(char) -> bool:
    return len(char.char) == 1 and unicodedata.category(char.char) == DASH_CATEGORY


def is_overlay(char) -> bool:
    return len(char.char) == 1 and unicodedata.category(char.char) == OVERLAY_CATEGORY
