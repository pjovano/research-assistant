from __future__ import annotations

import re

from _extract.notemarks import WRITTEN_MARK_RE

HYPHENATED_END_RE = re.compile(r"[^\W\d_]-$")
_SENTENCE_END_RE = re.compile(r"[.!?:;…”\"’')\]]\**$")
_SENTENCE_CLOSE_RE = re.compile(r"[.!?][”’\"')\]]*\s*$")
_TRAILING_WRITTEN_MARKS_RE = re.compile(rf"(?:{WRITTEN_MARK_RE.pattern})+$")


def closes_a_sentence(text: str) -> bool:
    return _SENTENCE_CLOSE_RE.search(text) is not None


def breaks_off_mid_sentence(text: str) -> bool:
    unmarked = _TRAILING_WRITTEN_MARKS_RE.sub("", text)
    return HYPHENATED_END_RE.search(unmarked) is not None or _SENTENCE_END_RE.search(unmarked) is None
