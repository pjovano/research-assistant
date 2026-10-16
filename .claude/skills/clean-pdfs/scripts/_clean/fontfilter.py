from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .lines import dictionary_lines
from .outline import Entry, Outline, OutlineError, TitleText

BOLD_FLAG = 16
ITALIC_FLAG = 2
SIZE_PRECISION = 1
SAMPLE_CHARS = 60
FILTER_PARTS = 3
FILTER_SEPARATOR = ":"
TEXT_DICTIONARY = "dict"


class FilterError(OutlineError):
    pass


@dataclass(frozen=True)
class FontFace:
    name: str
    size: float
    bold: bool
    italic: bool

    @classmethod
    def of_span(cls, span: dict) -> "FontFace":
        flags = int(span["flags"])
        return cls(str(span["font"]), round(float(span["size"]), SIZE_PRECISION),
                   bool(flags & BOLD_FLAG), bool(flags & ITALIC_FLAG))

    def as_dict(self) -> dict:
        return {"font": self.name, "size": self.size, "bold": self.bold, "italic": self.italic}


@dataclass(frozen=True)
class FontFilter:
    font: str
    size: float
    level: int

    @classmethod
    def parsed(cls, spec: str) -> "FontFilter":
        parts = spec.rsplit(FILTER_SEPARATOR, FILTER_PARTS - 1)
        if len(parts) != FILTER_PARTS:
            raise FilterError(f"filter {spec!r} is not <font>:<size>:<level>")
        return cls(parts[0], cls._size(spec, parts[1]), cls._level(spec, parts[2]))

    @staticmethod
    def _size(spec: str, raw: str) -> float:
        try:
            return round(float(raw), SIZE_PRECISION)
        except ValueError:
            raise FilterError(f"filter {spec!r} has a non-numeric size {raw!r}") from None

    @staticmethod
    def _level(spec: str, raw: str) -> int:
        if not raw.isdigit() or int(raw) < 1:
            raise FilterError(f"filter {spec!r} has a level {raw!r}; levels start at 1")
        return int(raw)

    def matches(self, face: FontFace) -> bool:
        return face.name == self.font and face.size == self.size


class StyledLine:
    def __init__(self, spans: list[dict]) -> None:
        self._spans = [span for span in spans if span["text"].strip()]

    @property
    def text(self) -> str:
        return "".join(span["text"] for span in self._spans)

    @property
    def faces(self) -> list[FontFace]:
        return [FontFace.of_span(span) for span in self._spans]

    def matched_filter(self, filters: list[FontFilter]) -> FontFilter | None:
        if not self._spans:
            return None
        for candidate in filters:
            if all(candidate.matches(face) for face in self.faces):
                return candidate
        return None


class PageLines:
    def __init__(self, page: pymupdf.Page) -> None:
        self._page = page

    def lines(self) -> list[StyledLine]:
        return [StyledLine(line["spans"]) for line in dictionary_lines(self._page.get_text(TEXT_DICTIONARY))]

    def faces_with_samples(self) -> list[dict]:
        samples: dict[FontFace, str] = {}
        for line in self.lines():
            self._sample(samples, line)
        return [{**face.as_dict(), "sample": text[:SAMPLE_CHARS]} for face, text in samples.items()]

    def _sample(self, samples: dict[FontFace, str], line: StyledLine) -> None:
        for face in line.faces:
            samples[face] = samples.get(face, "") or line.text.strip()


class FontReport:
    def __init__(self, path: Path, page: int) -> None:
        self._path = path
        self._page = page

    def as_dict(self) -> dict:
        with pymupdf.open(self._path) as doc:
            self._require_page(doc.page_count)
            faces = PageLines(doc[self._page - 1]).faces_with_samples()
        return {"file": self._path.name, "page": self._page, "fonts": faces}

    def _require_page(self, page_count: int) -> None:
        if not 1 <= self._page <= page_count:
            raise FilterError(f"page {self._page} lies outside 1..{page_count}")


class _EntryRun:
    def __init__(self, page: int) -> None:
        self._page = page
        self._entries: list[Entry] = []
        self._open: FontFilter | None = None

    def add(self, line: StyledLine, matched: FontFilter | None) -> None:
        if matched is None:
            self._open = None
            return
        if matched is self._open:
            self._extend(line)
        else:
            self._entries.append(Entry(matched.level, line.text.strip(), self._page))
            self._open = matched

    def _extend(self, line: StyledLine) -> None:
        last = self._entries[-1]
        self._entries[-1] = Entry(last.level, f"{last.title} {line.text.strip()}", last.page)

    def entries(self) -> list[Entry]:
        normalized = [self._normalized(entry) for entry in self._entries]
        return [entry for entry in normalized if entry.title]

    def _normalized(self, entry: Entry) -> Entry:
        return Entry(entry.level, TitleText(entry.title).normalized(), entry.page)


class OutlineSuggestion:
    def __init__(self, path: Path, filters: list[FontFilter]) -> None:
        self._path = path
        self._filters = filters

    def outline(self) -> Outline:
        with pymupdf.open(self._path) as doc:
            entries = [entry for index in range(doc.page_count) for entry in self._page_entries(doc[index], index + 1)]
        return Outline(entries)

    def _page_entries(self, page: pymupdf.Page, page_number: int) -> list[Entry]:
        run = _EntryRun(page_number)
        for line in PageLines(page).lines():
            run.add(line, line.matched_filter(self._filters))
        return run.entries()
