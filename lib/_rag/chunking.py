from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import vault
from notation import without_notation

from .blocks import Block, BodyParser, Section
from .documents import IndexedDocument
from .packing import PARAGRAPH_SEPARATOR, SENTENCE_SEPARATOR, Run, SentenceSplitter, TokenBudget, Unit, UnitPacker

CHUNKING_VERSION = 3
MAX_PARENT_TOKENS = 1024
MAX_CHILD_TOKENS = 256
ID_HASH_LENGTH = 16
ID_SEPARATOR = "::"
HASH_SEPARATOR = ":"
CONTEXT_LINE_JOIN = "\n"
HEADING_PATH_KEY = "heading_path"
FOLIO_FIRST_KEY = "folio_first"
FOLIO_LAST_KEY = "folio_last"
FILE_PAGE_FIRST_KEY = "file_page_first"
FILE_PAGE_LAST_KEY = "file_page_last"
TIME_FIRST_KEY = "time_first"
TIME_LAST_KEY = "time_last"
_LIST_JOIN = ", "
_LABEL_JOIN = ", "
_AUTHOR_JOIN = " and "
_SPACE_RUN_RE = re.compile(r"[ \t]+")


@dataclass(frozen=True)
class Parent:
    parent_id: str
    basename: str
    text: str
    metadata: dict


@dataclass(frozen=True)
class Child:
    chunk_id: str
    parent_id: str
    basename: str
    text: str
    context: str
    embedded_text: str
    metadata: dict


@dataclass(frozen=True)
class ChunkedDocument:
    parents: tuple[Parent, ...]
    children: tuple[Child, ...]

    @property
    def chunk_ids(self) -> list[str]:
        return [child.chunk_id for child in self.children]


def chunk_context(work_label: str, heading_path: str) -> str:
    return CONTEXT_LINE_JOIN.join(line for line in (work_label, heading_path) if line)


def embedded_text(context: str, text: str) -> str:
    prose = _SPACE_RUN_RE.sub(" ", without_notation(text)).strip()
    return f"{context}{CONTEXT_LINE_JOIN}{prose}" if context else prose


def chunk_id(basename: str, text: str, heading_path: str) -> str:
    digest = hashlib.sha256((text + heading_path).encode("utf-8")).hexdigest()
    return f"{basename}{ID_SEPARATOR}{digest[:ID_HASH_LENGTH]}"


class ParentChildChunker:
    def __init__(self, budget: TokenBudget | None = None, version: int = CHUNKING_VERSION) -> None:
        self._budget = budget or TokenBudget()
        self._version = version
        self._parents = UnitPacker(self._budget, MAX_PARENT_TOKENS)
        self._children = UnitPacker(self._budget, MAX_CHILD_TOKENS)
        self._sentences = SentenceSplitter()

    def chunked(self, document: IndexedDocument) -> ChunkedDocument:
        collector = _ChunkCollector(document)
        for section in BodyParser().sections(document.body):
            self._collect(section, collector)
        return collector.result()

    def document_hash(self, document: IndexedDocument) -> str:
        return f"{self.document_hash_prefix}{document.content_hash}"

    @property
    def document_hash_prefix(self) -> str:
        return f"{self._version}{HASH_SEPARATOR}"

    def _collect(self, section: Section, collector: "_ChunkCollector") -> None:
        for run in self._parents.runs(self._paragraph_units(section.blocks)):
            collector.add(section.heading_path, run, self._children.runs(self._child_units(run)))

    @staticmethod
    def _paragraph_units(blocks: tuple[Block, ...]) -> list[Unit]:
        return [Unit(block.text, PARAGRAPH_SEPARATOR, block.atomic, block.first_page, block.last_page)
                for block in blocks]

    def _child_units(self, run: Run) -> list[Unit]:
        units: list[Unit] = []
        for unit in run.units:
            units.extend(self._child_units_of(unit))
        return units

    def _child_units_of(self, unit: Unit) -> list[Unit]:
        if unit.atomic or self._children.fits(unit):
            return [unit]
        sentences = self._sentences.sentences(unit.text)
        separators = [unit.separator] + [SENTENCE_SEPARATOR] * (len(sentences) - 1)
        return [Unit(sentence, separator, True, unit.first_page, unit.last_page)
                for sentence, separator in zip(sentences, separators)]


class _ChunkCollector:
    def __init__(self, document: IndexedDocument) -> None:
        self._basename = document.basename
        labels = _WorkLabels(document.meta)
        self._work = labels.fields()
        self._label = labels.label(document.basename)
        self._parents: dict[str, Parent] = {}
        self._children: dict[str, Child] = {}

    def add(self, heading_path: str, parent_run: Run, child_runs: list[Run]) -> None:
        parent_id = chunk_id(self._basename, parent_run.text, heading_path)
        metadata = self._metadata(heading_path, parent_run, parent_id)
        self._parents.setdefault(parent_id, Parent(parent_id, self._basename, parent_run.text, metadata))
        for run in child_runs:
            self._add_child(heading_path, run, parent_id)

    def result(self) -> ChunkedDocument:
        return ChunkedDocument(tuple(self._parents.values()), tuple(self._children.values()))

    def _add_child(self, heading_path: str, run: Run, parent_id: str) -> None:
        context = chunk_context(self._label, heading_path)
        text = embedded_text(context, run.text)
        child_id = chunk_id(self._basename, text, heading_path)
        metadata = self._metadata(heading_path, run, parent_id)
        child = Child(child_id, parent_id, self._basename, run.text, context, text, metadata)
        self._children.setdefault(child_id, child)

    def _metadata(self, heading_path: str, run: Run, parent_id: str) -> dict:
        return {
            "basename": self._basename,
            HEADING_PATH_KEY: heading_path,
            FOLIO_FIRST_KEY: run.first_page.folio,
            FOLIO_LAST_KEY: run.last_page.folio,
            FILE_PAGE_FIRST_KEY: run.first_page.file_page,
            FILE_PAGE_LAST_KEY: run.last_page.file_page,
            TIME_FIRST_KEY: run.first_page.time,
            TIME_LAST_KEY: run.last_page.time,
            **self._work,
            "parent_id": parent_id,
        }


class _WorkLabels:
    def __init__(self, meta: dict) -> None:
        self._meta = meta

    def fields(self) -> dict:
        return {
            "title": self._string("title"),
            "author": self._joined("author"),
            "year": self._string("year"),
            "citekey": self._string("citekey"),
            "field": self._joined("field"),
        }

    def label(self, basename: str) -> str:
        parts = (self._authors(), self._string("year"), self._main_title())
        return _LABEL_JOIN.join(parts) if all(parts) else basename

    def _authors(self) -> str:
        return _AUTHOR_JOIN.join(self._listed(self._meta.get("author")))

    def _main_title(self) -> str:
        return vault.strip_subtitle(self._string("title"))

    def _string(self, key: str) -> str:
        value = self._meta.get(key)
        return "" if value is None else str(value)

    def _joined(self, key: str) -> str:
        return _LIST_JOIN.join(self._listed(self._meta.get(key)))

    @staticmethod
    def _listed(value) -> list[str]:
        if not value:
            return []
        return [str(value)] if isinstance(value, str) else [str(item) for item in value]
