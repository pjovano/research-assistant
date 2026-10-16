from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache, cached_property

from _references.parsing import CitationParser, ParsedReference
from _references.similarity import HeldTitles, TitleTokens
from _references.works import HeldWorks, LibraryWork, normalize_phrase

YEAR_AGREEMENT_POINTS = 10.0
YEAR_DISAGREEMENT_POINTS = -10.0
LOWEST_SCORE = 0.0
HIGHEST_SCORE = 100.0

AUTOMATIC_THRESHOLD = 90.0
CONFIRMATION_THRESHOLD = 70.0
TITLE_ONLY_SURNAME_CEILING = AUTOMATIC_THRESHOLD - 1.0

MIN_CONTAINER_WORDS = 2



class CitableWorks:
    def __init__(self, citing: LibraryWork, held: HeldWorks) -> None:
        self._citing = citing
        self._works = [work for work in held.works if self._citable(work)]

    @property
    def works(self) -> list[LibraryWork]:
        return list(self._works)

    def _citable(self, work: LibraryWork) -> bool:
        return work.basename != self._citing.basename and self._not_later(work)

    def _not_later(self, work: LibraryWork) -> bool:
        cited, citing = work.cited_year, self._citing.cited_year
        if cited is None or citing is None:
            return True
        return cited <= citing


class CitedReference:
    def __init__(self, parsed: ParsedReference, entry_text: str) -> None:
        self._parsed = parsed
        self._entry_text = entry_text

    @property
    def year(self) -> str | None:
        return self._parsed.year

    @cached_property
    def author_words(self) -> set[str]:
        authors = " ".join(self._parsed.authors) or self._entry_text
        return set(normalize_phrase(authors).split())

    @cached_property
    def title_words(self) -> set[str]:
        return set(normalize_phrase(self._parsed.title or "").split())

    def title_without_possessive(self, surnames: tuple[str, ...]) -> str:
        title = self._parsed.title or self._entry_text
        for surname in surnames:
            title = re.sub(rf"^\s*{re.escape(surname)}['’]?s\s+", "", title, count=1, flags=re.IGNORECASE)
        return title

    @cached_property
    def container(self) -> str | None:
        container = self._parsed.container or ""
        return container if len(TitleTokens(container).words) >= MIN_CONTAINER_WORDS else None



class HeldSurnames:
    def __init__(self, works: list[LibraryWork]) -> None:
        self._surnames = {token for work in works for token in work.surname_tokens}

    def named_in(self, entry_text: str) -> bool:
        lowered = entry_text.lower()
        return any(surname in lowered for surname in self._surnames)


class ReferenceScore:
    def __init__(self, cited: CitedReference, work: LibraryWork, titles: HeldTitles) -> None:
        self._cited = cited
        self._work = work
        self._titles = titles

    def value(self) -> float:
        named_in_authors = self._surname_in_authors()
        if not named_in_authors and not self._surname_in_title():
            return LOWEST_SCORE
        score = min(HIGHEST_SCORE, max(LOWEST_SCORE, self._raw()))
        return score if named_in_authors else min(score, TITLE_ONLY_SURNAME_CEILING)

    def _raw(self) -> float:
        return max(self._title_similarity(), self._container_similarity()) + self._year_points()

    def _surname_in_authors(self) -> bool:
        return bool(self._surnames() & self._cited.author_words)

    def _surname_in_title(self) -> bool:
        return bool(self._surnames() & self._cited.title_words)

    def _surnames(self) -> frozenset[str]:
        return self._work.surname_tokens

    def _title_similarity(self) -> float:
        return self._titles.best_for(self._cited.title_without_possessive(self._work.surnames))

    def _container_similarity(self) -> float:
        container = self._cited.container
        return self._titles.best_for(container) if container else LOWEST_SCORE

    def _year_points(self) -> float:
        if self._cited.year is None or not self._work.years:
            return LOWEST_SCORE
        return YEAR_AGREEMENT_POINTS if self._cited.year in self._work.years else YEAR_DISAGREEMENT_POINTS


@dataclass(frozen=True)
class ScoredMatch:
    work: LibraryWork
    score: float

    @property
    def is_automatic(self) -> bool:
        return self.score >= AUTOMATIC_THRESHOLD

    @property
    def needs_confirmation(self) -> bool:
        return CONFIRMATION_THRESHOLD <= self.score < AUTOMATIC_THRESHOLD


_held_titles = cache(HeldTitles)


class HeldTitleIndex:
    def __init__(self, held: HeldWorks) -> None:
        self._by_basename = {work.basename: _held_titles(work.titles) for work in held.works}

    def of(self, work: LibraryWork) -> HeldTitles:
        return self._by_basename[work.basename]


class ScoredCitations:
    def __init__(self, citing: LibraryWork, held: HeldWorks, parser: CitationParser) -> None:
        self._works = CitableWorks(citing, held).works
        self._parser = parser
        self._titles = HeldTitleIndex(held)
        self._surnames = HeldSurnames(self._works)

    def named_by(self, entry_text: str) -> LibraryWork | None:
        best = self.best_for(entry_text)
        return best.work if best is not None and best.is_automatic else None

    def best_for(self, entry_text: str) -> ScoredMatch | None:
        best = max(self.scored(entry_text), key=lambda match: match.score, default=None)
        return best if best is not None and best.score >= CONFIRMATION_THRESHOLD else None

    def scored(self, entry_text: str) -> list[ScoredMatch]:
        if not self._surnames.named_in(entry_text):
            return [ScoredMatch(work, LOWEST_SCORE) for work in self._works]
        cited = CitedReference(self._parser.parse(entry_text), entry_text)
        return [ScoredMatch(work, self._scored_against(cited, work)) for work in self._works]

    def _scored_against(self, cited: CitedReference, work: LibraryWork) -> float:
        return ReferenceScore(cited, work, self._titles.of(work)).value()


class CitationScoring:
    def __init__(self, held: HeldWorks, parser: CitationParser) -> None:
        self._held = held
        self._parser = parser

    @property
    def held(self) -> HeldWorks:
        return self._held

    def for_citing(self, citing: LibraryWork) -> ScoredCitations:
        return ScoredCitations(citing, self._held, self._parser)
