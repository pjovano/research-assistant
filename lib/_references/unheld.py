from __future__ import annotations

from dataclasses import dataclass

from _references.citing import ScoredCitations
from _references.matching import EditionIdentity
from _references.parsing import CitationParser
from _references.reading import SOURCE_CORPUS, SOURCE_PDF, CitedEntry, Locator, ReferenceReader
from _references.works import HeldWorks, WorkFactory

MIN_TOKEN_OVERLAP = 0.5
ANY_CITING_WORK = 1
MIN_COMMON_ENTRIES = 5
SAME_LIST_KEY = "same_list_as"

__all__ = ["ANY_CITING_WORK", "MIN_COMMON_ENTRIES", "SAME_LIST_KEY", "SOURCE_CORPUS", "SOURCE_PDF", "Citation", "CitedEntry",
           "CommonLists", "CountedWork", "Locator", "UnheldEntries", "UnheldWork", "UnheldWorks", "WorkEntries",
           "WorksBySurname"]


@dataclass(frozen=True)
class WorkEntries:
    basename: str
    source: str
    entries: list[CitedEntry]

    def as_dict(self) -> dict:
        return {"basename": self.basename, "source": self.source, "unheld_entries": len(self.entries)}


class UnheldEntries:
    def __init__(self, held: HeldWorks, parser: CitationParser, reader: ReferenceReader | None = None) -> None:
        self._held = held
        self._parser = parser
        self._reader = reader or ReferenceReader()

    def of(self, basename: str) -> WorkEntries:
        work = self._held.find(basename)
        if work is None:
            raise LookupError(f"'{basename}' is not a held work: no PDF of that basename is in the library")
        reading = self._reader.read(work)
        citations = ScoredCitations(work, self._held, self._parser)
        unheld = [entry for entry in reading.entries if citations.named_by(entry.text) is None]
        return WorkEntries(basename, reading.source, unheld)


class CommonLists:
    def __init__(self, works: list[WorkEntries]) -> None:
        self._wordings = {work.basename: {entry.text for entry in work.entries} for work in works}

    def shared_by(self, basename: str, other: str) -> bool:
        return len(self._wordings.get(basename, set()) & self._wordings.get(other, set())) >= MIN_COMMON_ENTRIES


@dataclass(frozen=True)
class Citation:
    locator: Locator
    same_list_as: str | None

    @property
    def is_independent(self) -> bool:
        return self.same_list_as is None

    def as_dict(self) -> dict:
        if self.is_independent:
            return self.locator.as_dict()
        return {**self.locator.as_dict(), SAME_LIST_KEY: self.same_list_as}


class UnheldWork:
    def __init__(self, first: CitedEntry, identity: EditionIdentity) -> None:
        self._first = first
        self._identity = identity
        self._tokens = WorkFactory.tokens_of(first.text)
        self._locators = [first.locator]
        self._years = [first.year] if first.year else []

    @property
    def surnames(self) -> frozenset[str]:
        return frozenset(self._first.surnames) | self._identity.record.surnames

    def same_as(self, entry: CitedEntry, identity: EditionIdentity) -> bool:
        return self._identity.names_same_work_as(identity) or self._cites_same_edition(entry)

    def add(self, entry: CitedEntry) -> None:
        self._add_year(entry.year)
        self._add_locator(entry.locator)

    def cited_by(self) -> list[Locator]:
        return list(self._locators)

    def citations(self, lists: CommonLists) -> list[Citation]:
        return [Citation(locator, self._earlier_work_of_its_list(position, lists))
                for position, locator in enumerate(self._locators)]

    def described(self) -> dict:
        return {"text": self._first.text, "surnames": list(self._first.surnames), "years": list(self._years)}

    def _earlier_work_of_its_list(self, position: int, lists: CommonLists) -> str | None:
        basename = self._locators[position].basename
        earlier = (locator.basename for locator in self._locators[:position])
        return next((other for other in earlier if lists.shared_by(basename, other)), None)

    def _cites_same_edition(self, entry: CitedEntry) -> bool:
        return (self._first.year == entry.year and bool(set(self._first.surnames) & set(entry.surnames))
                and self._overlap(WorkFactory.tokens_of(entry.text)) >= MIN_TOKEN_OVERLAP)

    def _add_year(self, year: str | None) -> None:
        if year and year not in self._years:
            self._years.append(year)

    def _add_locator(self, locator: Locator) -> None:
        if locator.basename not in {known.basename for known in self._locators}:
            self._locators.append(locator)

    def _overlap(self, tokens: set[str]) -> float:
        union = self._tokens | tokens
        return len(self._tokens & tokens) / len(union) if union else 0.0


class WorksBySurname:
    def __init__(self) -> None:
        self._works: dict[int, UnheldWork] = {}
        self._keys_by_surname: dict[str, set[int]] = {}

    def __len__(self) -> int:
        return len(self._works)

    def add(self, key: int, work: UnheldWork) -> None:
        self._works[key] = work
        for surname in work.surnames:
            self._keys_by_surname.setdefault(surname, set()).add(key)

    def key_of(self, entry: CitedEntry, identity: EditionIdentity) -> int | None:
        return next((key for key in self._sharing_a_surname(entry, identity)
                     if self._works[key].same_as(entry, identity)), None)

    def work(self, key: int) -> UnheldWork:
        return self._works[key]

    def works(self) -> list[UnheldWork]:
        return list(self._works.values())

    def _sharing_a_surname(self, entry: CitedEntry, identity: EditionIdentity) -> list[int]:
        surnames = set(entry.surnames) | identity.record.surnames
        return sorted(set().union(*(self._keys_by_surname.get(surname, set()) for surname in surnames)))


class CountedWork:
    def __init__(self, work: UnheldWork, lists: CommonLists) -> None:
        self._work = work
        self._citations = work.citations(lists)

    @property
    def citing_count(self) -> int:
        return sum(1 for citation in self._citations if citation.is_independent)

    def as_dict(self) -> dict:
        return {**self._work.described(), "cited_by": [citation.as_dict() for citation in self._citations],
                "cited_by_count": self.citing_count}


class UnheldWorks:
    def __init__(self, held: HeldWorks, parser: CitationParser) -> None:
        self._unheld = UnheldEntries(held, parser)
        self._parser = parser

    def over(self, basenames: list[str], min_citing: int = ANY_CITING_WORK) -> dict:
        works = [self._unheld.of(basename) for basename in basenames]
        lists = CommonLists(works)
        counted = [CountedWork(work, lists) for work in self._merged(works)]
        kept = [work for work in counted if work.citing_count >= min_citing]
        ordered = sorted(kept, key=lambda work: -work.citing_count)
        return {"works": [work.as_dict() for work in works], "entries": [work.as_dict() for work in ordered]}

    def _merged(self, works: list[WorkEntries]) -> list[UnheldWork]:
        merged = WorksBySurname()
        for entry in (entry for work in works for entry in work.entries):
            self._merge(entry, merged)
        return merged.works()

    def _merge(self, entry: CitedEntry, merged: WorksBySurname) -> None:
        identity = EditionIdentity.of(self._parser.parse(entry.text))
        key = merged.key_of(entry, identity)
        if key is None:
            merged.add(len(merged), UnheldWork(entry, identity))
        else:
            merged.work(key).add(entry)
