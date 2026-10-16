from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

import pymupdf

import vault
from _annotate.cli import ANNOTATION_AUTHOR_KEY
from _annotate.notes import ENTRY_SEPARATOR, LINK_SEPARATOR, OMISSION, TAG_IN_TEXT, Note, NoteLedger, Tag
from _annotate.palette import ZOTERO_COLOURS, Colour, TagPalette
from _annotate.quotation_span import CrossPageQuotationSpan, FoldedWords, QuotationSpan
from _annotate.reader import AnnotationInventory, AnnotationRecord, AnnotationRevision, RevisionChange
from _annotate.specs import AnnotationSpec
from _annotate.spans import WordGrid
from _annotate.writer import AnnotationPlan, AnnotationWriter

from .atomic_note import AtomicNote
from .claims import ACCEPTED_MARK, REVIEW_MARK
from .highlight_colours import HighlightChoices
from .linked_note import FIELD
from .note_lines import NoteFile

PROJECTS = "projects"
COVER_PROBE_CHARS = 40
COLOUR_TOLERANCE = 0.02
QUOTATION_RE = re.compile(r"^> \*\*(?P<relation>[^*]+)\*\* · “(?P<quotation>.+)”(?P<mark> #(?:review|accepted))?$")
SOURCE_RE = re.compile(r"^> \t\[\[(?P<source>[^\]|#]+)\]\], (?:\[[^\]]+\]\([^)]*[?&]page=(?P<page>\d+)\)|.+)$")
QUOTE_PREFIX = "> "
TAG_LINE_RE = re.compile(r"^(#\[\[[^\]]+\]\]\s*)+$")


@dataclass(frozen=True)
class WrittenReference:
    quotation: str
    source: str
    file_page: int | None
    comment: str
    accepted: bool = False
    relation: str = ""

    @classmethod
    def parsed(cls, block: str) -> "WrittenReference | None":
        lines = block.splitlines()
        quoted = QUOTATION_RE.match(lines[0]) if lines else None
        cited = SOURCE_RE.match(lines[1]) if len(lines) > 1 else None
        if quoted is None or cited is None:
            return None
        page = int(cited.group("page")) if cited.group("page") else None
        comment = "\n".join(line.removeprefix(QUOTE_PREFIX).strip() for line in lines[2:]).removesuffix(REVIEW_MARK).strip()
        return cls(quoted.group("quotation"), cited.group("source").strip(), page, comment,
                   quoted.group("mark") == ACCEPTED_MARK, quoted.group("relation").strip())

    def passages(self) -> list["WrittenReference"]:
        return [replace(self, quotation=passage.strip()) for passage in self.quotation.split(OMISSION.strip())
                if passage.strip()]


class NoteTopics:
    def __init__(self, note: AtomicNote) -> None:
        self._note = note

    def tags(self) -> list[str]:
        return list(dict.fromkeys([*self._note.links(PROJECTS), *self._note.links(FIELD)]))

    def fields(self) -> list[str]:
        return self._note.links(FIELD)


class BookColours:
    @staticmethod
    def name_of(colour: tuple | None) -> str | None:
        if colour is None:
            return None
        return next((name for name, code in ZOTERO_COLOURS
                     if all(abs(a - b) <= COLOUR_TOLERANCE for a, b in zip(Colour(name, code).rgb, colour))), None)


class TaggedEntries:
    def __init__(self, link: str, tags: list[str], inline: list[str] | None = None) -> None:
        self._link = link
        self._tags = [Tag(label) for label in tags] or [Tag("")]
        self._inline = tuple(Tag(label) for label in inline or [])

    def of(self, content: str) -> str:
        ledger = NoteLedger(content)
        return ENTRY_SEPARATOR.join(self._retagged(entry) if entry.startswith(f"[[{self._link}]]") else entry
                                    for entry in ledger.entries)

    def _retagged(self, entry: str) -> str:
        kept = "\n".join(line for line in entry.splitlines() if not TAG_LINE_RE.match(line.strip()))
        body = kept.removeprefix(f"[[{self._link}]]").strip().removeprefix(LINK_SEPARATOR.strip()).strip()
        return Note(self._link, TAG_IN_TEXT.sub(r"\1", body), self._tags[0], tuple(self._tags[1:]),
                    self._inline).rendered


class PageSpan:
    def __init__(self, pdf: Path, reference: WrittenReference) -> None:
        self._pdf = pdf
        self._reference = reference

    def entry(self) -> dict | None:
        with pymupdf.open(self._pdf) as document:
            page = self._reference.file_page
            return (self._on_one_page(document, page) or self._on_one_page(document, page + 1)
                    or self._over_the_page_break(document))

    def _on_one_page(self, document, page: int) -> dict | None:
        if page > document.page_count:
            return None
        span = QuotationSpan(WordGrid(document[page - 1]), self._reference.quotation).located()
        return {"page": page, "start": span[0], "end": span[1]} if span else None

    def _over_the_page_break(self, document) -> dict | None:
        page = self._reference.file_page
        if page >= document.page_count:
            return None
        grids = WordGrid(document[page - 1]), WordGrid(document[page])
        span = CrossPageQuotationSpan(*grids, self._reference.quotation).located()
        return {"page": page, "start": span[0], "end_page": page + 1, "end": span[1]} if span else None


class ReferenceSpans:
    def __init__(self, pdf: Path, reference: WrittenReference, colour: str) -> None:
        self._comment = reference.comment
        self.colour = colour
        self._located = [(passage.quotation, PageSpan(pdf, passage).entry()) for passage in reference.passages()]

    def covers(self, record: AnnotationRecord) -> bool:
        covered = FoldedWords.folded(record.covered)
        return any(entry and entry["page"] == record.page and FoldedWords.folded(quotation)[:COVER_PROBE_CHARS] in covered
                   for quotation, entry in self._located)

    def misses(self) -> list[str]:
        return [quotation for quotation, entry in self._located if entry is None]

    def entries(self) -> list[dict]:
        entries: list[dict] = []
        for entry in (entry for _, entry in self._located if entry):
            host = next((held for held in entries if self._on_one_page(held, entry)), None)
            if host is None:
                entries.append({**entry, "body": self._comment, "colour": self.colour})
            else:
                host.setdefault("further", []).append([entry["start"], entry["end"]])
        return entries

    @staticmethod
    def _on_one_page(held: dict, entry: dict) -> bool:
        return held["page"] == entry["page"] and "end_page" not in held and "end_page" not in entry


class BookHighlights:
    def __init__(self, source: str, references: list[WrittenReference], choices: HighlightChoices) -> None:
        self.source = source
        self._pdf = vault.LibraryPdf(source).path()
        self._spans = [ReferenceSpans(self._pdf, reference,
                                      choices.colour_of(source, reference.comment))
                       for reference in references]

    def colours(self) -> list[str]:
        return list(dict.fromkeys(spans.colour for spans in self._spans))

    def misses(self) -> list[str]:
        return [quotation for spans in self._spans for quotation in spans.misses()]

    def requests(self, stamp: dict) -> list:
        entries = [{**stamp, **entry} for spans in self._spans for entry in spans.entries()]
        return AnnotationSpec({"annotations": entries}).requests()

    def planned(self, stamp: dict) -> str:
        return AnnotationPlan(self._pdf).decisions(self.requests(stamp)).rendered()

    def write(self, stamp: dict) -> None:
        AnnotationWriter(self._pdf, vault.MACHINE.get(ANNOTATION_AUTHOR_KEY)).apply(self.requests(stamp))
        changes = self.retagging(stamp)
        if changes:
            AnnotationRevision(self._pdf).apply(changes)

    def retagging(self, stamp: dict) -> list[RevisionChange]:
        tagged = TaggedEntries(stamp["link"], stamp["tags"], stamp["inline_tags"])
        changes = [self._change(record, tagged, stamp["link"]) for record in AnnotationInventory(self._pdf).records()
                   if NoteLedger(record.note).mentions(stamp["link"])]
        return [change for change in changes if change.colour or change.note is not None]

    def _change(self, record: AnnotationRecord, tagged: TaggedEntries, link: str) -> RevisionChange:
        note = tagged.of(record.note)
        target = self._colour_covering(record)
        alone = all(entry.startswith(f"[[{link}]]") for entry in NoteLedger(record.note).entries)
        recoloured = target is not None and alone and BookColours.name_of(record.colour) != target
        return RevisionChange(record.page, record.index, TagPalette().named(target).rgb if recoloured else None,
                              note if note != record.note else None)

    def _colour_covering(self, record: AnnotationRecord) -> str | None:
        return next((spans.colour for spans in self._spans if spans.covers(record)), None)


class NoteHighlighting:
    def __init__(self, file: NoteFile, choices: HighlightChoices) -> None:
        self._file = file
        self._note = file.read()
        cited = [parsed for block in self._note.reference_blocks()
                 if (parsed := WrittenReference.parsed(block)) and parsed.file_page]
        self._unaccepted = sum(not reference.accepted for reference in cited)
        accepted = [reference for reference in cited if reference.accepted]
        self._require_cited(choices.named_works(), {reference.source for reference in accepted})
        self._books = self._books_of(accepted, choices)

    def plan(self) -> dict:
        return {"note": self._file.title, "tags": NoteTopics(self._note).tags(),
                "references_not_accepted": self._unaccepted,
                "pdfs": [self._listed(book, book.planned(self._stamp())) for book in self._books]}

    def apply(self) -> None:
        for book in self._books:
            book.write(self._stamp())

    def _listed(self, book: BookHighlights, outcome: str) -> dict:
        return {"pdf": book.source, "colours": book.colours(), "highlights": outcome.splitlines(),
                "retagged": len(book.retagging(self._stamp())), "quotations_not_located": book.misses()}

    def _stamp(self) -> dict:
        topics = NoteTopics(self._note)
        return {"link": self._file.title, "tags": topics.tags(), "inline_tags": topics.fields(), "rewrite": True}

    def _require_cited(self, named: tuple[str, ...], cited: set[str]) -> None:
        uncited = [source for source in named if source not in cited]
        if uncited:
            raise ValueError(f"{self._file.title!r} has no accepted reference to {uncited}: "
                             "--generic names works the note's accepted references cite")

    @staticmethod
    def _books_of(references: list[WrittenReference], choices: HighlightChoices) -> list[BookHighlights]:
        sources = list(dict.fromkeys(reference.source for reference in references))
        return [BookHighlights(source, [r for r in references if r.source == source], choices) for source in sources]


class PdfHighlights:
    def __init__(self, source: str, tag: str) -> None:
        self._records = AnnotationInventory(vault.LibraryPdf(source).path()).records(tag)
        self._source = source

    def as_json(self) -> dict:
        return {"pdf": self._source, "highlights": [self._listed(record) for record in self._records]}

    @staticmethod
    def _listed(record: AnnotationRecord) -> dict:
        return {"file_page": record.page, "end_file_page": record.end_page, "covers": record.covered,
                "annotation_note": record.note, "tags": [tag.label for tag in Tag.found_in(record.note)],
                "colour": BookColours.name_of(record.colour)}
