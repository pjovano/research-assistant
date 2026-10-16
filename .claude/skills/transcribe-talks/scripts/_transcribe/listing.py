from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .raw import PARAGRAPH_JOIN, Paragraph, RawTranscript
from .talk import TalkEntry

MAX_PART_WORDS = 4000
LOOP_REPEATS = 3
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")
_SPEAKER_LABEL_RE = re.compile(r"\*\*[^*\n]+:\*\*")
_ENCODING = "utf-8"


class LoopedSentences:
    def __init__(self, text: str) -> None:
        unlabelled = _SPEAKER_LABEL_RE.sub(" ", text)
        self._sentences = [sentence.strip() for sentence in _SENTENCE_END_RE.split(unlabelled) if sentence.strip()]

    def heard_words(self) -> int:
        counts = Counter(sentence.casefold() for sentence in self._sentences)
        looped = {sentence: count for sentence, count in counts.items() if count >= LOOP_REPEATS}
        repeated_words = sum(len(sentence.split()) * (count - 1) for sentence, count in looped.items())
        return sum(len(sentence.split()) for sentence in self._sentences) - repeated_words


@dataclass(frozen=True)
class Part:
    number: int
    paragraphs: tuple[Paragraph, ...]

    @property
    def markers(self) -> list[str]:
        return [paragraph.time for paragraph in self.paragraphs if paragraph.time]

    @property
    def words(self) -> int:
        return sum(paragraph.words for paragraph in self.paragraphs)

    @property
    def heard_words(self) -> int:
        return LoopedSentences(PARAGRAPH_JOIN.join(paragraph.text for paragraph in self.paragraphs)).heard_words()

    @property
    def speakers(self) -> list[str]:
        return sorted({paragraph.speaker for paragraph in self.paragraphs if paragraph.speaker})

    def text(self) -> str:
        return PARAGRAPH_JOIN.join(self._rendered(paragraph) for paragraph in self.paragraphs)

    @staticmethod
    def _rendered(paragraph: Paragraph) -> str:
        return f"%% {paragraph.time} %%\n{paragraph.text}" if paragraph.time else paragraph.text


class TranscriptParts:
    def __init__(self, paragraphs: list[Paragraph], max_words: int = MAX_PART_WORDS) -> None:
        self._paragraphs = paragraphs
        self._max_words = max_words

    def parts(self) -> list[Part]:
        groups: list[list[Paragraph]] = [[]]
        for paragraph in self._paragraphs:
            if groups[-1] and self._words_in(groups[-1]) + paragraph.words > self._max_words:
                groups.append([])
            groups[-1].append(paragraph)
        return [Part(number, tuple(group)) for number, group in enumerate(groups, start=1) if group]

    @staticmethod
    def _words_in(group: list[Paragraph]) -> int:
        return sum(paragraph.words for paragraph in group)


class ReviewListing:
    def __init__(self, entry: TalkEntry) -> None:
        self._entry = entry

    def parts(self) -> list[Part]:
        return TranscriptParts(RawTranscript(self._entry.raw).paragraphs()).parts()

    def reviewed_paths(self) -> list[Path]:
        return [self._entry.part_path(part.number) for part in self.parts()]

    def write(self) -> Path:
        self._entry.reviewed_dir.mkdir(parents=True, exist_ok=True)
        self._entry.listing.write_text(json.dumps(self.as_dict(), ensure_ascii=False, indent=1), encoding=_ENCODING)
        return self._entry.listing

    def as_dict(self) -> dict:
        return {"video_id": self._entry.video_id, "recording": self._entry.recording().as_dict(),
                "card": str(self._entry.card), "parts": [self._part_entry(part) for part in self.parts()]}

    def _part_entry(self, part: Part) -> dict:
        return {"number": part.number, "words": part.words, "speakers": part.speakers, "markers": part.markers,
                "reviewed_path": str(self._entry.part_path(part.number)), "text": part.text()}
