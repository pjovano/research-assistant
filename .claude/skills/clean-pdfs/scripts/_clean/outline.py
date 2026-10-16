from __future__ import annotations

import re
from dataclasses import dataclass

from .constants import MAX_TITLE_CHARS

_CONTROLS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE = re.compile(r"\s+")
_DOT_LEADERS = re.compile(r"\s*[.·…_]{2,}\s*\d{0,4}$")
_TRAILING_FOLIO_AFTER_GAP = re.compile(r"\S\s{2,}\d{1,4}$")


class OutlineError(Exception):
    pass


class TitleText:
    def __init__(self, raw: str) -> None:
        self._raw = raw

    def normalized(self) -> str:
        cleaned = _CONTROLS.sub("", self._raw)
        return _WHITESPACE.sub(" ", self._without_folio(cleaned)).strip()

    def _without_folio(self, text: str) -> str:
        stripped = _DOT_LEADERS.sub("", text).strip()
        if stripped != text.strip():
            return stripped
        return _TRAILING_FOLIO_AFTER_GAP.sub(lambda m: m.group(0)[0], stripped)


@dataclass(frozen=True)
class Entry:
    level: int
    title: str
    page: int

    def as_dict(self) -> dict:
        return {"level": self.level, "title": self.title, "page": self.page}

    def as_toc_row(self) -> list:
        return [self.level, self.title, self.page]

    def identity(self) -> tuple[int, str, int]:
        return (self.level, self.title, self.page)

    def placement(self) -> tuple[int, int]:
        return (self.level, self.page)


class Outline:
    def __init__(self, entries: list[Entry]) -> None:
        self._entries = entries

    @classmethod
    def from_toc(cls, rows: list) -> "Outline":
        return cls([Entry(int(r[0]), str(r[1]), int(r[2])) for r in rows])

    def entries(self) -> list[Entry]:
        return list(self._entries)

    def is_empty(self) -> bool:
        return not self._entries

    def as_dicts(self) -> list[dict]:
        return [entry.as_dict() for entry in self._entries]

    def as_toc(self) -> list[list]:
        return [entry.as_toc_row() for entry in self._entries]

    def max_depth(self) -> int:
        return max((entry.level for entry in self._entries), default=0)

    def level_histogram(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self._entries:
            label = str(entry.level)
            counts[label] = counts.get(label, 0) + 1
        return counts


class EntryDraft:
    def __init__(self, index: int, raw: object) -> None:
        self._index = index
        self._raw = raw

    def entry(self, page_count: int) -> Entry:
        self._require_mapping()
        return Entry(self._level(), self._title(), self._page(page_count))

    def _require_mapping(self) -> None:
        if not isinstance(self._raw, dict):
            self._reject("is not an object carrying level, title and page")

    def _level(self) -> int:
        level = self._integer("level")
        if level < 1:
            self._reject(f"has level {level}; levels start at 1")
        return level

    def _page(self, page_count: int) -> int:
        page = self._integer("page")
        if not 1 <= page <= page_count:
            self._reject(f"targets page {page}, outside 1..{page_count}")
        return page

    def _integer(self, field: str) -> int:
        value = self._raw.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            self._reject(f"has a missing or non-integer {field}: {value!r}")
        return value

    def _title(self) -> str:
        raw = self._raw.get("title")
        if not isinstance(raw, str) or "\n" in raw:
            self._reject("has a missing, non-string, or multi-line title")
        return self._checked(TitleText(raw).normalized())

    def _checked(self, title: str) -> str:
        if not title:
            self._reject("has a blank title")
        if len(title) > MAX_TITLE_CHARS:
            self._reject(f"has a title of {len(title)} characters; the cap is {MAX_TITLE_CHARS}")
        return title

    def _reject(self, complaint: str) -> None:
        raise OutlineError(f"entry {self._index}: {complaint}")


class ProposedOutline:
    def __init__(self, raw_entries: object, page_count: int) -> None:
        self._raw = raw_entries
        self._page_count = page_count

    def build(self) -> Outline:
        outline = self.build_allowing_empty()
        if outline.is_empty():
            raise OutlineError("the entry list is empty; pass --force to write an empty outline")
        return outline

    def build_allowing_empty(self) -> Outline:
        entries = self._drafted()
        _EntrySequence(entries).validate()
        return Outline(entries)

    def _drafted(self) -> list[Entry]:
        if not isinstance(self._raw, list):
            raise OutlineError("the entries payload must be a JSON list of objects")
        return [EntryDraft(i, raw).entry(self._page_count) for i, raw in enumerate(self._raw)]


class _EntrySequence:
    def __init__(self, entries: list[Entry]) -> None:
        self._entries = entries

    def validate(self) -> None:
        self._check_levels()
        self._check_pages()
        self._check_uniqueness()

    def _check_levels(self) -> None:
        previous = 0
        for index, entry in enumerate(self._entries):
            self._check_level(index, entry.level, previous)
            previous = entry.level

    def _check_level(self, index: int, level: int, previous: int) -> None:
        if level <= previous + 1:
            return
        if not previous:
            raise OutlineError(f"entry {index}: the outline must start at level 1, not {level}")
        raise OutlineError(f"entry {index}: level {level} jumps past level {previous + 1}")

    def _check_pages(self) -> None:
        for index in range(1, len(self._entries)):
            earlier, later = self._entries[index - 1], self._entries[index]
            if later.page < earlier.page:
                raise OutlineError(
                    f"entry {index}: page {later.page} goes backwards from {earlier.page}")

    def _check_uniqueness(self) -> None:
        seen: set = set()
        for index, entry in enumerate(self._entries):
            if entry.identity() in seen:
                raise OutlineError(f"entry {index}: duplicates an earlier level/title/page")
            seen.add(entry.identity())
