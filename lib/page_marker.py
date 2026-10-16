from __future__ import annotations

import re
from dataclasses import dataclass

_MARKER_RE = re.compile(
    r"%% p\. (?P<folio>\S+) \(file p\. (?P<file_page>\d+)\) %%|%% file p\. (?P<bare_file_page>\d+) %%"
    r"|%% (?P<time>\d{2}:\d{2}:\d{2}) %%")


@dataclass(frozen=True)
class PageMarker:
    file_page: int | None = None
    folio: str | None = None
    time: str | None = None

    def comment(self) -> str:
        if self.time:
            return f"%% {self.time} %%"
        if self.folio:
            return f"%% p. {self.folio} (file p. {self.file_page}) %%"
        return f"%% file p. {self.file_page} %%"

    @staticmethod
    def parsed(line: str) -> "PageMarker | None":
        match = _MARKER_RE.fullmatch(line.strip())
        return None if match is None else PageMarker._of(match)

    @staticmethod
    def stripped(text: str, replacement: str = " ") -> str:
        return _MARKER_RE.sub(replacement, text)

    @staticmethod
    def inline(text: str) -> list["PageMarker"]:
        return [PageMarker._of(match) for match in _MARKER_RE.finditer(text)]

    @staticmethod
    def located(text: str) -> list[tuple[int, int, "PageMarker"]]:
        return [(match.start(), match.end(), PageMarker._of(match)) for match in _MARKER_RE.finditer(text)]

    @staticmethod
    def sliced(text: str) -> dict[int, str]:
        matches = list(_MARKER_RE.finditer(text))
        ends = [following.start() for following in matches[1:]] + [len(text)]
        slices: dict[int, str] = {}
        for match, end in zip(matches, ends):
            page = PageMarker._of(match).file_page
            if page is not None:
                slices[page] = (slices.get(page, "") + "\n" + text[match.end():end]).strip()
        return slices

    @staticmethod
    def _of(match: re.Match) -> "PageMarker":
        numbered = match.group("file_page") or match.group("bare_file_page")
        return PageMarker(int(numbered) if numbered else None, match.group("folio"), match.group("time"))
