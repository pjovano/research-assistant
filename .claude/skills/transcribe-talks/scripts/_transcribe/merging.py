from __future__ import annotations

import re
from dataclasses import dataclass

from .diarizing import Turn
from .whispering import Segment

UNKNOWN_SPEAKER = "SPEAKER_UNKNOWN"
MAX_UTTERANCE_WORDS = 250
_SENTENCE_END_RE = re.compile(r"[.!?…:][\"”’)\]]*\s*$")
_TEXT_JOIN = " "


@dataclass(frozen=True)
class Utterance:
    start_ms: int
    speaker: str
    text: str


class SpeakerAssignment:
    def __init__(self, segments: list[Segment], turns: list[Turn]) -> None:
        self._segments = segments
        self._turns = turns

    def utterances(self) -> list[Utterance]:
        merged: list[Utterance] = []
        for segment in self._segments:
            self._add(merged, segment, self._speaker_of(segment))
        return merged

    @staticmethod
    def _add(merged: list[Utterance], segment: Segment, speaker: str) -> None:
        if merged and merged[-1].speaker == speaker and _has_room(merged[-1]):
            last = merged[-1]
            merged[-1] = Utterance(last.start_ms, speaker, f"{last.text}{_TEXT_JOIN}{segment.text}")
        else:
            merged.append(Utterance(segment.start_ms, speaker, segment.text))

    def _speaker_of(self, segment: Segment) -> str:
        if not self._turns:
            return UNKNOWN_SPEAKER
        overlapping = max(self._turns, key=lambda turn: _overlap(segment, turn))
        if _overlap(segment, overlapping) > 0:
            return overlapping.speaker
        return min(self._turns, key=lambda turn: _distance(segment, turn)).speaker


def _has_room(utterance: Utterance) -> bool:
    return len(utterance.text.split()) < MAX_UTTERANCE_WORDS or not ends_sentence(utterance.text)


def ends_sentence(text: str) -> bool:
    return _SENTENCE_END_RE.search(text) is not None


def _overlap(segment: Segment, turn: Turn) -> int:
    return min(segment.end_ms, turn.end_ms) - max(segment.start_ms, turn.start_ms)


def _distance(segment: Segment, turn: Turn) -> int:
    return max(turn.start_ms - segment.end_ms, segment.start_ms - turn.end_ms, 0)
