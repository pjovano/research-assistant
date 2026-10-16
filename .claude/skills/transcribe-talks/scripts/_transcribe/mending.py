from __future__ import annotations

import re

from page_marker import PageMarker

from .merging import ends_sentence
from .raw import BLOCK_SPLIT_RE, PARAGRAPH_JOIN, SPEAKER_LINE_RE

MAX_MOVED_WORDS = 80
_FIRST_SENTENCE_END_RE = re.compile(r"[.!?…][\"”’)\]]*(?=\s|$)")
_LINE_BREAK = "\n"


class SpokenBlock:
    def __init__(self, block: str) -> None:
        first_line, _newline, rest = block.partition(_LINE_BREAK)
        parsed = PageMarker.parsed(first_line)
        self.marker = first_line if parsed is not None and parsed.time else None
        speech = rest if self.marker else block
        match = SPEAKER_LINE_RE.match(speech.strip())
        self.speaker = match.group("speaker") if match else None
        self.text = match.group("text").strip() if match else speech

    @property
    def is_speech(self) -> bool:
        return self.speaker is not None

    def rendered(self) -> str:
        speech = f"**{self.speaker}:** {self.text}"
        return f"{self.marker}{_LINE_BREAK}{speech}" if self.marker else speech


class MarkerMend:
    def __init__(self, body: str) -> None:
        self._blocks = [block for block in BLOCK_SPLIT_RE.split(body.strip()) if block.strip()]

    def mended(self) -> str:
        blocks = list(self._blocks)
        index = 1
        while index < len(blocks):
            index = self._mend_at(blocks, index)
        return PARAGRAPH_JOIN.join(blocks)

    def _mend_at(self, blocks: list[str], index: int) -> int:
        before, after = SpokenBlock(blocks[index - 1]), SpokenBlock(blocks[index])
        if not self._cuts_a_sentence(before, after):
            return index + 1
        return self._moved_back(blocks, index)

    @staticmethod
    def _cuts_a_sentence(before: SpokenBlock, after: SpokenBlock) -> bool:
        one_speaker = before.is_speech and after.is_speech and before.speaker == after.speaker
        return one_speaker and after.marker is not None and not ends_sentence(before.text)

    @staticmethod
    def _moved_back(blocks: list[str], index: int) -> int:
        before, after = SpokenBlock(blocks[index - 1]), SpokenBlock(blocks[index])
        end = _FIRST_SENTENCE_END_RE.search(after.text)
        fragment = after.text[:end.end()] if end else after.text
        if len(fragment.split()) > MAX_MOVED_WORDS:
            return index + 1
        before.text = f"{before.text} {fragment}".strip()
        blocks[index - 1] = before.rendered()
        rest = after.text[len(fragment):].strip()
        if not rest:
            del blocks[index]
            return index
        after.text = rest
        blocks[index] = after.rendered()
        return index + 1
