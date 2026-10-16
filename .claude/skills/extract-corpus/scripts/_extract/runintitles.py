from __future__ import annotations

import re

from _extract.headings import shape_of

MAX_PAGINATION_CHARS = 24
_LEADING_EDITION_PAGINATION_RE = re.compile(rf"^\s*\\?\[[^\[\]\n]{{1,{MAX_PAGINATION_CHARS}}}?\\?\]\s*")


class RunInTitle:
    def __init__(self, title: str) -> None:
        self._shape = shape_of(title)
        self._word_count = len(title.split())

    def opens(self, text: str) -> bool:
        return self._opens_directly(_past_the_pagination(text))

    def past(self, text: str) -> str:
        unpaginated = _past_the_pagination(text)
        if not self._opens_directly(unpaginated):
            return text
        pagination = text[:len(text) - len(unpaginated)]
        words = unpaginated.split(maxsplit=self._word_count)
        rest = words[self._word_count] if len(words) > self._word_count else ""
        return f"{pagination}{rest}".strip()

    def _opens_directly(self, text: str) -> bool:
        opening = " ".join(text.split()[:self._word_count])
        return bool(self._shape) and shape_of(opening) == self._shape


def _past_the_pagination(text: str) -> str:
    return _LEADING_EDITION_PAGINATION_RE.sub("", text, count=1)
