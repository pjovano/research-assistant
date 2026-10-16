from __future__ import annotations

import dataclasses
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

ROMAN_NUMERAL_PATTERN = r"(?=[ivxlcdm])m{0,3}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})"
FOLIO_WORD_PATTERN = rf"\d{{1,4}}|{ROMAN_NUMERAL_PATTERN}"
BARE_FOLIO_RE = re.compile(rf"^\s*[\[(]?\s*({FOLIO_WORD_PATTERN})\s*[\])]?\s*$", re.IGNORECASE)
_MARKED_DIGITS_RE = re.compile(r"^[^\w\s]*\s*(\d{1,4})\s*[^\w\s]*$")
_LEADING_FOLIO_RE = re.compile(r"^(\d{1,4})\s+\S")
_TRAILING_FOLIO_RE = re.compile(r"\S\s+(\d{1,4})$")
_LABEL_PREFIX_RE = re.compile(r"^p{1,2}(?:\.|\s|(?=\d))\s*", re.IGNORECASE)
_ROMAN_RE = re.compile(r"^[ivxlcdm]+$", re.IGNORECASE)
_ONES_AS_CAPITALS_RE = re.compile(r"^(?=[\d ]*I)[\dI](?:[\dI ]*[\dI])?$")

TEXT_WEIGHT = 3
LABEL_WEIGHT = 1
CONFIRMING_WEIGHT = 0
MAX_FOLIO_DIGITS = 4
MIN_PAGINATION_VOTES = 3
PRINTED_PAGES_PER_FILE_PAGE = (1, 2)
EDGE_SCAN_LINES = 3
FIRST_FILE_PAGE = 1


@dataclass(frozen=True)
class FolioCandidate:
    value: str
    weight: int

    @property
    def number(self) -> int | None:
        return int(self.value) if self.value.isdigit() else None

    @property
    def is_roman(self) -> bool:
        return self.number is None and bool(_ROMAN_RE.match(self.value))

    @property
    def elects(self) -> bool:
        return self.weight > CONFIRMING_WEIGHT


@dataclass(frozen=True)
class PageInput:
    text: str
    embedded_label: str | None
    edge_text: str = ""


@dataclass(frozen=True)
class FolioSignals:
    furniture: str | None
    edge: str | None
    label: str | None
    label_trusted: bool = True

    @property
    def printed(self) -> str | None:
        return self.furniture or self.edge

    @property
    def folio(self) -> str | None:
        if self.printed is not None:
            return self.printed
        return self.label if self.label_trusted else None

    @property
    def label_contradicted(self) -> bool:
        return _differ(self.printed, self.label)

    @property
    def label_corroborated(self) -> bool:
        return _agree(self.printed, self.label)

    def disagreements(self) -> list[str]:
        found = []
        if _differ(self.furniture, self.edge):
            found.append(f"the text layer's edge line reads {self.edge!r} where the running head reads "
                         f"{self.furniture!r}")
        if self.label_contradicted:
            found.append(f"the page label {self.label!r} disagrees with the printed folio {self.printed!r}")
        return found


def _differ(one: str | None, other: str | None) -> bool:
    return one is not None and other is not None and one.casefold() != other.casefold()


def _agree(one: str | None, other: str | None) -> bool:
    return one is not None and other is not None and one.casefold() == other.casefold()


class LabelNormalizer:
    def normalize(self, raw: str | None) -> str | None:
        if not raw:
            return None
        stripped = _LABEL_PREFIX_RE.sub("", raw.strip()).strip("[] ")
        return stripped or None


@dataclass(frozen=True)
class PageCandidates:
    furniture: list[FolioCandidate]
    edge: list[FolioCandidate]
    label: FolioCandidate | None

    @property
    def voting(self) -> list[FolioCandidate]:
        return self.printed + ([self.label] if self.label else [])

    @property
    def printed(self) -> list[FolioCandidate]:
        return self.furniture or self.edge

    @property
    def readings(self) -> list[list[FolioCandidate]]:
        return [self.furniture, self.edge]

    def held_by(self, pagination: Pagination, index: int) -> bool:
        return any(pagination.holds(candidate, index) for candidate in self.furniture + self.edge)


class CandidateReader:
    def of(self, page: PageInput) -> PageCandidates:
        label = LabelNormalizer().normalize(page.embedded_label)
        return PageCandidates(self._text_candidates(page.text), self._text_candidates(page.edge_text),
                              FolioCandidate(label, LABEL_WEIGHT) if label else None)

    def _text_candidates(self, text: str) -> list[FolioCandidate]:
        edges = self._edge_lines([line.strip() for line in (text or "").splitlines() if line.strip()])
        printed = [FolioCandidate(value, TEXT_WEIGHT) for value in self._from_text(edges)]
        return printed + [FolioCandidate(value, CONFIRMING_WEIGHT) for value in self._ones_read_as_capitals(edges)]

    def _from_text(self, edges: list[str]) -> list[str]:
        values = [self._bare(line) for line in edges] + [self._edge(line) for line in edges]
        return [value for value in values if value]

    @staticmethod
    def _ones_read_as_capitals(edges: list[str]) -> list[str]:
        readings = [line.replace(" ", "").replace("I", "1") for line in edges if _ONES_AS_CAPITALS_RE.match(line)]
        return [reading for reading in readings if len(reading) <= MAX_FOLIO_DIGITS]

    def _edge_lines(self, lines: list[str]) -> list[str]:
        return lines[:EDGE_SCAN_LINES] + lines[-EDGE_SCAN_LINES:]

    def _bare(self, line: str) -> str | None:
        match = BARE_FOLIO_RE.match(line) or _MARKED_DIGITS_RE.match(line)
        return match.group(1) if match else None

    def _edge(self, line: str) -> str | None:
        for pattern in (_LEADING_FOLIO_RE, _TRAILING_FOLIO_RE):
            match = pattern.search(line)
            if match:
                return match.group(1)
        return None


@dataclass(frozen=True)
class Pagination:
    first_folio: int
    printed_pages_per_file_page: int

    def holds(self, candidate: FolioCandidate, index: int) -> bool:
        first_on_page = self.first_folio + index * self.printed_pages_per_file_page
        return candidate.number in range(first_on_page, first_on_page + self.printed_pages_per_file_page)


def paginations_through(candidate: FolioCandidate, index: int, layouts: tuple[int, ...]) -> list[Pagination]:
    if candidate.number is None or not candidate.elects:
        return []
    return [Pagination(candidate.number - index * pages - position, pages)
            for pages in layouts for position in range(pages)]


class PaginationElection:
    def winners(self, per_page: list[PageCandidates]) -> list[Pagination]:
        first = self.winner([candidates.voting for candidates in per_page])
        if first is None:
            return []
        return [first, *StretchElection(per_page, first).following()]

    def winner(self, per_page: list[list[FolioCandidate]]) -> Pagination | None:
        votes: dict[Pagination, int] = defaultdict(int)
        for index, candidates in enumerate(per_page):
            for candidate in candidates:
                for pagination in paginations_through(candidate, index, PRINTED_PAGES_PER_FILE_PAGE):
                    votes[pagination] += candidate.weight
        return self._best(votes)

    def _best(self, votes: dict[Pagination, int]) -> Pagination | None:
        if not votes:
            return None
        pagination = max(votes, key=lambda p: (votes[p], -p.printed_pages_per_file_page))
        return pagination if votes[pagination] >= MIN_PAGINATION_VOTES * TEXT_WEIGHT else None


class StretchElection:
    def __init__(self, per_page: list[PageCandidates], first: Pagination) -> None:
        self._per_page = per_page
        self._elected = [first]
        self._layout = (first.printed_pages_per_file_page,)

    def following(self) -> list[Pagination]:
        while (winner := self._next()) is not None:
            self._elected.append(winner)
        return self._elected[1:]

    def _next(self) -> Pagination | None:
        stretches = {pagination: strongest_stretch(readings) for pagination, readings in self._readings_held().items()}
        best = max(stretches, key=stretches.get, default=None)
        return best if best is not None and stretches[best] >= MIN_PAGINATION_VOTES else None

    def _readings_held(self) -> dict[Pagination, Counter[int]]:
        held: dict[Pagination, Counter[int]] = defaultdict(Counter)
        for index, reading in self._unheld_readings():
            for pagination in self._paginations_through(reading, index):
                held[pagination][index] += 1
        return held

    def _paginations_through(self, reading: list[FolioCandidate], index: int) -> set[Pagination]:
        return {pagination for candidate in reading for pagination in paginations_through(candidate, index, self._layout)}

    def _unheld_readings(self) -> list[tuple[int, list[FolioCandidate]]]:
        return [(index, reading) for index, candidates in enumerate(self._per_page)
                if not self._held(candidates, index) for reading in candidates.readings]

    def _held(self, candidates: PageCandidates, index: int) -> bool:
        return any(candidates.held_by(pagination, index) for pagination in self._elected)


def strongest_stretch(readings_by_index: Counter[int]) -> int:
    return max(_readings_from(index, readings_by_index) for index in readings_by_index
               if index - 1 not in readings_by_index)


def _readings_from(first_index: int, readings_by_index: Counter[int]) -> int:
    total = 0
    index = first_index
    while index in readings_by_index:
        total += readings_by_index[index]
        index += 1
    return total


class FolioResolver:
    def resolve(self, pages: list[PageInput]) -> list[str | None]:
        return [signals.folio for signals in self.signals(pages)]

    def signals(self, pages: list[PageInput]) -> list[FolioSignals]:
        per_page = [CandidateReader().of(page) for page in pages]
        runs = ElectedRuns(per_page, PaginationElection().winners(per_page))
        read = [self._signals(candidates, index, runs.pagination_at(index))
                for index, candidates in enumerate(per_page)]
        trusted = LabelTrust(read).holds()
        return [dataclasses.replace(signals, label_trusted=trusted) for signals in read]

    def _signals(self, candidates: PageCandidates, index: int, pagination: Pagination | None) -> FolioSignals:
        label = candidates.label.value if candidates.label else None
        return FolioSignals(self._chosen(candidates.furniture, index, pagination),
                            self._chosen(candidates.edge, index, pagination), label)

    def _chosen(self, candidates: list[FolioCandidate], index: int, pagination: Pagination | None) -> str | None:
        if pagination is None:
            return self._roman(candidates)
        return self._in_pagination(candidates, index, pagination)

    @staticmethod
    def _in_pagination(candidates: list[FolioCandidate], index: int, pagination: Pagination) -> str | None:
        return next((candidate.value for candidate in candidates if pagination.holds(candidate, index)), None)

    def _roman(self, candidates: list[FolioCandidate]) -> str | None:
        romans = [candidate for candidate in candidates if candidate.is_roman]
        return romans[0].value if romans else None


class ElectedRuns:
    def __init__(self, per_page: list[PageCandidates], paginations: list[Pagination]) -> None:
        self._holders = [self._holder(candidates, index, paginations) for index, candidates in enumerate(per_page)]

    @staticmethod
    def _holder(candidates: PageCandidates, index: int, paginations: list[Pagination]) -> Pagination | None:
        return next((pagination for pagination in paginations if candidates.held_by(pagination, index)), None)

    def pagination_at(self, index: int) -> Pagination | None:
        return self._holders[index] or self._flanking(index)

    def _flanking(self, index: int) -> Pagination | None:
        before = next((holder for holder in reversed(self._holders[:index]) if holder), None)
        after = next((holder for holder in self._holders[index + 1:] if holder), None)
        return before if before == after else None


class LabelTrust:
    def __init__(self, signals: list[FolioSignals]) -> None:
        self._signals = signals

    def holds(self) -> bool:
        return not self._contradicted() and (self._corroborated() or not self._restates_file_pages())

    def _contradicted(self) -> bool:
        return any(signals.label_contradicted for signals in self._signals)

    def _corroborated(self) -> bool:
        return any(signals.label_corroborated for signals in self._signals)

    def _restates_file_pages(self) -> bool:
        return all(signals.label == str(file_page)
                   for file_page, signals in enumerate(self._signals, start=FIRST_FILE_PAGE))
