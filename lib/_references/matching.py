from __future__ import annotations

import re
from dataclasses import dataclass, replace
from difflib import SequenceMatcher

import identifiers
import vault
from _references.parsing import ParsedReference
from _references.works import LibraryWork, normalize_phrase, surname_token

TITLE_WEIGHT = 0.5
AUTHOR_WEIGHT = 0.3
YEAR_WEIGHT = 0.2
UNKNOWN_CREDIT = 0.5
ADJACENT_YEAR_CREDIT = 0.5
MATCH_THRESHOLD = 0.85
MIN_TITLE_RATIO = 0.8
IDENTICAL_TITLES = 1.0
MIN_TITLE_CHARS = 12
MIN_TRUNCATED_PREFIX_CHARS = 20

_URL_SCHEME_RE = re.compile(r"^https?://(www\.)?", re.IGNORECASE)
_TRUNCATION_MARKS = ("...", "…")


def surname_of(author: str) -> str:
    head, comma, _ = author.partition(",")
    return surname_token(head if comma else author)


def identifier_of(url: str) -> str | None:
    dois = identifiers.find_dois(url)
    if dois:
        return dois[0]
    if "?" in url:
        return None
    return _URL_SCHEME_RE.sub("", url.strip()).rstrip("/").lower()


def is_truncated(title: str) -> bool:
    return title.rstrip().endswith(_TRUNCATION_MARKS)


def main_title(title: str) -> str:
    main = normalize_phrase(vault.strip_subtitle(title))
    return main if len(main) >= MIN_TITLE_CHARS else normalize_phrase(title)


@dataclass(frozen=True)
class Record:
    title: str
    surnames: frozenset[str]
    years: frozenset[int]
    identifiers: frozenset[str] = frozenset()
    truncated: bool = False

    @classmethod
    def of(cls, title: str, authors: list[str], year: int | None) -> "Record":
        surnames = frozenset(name for name in (surname_of(author) for author in authors) if name)
        years = frozenset([year]) if year else frozenset()
        return cls(main_title(title), surnames, years, frozenset(), is_truncated(title))

    def identified_by(self, urls: tuple[str, ...]) -> "Record":
        found = frozenset(found for found in (identifier_of(url) for url in urls if url) if found)
        return replace(self, identifiers=found)

    @classmethod
    def of_work(cls, work: LibraryWork) -> list["Record"]:
        years = frozenset(int(year) for year in work.years if year.isdigit())
        return [cls(title, work.surname_tokens, years) for title in work.titles]


class RecordMatch:
    def __init__(self, left: Record, right: Record) -> None:
        self._left = left
        self._right = right

    def holds(self) -> bool:
        if self._left.identifiers & self._right.identifiers or self._one_truncates_the_other():
            return True
        if self._score_of(IDENTICAL_TITLES) < MATCH_THRESHOLD:
            return False
        ratio = self.title_ratio()
        return ratio >= MIN_TITLE_RATIO and self._score_of(ratio) >= MATCH_THRESHOLD

    def score(self) -> float:
        return self._score_of(self.title_ratio())

    def _score_of(self, title_ratio: float) -> float:
        return (TITLE_WEIGHT * title_ratio
                + AUTHOR_WEIGHT * self._author_credit()
                + YEAR_WEIGHT * self._year_credit())

    def title_ratio(self) -> float:
        if not self._left.title or not self._right.title:
            return 0.0
        return SequenceMatcher(None, self._left.title, self._right.title).ratio()

    def _one_truncates_the_other(self) -> bool:
        shorter, longer = sorted((self._left, self._right), key=lambda record: len(record.title))
        return (shorter.truncated and len(shorter.title) >= MIN_TRUNCATED_PREFIX_CHARS
                and longer.title.startswith(shorter.title))

    def _author_credit(self) -> float:
        if not self._left.surnames or not self._right.surnames:
            return UNKNOWN_CREDIT
        return 1.0 if self._left.surnames & self._right.surnames else 0.0

    def _year_credit(self) -> float:
        if not self._left.years or not self._right.years:
            return UNKNOWN_CREDIT
        if self._left.years & self._right.years:
            return 1.0
        gap = min(abs(a - b) for a in self._left.years for b in self._right.years)
        return ADJACENT_YEAR_CREDIT if gap == 1 else 0.0


class CitationMatch:
    def __init__(self, record: Record, entry_text: str, entry_years: frozenset[int]) -> None:
        self._record = record
        self._text = f" {normalize_phrase(entry_text)} "
        self._years = entry_years

    def holds(self) -> bool:
        return self._title_named() and self._author_named() and self._year_agrees()

    def _title_named(self) -> bool:
        title = self._record.title
        return len(title) >= MIN_TITLE_CHARS and f" {title} " in self._text

    def _author_named(self) -> bool:
        return any(f" {surname} " in self._text for surname in self._record.surnames)

    def _year_agrees(self) -> bool:
        if not self._years or not self._record.years:
            return True
        return bool(self._years & self._record.years)


@dataclass(frozen=True)
class EditionIdentity:
    record: Record

    @classmethod
    def of(cls, parsed: ParsedReference) -> "EditionIdentity":
        first_author = list(parsed.authors[:1])
        return cls(Record.of(parsed.title or "", first_author, None))

    @property
    def is_distinctive(self) -> bool:
        return bool(self.record.surnames) and len(self.record.title) >= MIN_TITLE_CHARS

    def names_same_work_as(self, other: "EditionIdentity") -> bool:
        comparable = self.is_distinctive and other.is_distinctive
        return comparable and RecordMatch(self.record, other.record).holds()
