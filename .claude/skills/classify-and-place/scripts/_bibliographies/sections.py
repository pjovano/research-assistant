from __future__ import annotations

import re

import vault

_BLANK_RUN_RE = re.compile(r"\n{3,}")
_HEADING_GROUP = 1
_CONTENT_GROUP = 2

EMPTY_SECTION_MARKER = "*(none)*"


class Section:
    def __init__(self, heading: str) -> None:
        self._heading = heading
        self._pattern = vault.section_pattern(heading)

    def is_in(self, body: str) -> bool:
        return self._pattern.search(body) is not None

    def is_repeated_in(self, body: str) -> bool:
        return len(self._pattern.findall(body)) > 1

    def content_in(self, body: str) -> str:
        hit = self._pattern.search(body)
        return hit.group(_CONTENT_GROUP) if hit else ""

    def with_content(self, body: str, content: str) -> str:
        block = self._normalized(content)
        if self.is_in(body):
            return self._pattern.sub(lambda hit: f"{hit.group(_HEADING_GROUP)}{block}", body)
        appended = f"{body.rstrip()}\n\n## {self._heading}\n{block}"
        return appended.strip() + "\n"

    def lines_in(self, body: str) -> list[str]:
        lines = (line.strip() for line in self.content_in(body).splitlines())
        return [line for line in lines if line and line != EMPTY_SECTION_MARKER]

    @staticmethod
    def _normalized(content: str) -> str:
        return _BLANK_RUN_RE.sub("\n\n", content)
