from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path

import vault
from _references.entries import YEAR_PATTERN

CITATION_PARSER_MODEL_KEY = "citation_parser_model"
DEFAULT_CITATION_PARSER_MODEL = "SIRIS-Lab/citation-parser-ENTITY"
PARSER_CACHE_FILENAME = "citation-parser-cache.sqlite"

_AUTHORS = "AUTHORS"
_TITLE = "TITLE"
_JOURNAL = "JOURNAL"
_YEAR = "PUBLICATION_YEAR"
_PUBLISHER = "PUBLISHER"
_PAGE_FIRST = "PAGE_FIRST"
_PAGE_LAST = "PAGE_LAST"

_YEAR_RE = re.compile(YEAR_PATTERN)
_TRAILING_YEAR_RE = re.compile(rf"[\s,(]*\b{YEAR_PATTERN}[a-z]?\)?\.?\s*$")
_NO_LETTERS_RE = re.compile(r"^[^\w]*$", re.UNICODE)
_NAME_EDGES = " ,;:"

MAX_FRAGMENT_GAP_CHARS = 1
PAGE_RANGE_DASH = "–"

_PIPELINE_TASK = "token-classification"
_SPAN_AGGREGATION = "simple"

_CACHE_SCHEMA = ("CREATE TABLE IF NOT EXISTS parsed (model TEXT NOT NULL, entry TEXT NOT NULL, "
                 "reference TEXT NOT NULL, PRIMARY KEY (model, entry))")
_CACHE_SELECT = "SELECT reference FROM parsed WHERE model = ? AND entry = ?"
_CACHE_INSERT = "INSERT OR REPLACE INTO parsed (model, entry, reference) VALUES (?, ?, ?)"


class CitationParserUnavailable(RuntimeError):
    pass


class ParserSettings:
    def __init__(self, values: dict | None = None) -> None:
        self._values = vault.MACHINE if values is None else values

    @property
    def model(self) -> str:
        return str(self._values.get(CITATION_PARSER_MODEL_KEY) or DEFAULT_CITATION_PARSER_MODEL)


@dataclass(frozen=True)
class LabelledSpan:
    label: str
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class ParsedReference:
    authors: tuple[str, ...]
    title: str | None
    container: str | None
    year: str | None
    publisher: str | None
    pages: str | None


class SpanFields:
    def __init__(self, spans: list[LabelledSpan]) -> None:
        self._spans = self._with_split_words_joined(sorted(spans, key=lambda span: span.start))

    @staticmethod
    def _with_split_words_joined(spans: list[LabelledSpan]) -> list[LabelledSpan]:
        joined: list[LabelledSpan] = []
        for span in spans:
            previous = joined[-1] if joined else None
            if previous and previous.end == span.start:
                joined[-1] = LabelledSpan(previous.label, previous.text + span.text, previous.start, span.end)
            else:
                joined.append(span)
        return joined

    def reference(self) -> ParsedReference:
        titles = self._texts(_TITLE)
        return ParsedReference(self._authors(), self._first(titles), self._container(titles), self._year(),
                               self._first(self._texts(_PUBLISHER)), self._pages())

    def _texts(self, label: str) -> list[str]:
        return [span.text.strip() for span in self._spans if span.label == label]

    @staticmethod
    def _first(texts: list[str]) -> str | None:
        return texts[0] if texts else None

    def _authors(self) -> tuple[str, ...]:
        cleaned = (self._author_name(text) for text in self._texts(_AUTHORS))
        return tuple(name for name in cleaned if name)

    @staticmethod
    def _author_name(text: str) -> str:
        without_year = _TRAILING_YEAR_RE.sub("", text).strip(_NAME_EDGES)
        return "" if _NO_LETTERS_RE.match(without_year) else without_year

    def _container(self, titles: list[str]) -> str | None:
        if len(titles) > 1:
            return titles[1]
        return self._first(self._texts(_JOURNAL))

    def _year(self) -> str | None:
        digit_years = [span for span in self._spans if span.label == _YEAR and self._has_digit(span)]
        joined = self._joined_fragments(digit_years)
        match = _YEAR_RE.search(joined)
        return match.group(1) if match else None

    @staticmethod
    def _has_digit(span: LabelledSpan) -> bool:
        return any(character.isdigit() for character in span.text)

    @staticmethod
    def _joined_fragments(fragments: list[LabelledSpan]) -> str:
        joined, previous_end = "", None
        for fragment in fragments:
            if previous_end is not None and fragment.start - previous_end > MAX_FRAGMENT_GAP_CHARS:
                break
            joined += fragment.text.strip()
            previous_end = fragment.end
        return joined

    def _pages(self) -> str | None:
        first, last = self._first(self._texts(_PAGE_FIRST)), self._first(self._texts(_PAGE_LAST))
        if first is None:
            return None
        return f"{first}{PAGE_RANGE_DASH}{last}" if last else first


class ParsedReferenceCache:
    def __init__(self, model: str) -> None:
        self._model = model
        self._connection: sqlite3.Connection | None = None

    def remembered(self, entry_text: str) -> ParsedReference | None:
        connection = self._existing()
        if connection is None:
            return None
        row = connection.execute(_CACHE_SELECT, (self._model, entry_text)).fetchone()
        return None if row is None else self._decoded(row[0])

    def remember(self, entry_text: str, reference: ParsedReference) -> None:
        connection = self._created()
        connection.execute(_CACHE_INSERT, (self._model, entry_text, self._encoded(reference)))
        connection.commit()

    def _existing(self) -> sqlite3.Connection | None:
        if self._connection is None and self._path().is_file():
            self._connection = self._opened()
        return self._connection

    def _created(self) -> sqlite3.Connection:
        if self._connection is None:
            self._path().parent.mkdir(parents=True, exist_ok=True)
            self._connection = self._opened()
        return self._connection

    def _opened(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path())
        connection.execute(_CACHE_SCHEMA)
        return connection

    @staticmethod
    def _path() -> Path:
        return vault.RAG_DIR / PARSER_CACHE_FILENAME

    @staticmethod
    def _encoded(reference: ParsedReference) -> str:
        return json.dumps(asdict(reference), ensure_ascii=False)

    @classmethod
    def _decoded(cls, stored: str) -> ParsedReference | None:
        try:
            return cls._reference_from(json.loads(stored))
        except (ValueError, TypeError, KeyError):
            return None

    @staticmethod
    def _reference_from(fields: dict) -> ParsedReference:
        return ParsedReference(tuple(fields.pop("authors")), **fields)


class CitationParser:
    _pipelines: dict[str, object] = {}

    def __init__(self, model: str | None = None) -> None:
        self._model = model or ParserSettings().model
        self._cache = ParsedReferenceCache(self._model)

    def parse(self, entry_text: str) -> ParsedReference:
        remembered = self._cache.remembered(entry_text)
        if remembered is not None:
            return remembered
        parsed = SpanFields(self._spans(entry_text)).reference()
        self._cache.remember(entry_text, parsed)
        return parsed

    def _spans(self, text: str) -> list[LabelledSpan]:
        return [LabelledSpan(item["entity_group"], text[item["start"]:item["end"]], item["start"], item["end"])
                for item in self._pipeline()(text)]

    def _pipeline(self):
        if self._model not in self._pipelines:
            self._pipelines[self._model] = self._loaded()
        return self._pipelines[self._model]

    def _loaded(self):
        try:
            return self._pipeline_built()
        except (ImportError, OSError, ValueError, RuntimeError) as cause:
            raise CitationParserUnavailable(f"citation parser {self._model} could not be loaded: {cause}") from cause

    def _pipeline_built(self):
        from transformers import pipeline
        return pipeline(_PIPELINE_TASK, model=self._model, aggregation_strategy=_SPAN_AGGREGATION)
