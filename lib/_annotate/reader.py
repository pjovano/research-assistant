from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pymupdf

from .editing import HighlightStamp, IncrementalEdit
from .markers import PageGrids
from .notes import NoteLedger, Tag
from .overlap import CoveredWords
from .pairs import HighlightPairs

MISSING = "missing"
DELETED = "deleted"
MODIFIED = "modified"
PLANNED_DELETE = "delete"
PLANNED_MODIFY = "modify"
NO_ANNOTATION = "no annotation at this reference"


@dataclass(frozen=True)
class AnnotationRecord:
    page: int
    index: int
    kind: str
    author: str
    note: str
    covered: str
    colour: tuple | None
    tag: str = ""
    end_page: int | None = None
    end_index: int | None = None

    @property
    def reference(self) -> str:
        return f"{self.page}:{self.index}"

    @property
    def references(self) -> list[str]:
        if self.end_page is None:
            return [self.reference]
        return [self.reference, f"{self.end_page}:{self.end_index}"]

    def partner_of(self, reference: str) -> str | None:
        if reference not in self.references:
            return None
        others = [r for r in self.references if r != reference]
        return others[0] if others else None

    def joined(self, later: "AnnotationRecord") -> "AnnotationRecord":
        return replace(self, end_page=later.page, end_index=later.index,
                       covered=f"{self.covered} {later.covered}")

    def rendered(self) -> str:
        head = f"{self._location} [{self.kind}] author={self.author or '-'}"
        return f"{head}\n    covers: {self.covered}\n    note:   {self.note or '-'}"

    @property
    def _location(self) -> str:
        if self.end_page is None:
            return f"p{self.page} #{self.index}"
        return f"p{self.page}–{self.end_page} #{self.index}/#{self.end_index}"


class PairedRecords:
    def __init__(self, records: list[AnnotationRecord], pairs: HighlightPairs) -> None:
        self._records = records
        self._pairs = pairs

    def merged(self) -> list[AnnotationRecord]:
        by_reference = {record.reference: record for record in self._records}
        merged, consumed = [], set()
        for record in self._records:
            if record.reference in consumed:
                continue
            merged.append(self._with_partner(record, by_reference, consumed))
        return merged

    def _with_partner(self, record: AnnotationRecord, by_reference: dict,
                      consumed: set) -> AnnotationRecord:
        partner = self._pairs.partner_of(record.reference)
        if partner is None:
            return record
        consumed.add(partner)
        return record.joined(by_reference[partner])


class AnnotationInventory:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def records(self, tag: str = "") -> list[AnnotationRecord]:
        with pymupdf.open(self._pdf_path) as document:
            grids = PageGrids(document)
            records = self._all_records(document, grids)
            found = PairedRecords(records, HighlightPairs(document, grids)).merged()
        return [r for r in found if self._wanted(r, tag)]

    def _wanted(self, record: AnnotationRecord, tag: str) -> bool:
        if not tag:
            return True
        if Tag(record.tag).matches(tag):
            return True
        return any(found.matches(tag) for found in Tag.found_in(record.note))

    def rendered(self, tag: str = "") -> str:
        records = self.records(tag)
        if not records:
            return "no annotations"
        return "\n".join(r.rendered() for r in records) + f"\n\n{len(records)} annotation(s)"

    def _all_records(self, document, grids: PageGrids) -> list[AnnotationRecord]:
        records = []
        for number in range(document.page_count):
            records.extend(self._page_records(document[number], number + 1, grids))
        return records

    def _page_records(self, page, page_number: int, grids: PageGrids) -> list[AnnotationRecord]:
        annotations = list(page.annots() or [])
        if not annotations:
            return []
        return _PageAnnotations(page_number, CoveredWords(grids.of(page_number))).records(annotations)


class _PageAnnotations:
    def __init__(self, page_number: int, covered: CoveredWords) -> None:
        self._page_number = page_number
        self._covered = covered

    def records(self, annotations: list) -> list[AnnotationRecord]:
        return [self._record(annotation, index) for index, annotation in enumerate(annotations)]

    def _record(self, annotation, index: int) -> AnnotationRecord:
        info = annotation.info
        return AnnotationRecord(self._page_number, index, annotation.type[1],
                                info.get("title", ""), info.get("content", ""),
                                self._covered.text_of(annotation), self._stroke(annotation),
                                info.get("subject", ""))

    @staticmethod
    def _stroke(annotation) -> tuple | None:
        colours = annotation.colors or {}
        stroke = colours.get("stroke")
        return tuple(stroke) if stroke else None


@dataclass(frozen=True)
class RevisionChange:
    page: int
    index: int
    colour: tuple | None = None
    note: str | None = None
    append: str | None = None
    delete: bool = False

    @property
    def reference(self) -> str:
        return f"{self.page}:{self.index}"

    def at(self, reference: str) -> "RevisionChange":
        page, index = reference.split(":")
        return replace(self, page=int(page), index=int(index))


@dataclass(frozen=True)
class RevisionOutcome:
    change: RevisionChange
    action: str
    detail: str = ""
    partner: RevisionChange | None = None

    def rendered(self) -> str:
        return f"{self._location} {self.action.upper()} {self.detail}".rstrip()

    @property
    def _location(self) -> str:
        location = f"p{self.change.page} #{self.change.index}"
        if self.partner is None:
            return location
        return f"{location} + p{self.partner.page} #{self.partner.index}"


class RevisionTargets:
    def __init__(self, changes: list[RevisionChange], pairs: HighlightPairs) -> None:
        self._changes = changes
        self._partners = {c.reference: self._partner(c, pairs) for c in changes}

    def partner_of(self, change: RevisionChange) -> RevisionChange | None:
        return self._partners[change.reference]

    def all(self) -> list[RevisionChange]:
        partners = [p for p in self._partners.values() if p is not None]
        return list(self._changes) + partners

    def _partner(self, change: RevisionChange, pairs: HighlightPairs) -> RevisionChange | None:
        reference = pairs.partner_of(change.reference)
        if reference is None or reference in {c.reference for c in self._changes}:
            return None
        return change.at(reference)


class AnnotationRevision:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path
        self._outcomes: list[RevisionOutcome] = []

    @property
    def outcomes(self) -> list[RevisionOutcome]:
        return list(self._outcomes)

    def plan(self, changes: list[RevisionChange]) -> list[RevisionOutcome]:
        records = AnnotationInventory(self._pdf_path).records()
        inventory = {reference: record for record in records for reference in record.references}
        return [self._planned(change, inventory) for change in changes]

    def apply(self, changes: list[RevisionChange]) -> None:
        self._outcomes = IncrementalEdit(self._pdf_path).applied(
            lambda document: self._apply_all(document, changes), self._changed)

    def _changed(self, outcomes: list[RevisionOutcome]) -> bool:
        return any(o.action in (DELETED, MODIFIED) for o in outcomes)

    def _planned(self, change: RevisionChange, inventory: dict) -> RevisionOutcome:
        record = inventory.get(change.reference)
        if record is None:
            return RevisionOutcome(change, MISSING, NO_ANNOTATION)
        partner = record.partner_of(change.reference)
        return RevisionOutcome(change, self._verb(change), record.covered,
                               change.at(partner) if partner else None)

    def _verb(self, change: RevisionChange) -> str:
        if change.delete:
            return PLANNED_DELETE
        return PLANNED_MODIFY

    def _apply_all(self, document, changes: list[RevisionChange]) -> list[RevisionOutcome]:
        targets = RevisionTargets(changes, HighlightPairs(document, PageGrids(document)))
        actions: dict[str, str] = {}
        for page_number, group in self._by_page(targets.all()).items():
            actions.update(self._apply_page(document[page_number - 1], group))
        return [self._outcome(change, targets.partner_of(change), actions) for change in changes]

    def _by_page(self, changes: list[RevisionChange]) -> dict:
        grouped: dict = {}
        for change in changes:
            grouped.setdefault(change.page, []).append(change)
        return grouped

    def _apply_page(self, page, group: list[RevisionChange]) -> dict[str, str]:
        annotations = list(page.annots() or [])
        ordered = sorted(group, key=lambda c: c.index, reverse=True)
        return {c.reference: self._apply_one(annotations, c) for c in ordered}

    def _apply_one(self, annotations: list, change: RevisionChange) -> str:
        if change.index >= len(annotations):
            return MISSING
        return self._mutate(annotations[change.index], change)

    def _mutate(self, annotation, change: RevisionChange) -> str:
        if change.delete:
            annotation.parent.delete_annot(annotation)
            return DELETED
        content = self._content_for(annotation, change)
        HighlightStamp(annotation).recoloured(change.colour).stamped(
            annotation.info.get("title", ""), content, annotation.info.get("subject", ""))
        return MODIFIED

    def _content_for(self, annotation, change: RevisionChange) -> str:
        if change.note is not None:
            return change.note
        if change.append is not None:
            return self._appended(annotation, change.append)
        return annotation.info.get("content", "")

    def _appended(self, annotation, addition: str) -> str:
        return NoteLedger.of(annotation).extended(addition)

    def _outcome(self, change: RevisionChange, partner: RevisionChange | None,
                 actions: dict[str, str]) -> RevisionOutcome:
        action = actions[change.reference]
        detail = NO_ANNOTATION if action == MISSING else ""
        return RevisionOutcome(change, action, detail, partner)
