from __future__ import annotations

import re
from collections import Counter

from page_marker import PageMarker

_NOTE_LABEL_RE = re.compile(r"\[\^[^\]\s]+\]:?")
_WORD_RE = re.compile(r"\w+")


class WordChanges:
    def __init__(self, stored: str, rebuilt: str) -> None:
        self._stored = stored
        self._rebuilt = rebuilt

    def count(self) -> int:
        stored, rebuilt = words_of(self._stored), words_of(self._rebuilt)
        return sum(((stored - rebuilt) + (rebuilt - stored)).values())


def words_of(body: str) -> Counter:
    return Counter(_WORD_RE.findall(_NOTE_LABEL_RE.sub(" ", PageMarker.stripped(body))))
