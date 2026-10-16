from __future__ import annotations

import re
from collections import Counter

from .constants import FRONT_MATTER_WORDS, MAX_SCAN_PAGES, PER_PAGE_ENTRY_RATIO
from .outline import Entry, Outline, OutlineError

_PAGE_LABEL = re.compile(r"^(?:p|pp|pg|page)?\.?\s*\d{1,4}$", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"^(?:untitled|bookmark|no\s*name)\b", re.IGNORECASE)
_NUMBERING_CHARS = "0123456789. "


class Suspicions:
    def __init__(self, outline: Outline, page_count: int) -> None:
        self._entries = outline.entries()
        self._page_count = page_count

    def names(self) -> list[str]:
        return [name for name, test in self._checks() if self._entries and test()]

    def _checks(self) -> tuple:
        return (
            ("per_page_entries", self._per_page_entries),
            ("page_labelled_titles", self._page_labelled_titles),
            ("untitled", self._untitled),
            ("empty_titles", self._empty_titles),
            ("all_target_first_page", self._all_target_first_page),
            ("flat", self._flat),
            ("duplicate_titles", self._duplicate_titles),
            ("non_monotonic", self._non_monotonic),
            ("out_of_range", self._out_of_range),
            ("front_matter_only", self._front_matter_only),
        )

    def _per_page_entries(self) -> bool:
        return bool(self._page_count) and (
            len(self._entries) >= self._page_count * PER_PAGE_ENTRY_RATIO)

    def _page_labelled_titles(self) -> bool:
        return any(_PAGE_LABEL.match(entry.title.strip()) for entry in self._entries)

    def _untitled(self) -> bool:
        return any(_PLACEHOLDER.match(entry.title.strip()) for entry in self._entries)

    def _empty_titles(self) -> bool:
        return any(not entry.title.strip() for entry in self._entries)

    def _all_target_first_page(self) -> bool:
        return all(entry.page == 1 for entry in self._entries)

    def _flat(self) -> bool:
        return all(entry.level == 1 for entry in self._entries)

    def _duplicate_titles(self) -> bool:
        titles = [entry.title.strip().lower() for entry in self._entries]
        return len(set(titles)) < len(titles)

    def _non_monotonic(self) -> bool:
        pages = [entry.page for entry in self._entries]
        return any(later < earlier for earlier, later in zip(pages, pages[1:]))

    def _out_of_range(self) -> bool:
        return any(not 1 <= entry.page <= self._page_count for entry in self._entries)

    def _front_matter_only(self) -> bool:
        return all(self._is_front_matter(entry.title) for entry in self._entries)

    def _is_front_matter(self, title: str) -> bool:
        return title.strip().lower().lstrip(_NUMBERING_CHARS) in FRONT_MATTER_WORDS


class _UnambiguousPairs:
    def __init__(self, before: list[Entry], after: list[Entry], key) -> None:
        self._before = self._unique(before, key)
        self._after = self._unique(after, key)

    def matched(self) -> list[tuple]:
        return [(self._before[k], entry) for k, entry in self._after.items() if k in self._before]

    def _unique(self, entries: list[Entry], key) -> dict:
        counts = Counter(key(entry) for entry in entries)
        return {key(entry): entry for entry in entries if counts[key(entry)] == 1}


class OutlineDiff:
    def __init__(self, before: Outline, after: Outline) -> None:
        self._before = before.entries()
        self._after = after.entries()

    def as_dict(self) -> dict:
        return {
            "added": [entry.as_dict() for entry in self._added()],
            "removed": [entry.as_dict() for entry in self._removed()],
            "retargeted": self._retargeted(),
            "renamed": self._renamed(),
        }

    def _added(self) -> list[Entry]:
        return self._absent_from(self._after, self._before)

    def _removed(self) -> list[Entry]:
        return self._absent_from(self._before, self._after)

    def _absent_from(self, candidates: list[Entry], reference: list[Entry]) -> list[Entry]:
        titles = {entry.title for entry in reference}
        places = {entry.placement() for entry in reference}
        return [e for e in candidates if e.title not in titles and e.placement() not in places]

    def _retargeted(self) -> list[dict]:
        pairs = _UnambiguousPairs(self._before, self._after, lambda e: e.title)
        return [{"title": after.title, "from": before.page, "to": after.page}
                for before, after in pairs.matched() if before.page != after.page]

    def _renamed(self) -> list[dict]:
        pairs = _UnambiguousPairs(self._before, self._after, lambda e: e.placement())
        return [{"page": after.page, "from": before.title, "to": after.title}
                for before, after in pairs.matched() if before.title != after.title]


class ScanRange:
    def __init__(self, first: int, last: int, page_count: int) -> None:
        self._first = first
        self._last = last
        self._page_count = page_count

    def pages(self) -> list[int]:
        self._check_bounds()
        self._check_span()
        return list(range(self._first, self._last + 1))

    def _check_bounds(self) -> None:
        if self._last < self._first:
            raise OutlineError(f"--to {self._last} precedes --from {self._first}")
        if self._first < 1 or self._last > self._page_count:
            raise OutlineError(
                f"--from {self._first} --to {self._last} lies outside 1..{self._page_count}")

    def _check_span(self) -> None:
        span = self._last - self._first + 1
        if span > MAX_SCAN_PAGES:
            raise OutlineError(
                f"{span} pages requested; scan renders at most {MAX_SCAN_PAGES} per call. "
                "Walk the book in batches.")
