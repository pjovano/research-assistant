from __future__ import annotations

from _references.citing import (
    AUTOMATIC_THRESHOLD,
    CONFIRMATION_THRESHOLD,
    CitableWorks,
    CitationScoring,
    CitedReference,
    HeldSurnames,
    HeldTitleIndex,
    ReferenceScore,
    ScoredCitations,
    ScoredMatch,
)
from _references.entries import EntryParser, ReferenceEntry, RepeatedAuthors
from _references.graph import CitationEdge, CitationGraph, NoteEdgeCache, NoteEdges
from _references.matching import CitationMatch, EditionIdentity, Record, RecordMatch
from _references.notes import DEFINITION_RE, HEADING_RE, NoteLines
from _references.parsing import (
    CITATION_PARSER_MODEL_KEY,
    DEFAULT_CITATION_PARSER_MODEL,
    CitationParser,
    CitationParserUnavailable,
    LabelledSpan,
    PARSER_CACHE_FILENAME,
    ParsedReference,
    ParsedReferenceCache,
    ParserSettings,
    SpanFields,
)
from _references.reading import (
    SOURCE_CORPUS,
    SOURCE_PDF,
    CitedEntry,
    CorpusEntries,
    CorpusOnlyReader,
    Locator,
    MarkedLines,
    PdfEntries,
    ReferenceReader,
    ReferenceReading,
)
from _references.records import ReferenceExtractor, ReferenceRecord
from _references.similarity import HeldTitles, TitleTokens
from _references.unheld import (
    ANY_CITING_WORK, MIN_COMMON_ENTRIES, CommonLists, UnheldEntries, UnheldWork, UnheldWorks, WorkEntries,
    WorksBySurname,
)
from _references.works import HeldWorks, LibraryWork, WorkFactory, normalize_phrase, surname_token
from _references.zones import (
    ABSENT,
    BIBLIOGRAPHY,
    CachedZone,
    ReferenceZone,
    SectionHeading,
    ZONE_CACHE_NAME,
    ZoneCache,
    ZoneLocator,
)

__all__ = [
    "ABSENT", "ANY_CITING_WORK", "AUTOMATIC_THRESHOLD", "BIBLIOGRAPHY", "PARSER_CACHE_FILENAME", "ZONE_CACHE_NAME",
    "CITATION_PARSER_MODEL_KEY", "CONFIRMATION_THRESHOLD", "MIN_COMMON_ENTRIES",
    "DEFAULT_CITATION_PARSER_MODEL", "DEFINITION_RE", "HEADING_RE", "SOURCE_CORPUS", "SOURCE_PDF",
    "CachedZone", "CitableWorks",
    "CitationEdge", "CitationGraph", "CitationMatch", "CitationParser", "CitationScoring",
    "CitationParserUnavailable", "CitedEntry",
    "CitedReference", "CommonLists", "CorpusEntries", "CorpusOnlyReader", "EditionIdentity", "EntryParser", "HeldSurnames", "RepeatedAuthors", "HeldTitleIndex", "HeldTitles",
    "HeldWorks",
    "LabelledSpan", "LibraryWork",
    "Locator", "MarkedLines", "NoteEdgeCache", "NoteEdges", "NoteLines", "ParsedReference",
    "ParsedReferenceCache", "ParserSettings",
    "PdfEntries",
    "Record", "RecordMatch", "ReferenceEntry",
    "ReferenceExtractor", "ReferenceReader", "ReferenceReading", "ReferenceRecord", "ReferenceScore",
    "ReferenceZone",
    "ScoredCitations", "ScoredMatch", "SectionHeading", "SpanFields", "TitleTokens", "UnheldEntries", "UnheldWork",
    "UnheldWorks", "WorkEntries", "WorkFactory", "WorksBySurname",
    "ZoneCache",
    "ZoneLocator",
    "normalize_phrase",
    "surname_token",
]
