from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit

from references import HeldWorks

from _discover.cited import SAME_LIST_KEY
from _discover.matching import CitationMatch, Record, RecordMatch, is_truncated

OBTAIN_KINDS = ("publisher", "open copy", "internet archive")


@dataclass(frozen=True)
class Sighting:
    source: str
    seen_at: str
    query: str
    citations: int | None

    def as_dict(self) -> dict:
        return {"source": self.source, "seen_at": self.seen_at, "query": self.query, "citations": self.citations}


@dataclass
class Candidate:
    title: str
    authors: list[str]
    year: int | None
    container: str
    comment: str
    sightings: list[Sighting]
    obtain_links: list[dict] = field(default_factory=list)
    held_as: str | None = None
    cited_by: list[dict] = field(default_factory=list)

    @property
    def record(self) -> Record:
        urls = (*[link["url"] for link in self.obtain_links], *[s.seen_at for s in self.sightings])
        return Record.of(self.title, self.authors, self.year).identified_by(urls)

    @property
    def source_citations(self) -> int:
        return max((sighting.citations or 0 for sighting in self.sightings), default=0)

    @property
    def citing_count(self) -> int:
        return sum(1 for locator in self.cited_by if SAME_LIST_KEY not in locator)

    def absorb(self, other: "Candidate") -> None:
        if is_truncated(self.title) and not is_truncated(other.title):
            self.title = other.title
        self.sightings.extend(other.sightings)
        known = {link["url"] for link in self.obtain_links}
        self.obtain_links.extend(link for link in other.obtain_links if link["url"] not in known)
        if not self.authors:
            self.authors = list(other.authors)
        if self.year is None:
            self.year = other.year
        if not self.comment:
            self.comment = other.comment

    def mark_held_as(self, basename: str | None) -> None:
        self.held_as = basename

    def cite_from(self, locators: list[dict]) -> None:
        self.cited_by = locators

    def as_dict(self) -> dict:
        return {"title": self.title, "authors": self.authors, "year": self.year, "container": self.container,
                "comment": self.comment, "held_as": self.held_as, "cited_by": self.cited_by,
                "cited_by_count": self.citing_count, "source_citations": self.source_citations,
                "sightings": [sighting.as_dict() for sighting in self.sightings], "obtain_links": self.obtain_links}


class CandidateParser:
    def parse(self, reports: list[dict]) -> list[Candidate]:
        return [candidate for report in reports for candidate in self._of_report(report)]

    def unreachable(self, reports: list[dict]) -> list[dict]:
        return [{"source": report.get("source", ""), "unreachable": report["unreachable"]}
                for report in reports if report.get("unreachable")]

    def queries_run(self, reports: list[dict]) -> list[dict]:
        return [{"source": report.get("source", ""), "query": query}
                for report in reports for query in report.get("queries_run", [])]

    def _of_report(self, report: dict) -> list[Candidate]:
        source = report.get("source", "")
        return [self._candidate(source, raw) for raw in report.get("candidates", []) if raw.get("seen_at")]

    def _candidate(self, source: str, raw: dict) -> Candidate:
        sighting = Sighting(source, raw["seen_at"], raw.get("query", ""), self._count(raw.get("citations")))
        obtain = raw.get("obtain") or {}
        links = [obtain] if self._is_page(obtain.get("url")) and obtain.get("kind") in OBTAIN_KINDS else []
        return Candidate(raw.get("title", ""), list(raw.get("authors") or []), self._count(raw.get("year")),
                         raw.get("container", ""), raw.get("comment", ""), [sighting], links)

    @staticmethod
    def _is_page(url) -> bool:
        parts = urlsplit(url or "")
        return bool(parts.netloc) and parts.path.strip("/") != ""

    @staticmethod
    def _count(value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class CandidateMerge:
    def merged(self, candidates: list[Candidate]) -> list[Candidate]:
        merged: list[Candidate] = []
        for candidate in candidates:
            same = next((kept for kept in merged if RecordMatch(kept.record, candidate.record).holds()), None)
            if same is None:
                merged.append(candidate)
            else:
                same.absorb(candidate)
        return merged


class HeldMarking:
    def __init__(self, held: HeldWorks) -> None:
        self._records = [(work.basename, record) for work in held.works for record in Record.of_work(work)]

    def mark(self, candidates: list[Candidate]) -> None:
        for candidate in candidates:
            candidate.mark_held_as(self._held_as(candidate.record))

    def _held_as(self, record: Record) -> str | None:
        return next((basename for basename, held in self._records if RecordMatch(held, record).holds()), None)


@dataclass(frozen=True)
class UnheldEntry:
    raw: dict

    @property
    def years(self) -> frozenset[int]:
        return frozenset(int(year) for year in self.raw.get("years", []) if str(year).isdigit())

    @property
    def locators(self) -> list[dict]:
        return list(self.raw["cited_by"])

    def is_named_by(self, record: Record) -> bool:
        return CitationMatch(record, self.raw["text"], self.years).holds()


class LocalCitations:
    def __init__(self, unheld: dict) -> None:
        self._entries = [UnheldEntry(raw) for raw in unheld.get("entries", [])]

    def attach(self, candidates: list[Candidate]) -> None:
        for candidate in candidates:
            candidate.cite_from(self._locators(candidate.record))

    def _locators(self, record: Record) -> list[dict]:
        found: dict[str, dict] = {}
        for entry in self._entries:
            if entry.is_named_by(record):
                self._keep(entry.locators, found)
        return list(found.values())

    @staticmethod
    def _keep(locators: list[dict], found: dict[str, dict]) -> None:
        for locator in locators:
            known = found.setdefault(locator["basename"], locator)
            if SAME_LIST_KEY in known and SAME_LIST_KEY not in locator:
                found[locator["basename"]] = locator


class UnseenKnownItems:
    def __init__(self, known: dict) -> None:
        self._entries = [UnheldEntry(raw) for raw in known.get("entries", [])]

    def among(self, candidates: list[Candidate]) -> list[dict]:
        records = [candidate.record for candidate in candidates]
        return [entry.raw for entry in self._entries if not any(entry.is_named_by(record) for record in records)]


class Ordering:
    def ordered(self, candidates: list[Candidate]) -> list[Candidate]:
        return sorted(candidates, key=self._impact)

    @staticmethod
    def _impact(candidate: Candidate) -> tuple[int, int, int]:
        return (-candidate.citing_count, -candidate.source_citations, -(candidate.year or 0))


class MergeReport:
    def __init__(self, held: HeldWorks, unheld: dict, known: dict | None = None) -> None:
        self._parser = CandidateParser()
        self._merge = CandidateMerge()
        self._marking = HeldMarking(held)
        self._local = LocalCitations(unheld)
        self._known = UnseenKnownItems(known or {})
        self._ordering = Ordering()

    def over(self, reports: list[dict]) -> dict:
        candidates = self._merge.merged(self._parser.parse(reports))
        self._marking.mark(candidates)
        self._local.attach(candidates)
        ordered = self._ordering.ordered(candidates)
        return {"queries_run": self._parser.queries_run(reports),
                "unreachable": self._parser.unreachable(reports),
                "held": [candidate.as_dict() for candidate in ordered if candidate.held_as],
                "candidates": [candidate.as_dict() for candidate in ordered if not candidate.held_as],
                "known_unseen": self._known.among(candidates)}
