from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from page_marker import PageMarker

from .diarizing import MILLISECONDS_PER_SECOND
from .merging import Utterance

SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60
PARAGRAPH_JOIN = "\n\n"
BLOCK_SPLIT_RE = re.compile(r"\n\s*\n")
SPEAKER_LINE_RE = re.compile(r"^\*\*(?P<speaker>[^*\n]+):\*\*[ \t]*(?P<text>.*)$", re.DOTALL)
_ENCODING = "utf-8"


def timestamp(milliseconds: int) -> str:
    total_seconds = milliseconds // MILLISECONDS_PER_SECOND
    minutes, seconds = divmod(total_seconds, SECONDS_PER_MINUTE)
    hours, minutes = divmod(minutes, MINUTES_PER_HOUR)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


@dataclass(frozen=True)
class Paragraph:
    time: str | None
    text: str

    @property
    def words(self) -> int:
        return len(self.text.split())

    @property
    def speaker(self) -> str | None:
        match = SPEAKER_LINE_RE.match(self.text)
        return match.group("speaker") if match else None


class TranscriptText:
    @staticmethod
    def rendered(utterances: list[Utterance]) -> str:
        blocks = [f"{PageMarker(time=timestamp(utterance.start_ms)).comment()}\n**{utterance.speaker}:** "
                  f"{utterance.text}" for utterance in utterances]
        return PARAGRAPH_JOIN.join(blocks) + "\n"

    @staticmethod
    def paragraphs(text: str) -> list[Paragraph]:
        blocks = (block.strip() for block in BLOCK_SPLIT_RE.split(text))
        return [TranscriptText._paragraph(block) for block in blocks if block]

    @staticmethod
    def _paragraph(block: str) -> Paragraph:
        first_line, _newline, rest = block.partition("\n")
        marker = PageMarker.parsed(first_line)
        if marker is None or marker.time is None:
            return Paragraph(None, block)
        return Paragraph(marker.time, rest.strip())


class RawTranscript:
    def __init__(self, path: Path) -> None:
        self._path = path

    def write(self, utterances: list[Utterance]) -> None:
        self._path.write_text(TranscriptText.rendered(utterances), encoding=_ENCODING)

    def paragraphs(self) -> list[Paragraph]:
        return TranscriptText.paragraphs(self._path.read_text(encoding=_ENCODING))
