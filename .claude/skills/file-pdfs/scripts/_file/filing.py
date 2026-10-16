from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import identifiers
import vault
import zotero
from zotero import ConnectorResult
from _vault.scratch import INGEST_ENTRY

from _file.bib import RequiredFields
from _file.notes import CorpusNote, DraftCard, NoteFrontmatter
from _file.citekeys import CitekeyAllocator
from _file.preview import FilingPreview

ATTACH_SETTLE_SECONDS = 30
CITEKEY_SETTLE_SECONDS = 10

STATUS_FILED = "filed"
STATUS_FILED_UNVERIFIED = "filed-unverified"
STATUS_FILED_NO_ATTACHMENT = "filed-no-attachment"
STATUS_CONNECTION_LOST = "connection-lost"
STATUS_CONNECTOR_REFUSED = "connector-refused"
STATUS_ZOTERO_OFFLINE = "zotero-offline"
STATUS_ALREADY_FILED = "already-filed"
STATUS_DUPLICATE = "duplicate"
STATUS_DUPLICATE_IN_ZOTERO = "duplicate-in-zotero"
STATUS_NOTE_COLLISION = "filed-note-collision"
STATUS_NO_CREATOR = "no-creator"
STATUS_NOTE_CHANGED_ON_DISK = "note-changed-on-disk"


def no_creator_row(pdf_name: str, missing: vault.CreatorMissing) -> dict:
    return {"file": pdf_name, "status": STATUS_NO_CREATOR, "message": str(missing)}


def note_changed_row(pdf_name: str, changed: vault.NoteChangedOnDisk) -> dict:
    return {"file": pdf_name, "status": STATUS_NOTE_CHANGED_ON_DISK, "path": str(changed.path),
            "message": str(changed)}


def refuses_a_changed_note(rows: list[dict]) -> bool:
    return any(row.get("status") == STATUS_NOTE_CHANGED_ON_DISK for row in rows)


class NoteCollision(RuntimeError):
    pass


@dataclass(frozen=True)
class PlacedAttachment:
    path: Path
    link: str

    @property
    def pdf_name(self) -> str:
        return vault.nfc(self.path.name)


@dataclass(frozen=True)
class Placement:
    verified: PlacedAttachment | None = None
    other_name: str | None = None

    def elsewhere(self) -> dict:
        return {"placed_elsewhere": self.other_name} if self.other_name else {}


@dataclass(frozen=True)
class FilingOutcome:
    source_pdf: Path
    meta: dict
    citekey: str
    connector: ConnectorResult
    placement: Placement

    @property
    def placed(self) -> PlacedAttachment | None:
        return self.placement.verified

    @property
    def filed(self) -> bool:
        return self.connector.item_saved

    @property
    def is_verified(self) -> bool:
        return self.placed is not None

    @property
    def status(self) -> str:
        if self.is_verified:
            return STATUS_FILED
        if self.filed:
            return STATUS_FILED_UNVERIFIED if self.connector.attachment_saved else STATUS_FILED_NO_ATTACHMENT
        if self.connector.connection_lost:
            return STATUS_CONNECTION_LOST
        return STATUS_CONNECTOR_REFUSED if self.connector.online else STATUS_ZOTERO_OFFLINE


class ItemFiler:
    def file(self, meta: dict, pdf_path: Path) -> ConnectorResult:
        return zotero.save_item_with_attachment(self._payload(meta), pdf_path)

    def _payload(self, meta: dict) -> dict:
        return {
            "title": meta["title"],
            "authors": meta["authors"],
            "year": meta["year"],
            "orig_year": meta.get("orig_year"),
            "type": meta["type"],
            "bib": meta.get("bib") or {},
        }


class ZoteroHolding:
    _ISBN_FIELD = "ISBN"

    def citekey_for(self, meta: dict, draft: DraftCard) -> str | None:
        doi = self._identified(draft, identifiers.KIND_DOI)
        return zotero.find_existing_citekey(zotero.HeldWorkQuery.of_meta(meta, doi, self._recorded_isbn(draft)))

    def _recorded_isbn(self, draft: DraftCard) -> str | None:
        return draft.zotero.get(self._ISBN_FIELD) or self._identified(draft, identifiers.KIND_ISBN)

    def _identified(self, draft: DraftCard, kind: str) -> str | None:
        identifier = (draft.identified or {}).get("identifier") or {}
        return identifier.get("value") if identifier.get("kind") == kind else None

    def duplicate_row(self, pdf_name: str, meta: dict, draft: DraftCard) -> dict | None:
        held_as = self.citekey_for(meta, draft)
        if held_as:
            return {"file": pdf_name, "status": STATUS_DUPLICATE_IN_ZOTERO, "held_as": held_as}
        return None


class AssignedCitekey:
    _POLL_SECONDS = 1

    def __init__(self, predicted: str, timeout: float = CITEKEY_SETTLE_SECONDS) -> None:
        self._predicted = predicted
        self._timeout = timeout

    def after(self, result: ConnectorResult, meta: dict) -> str:
        return self._of_item(result.item_key) or self._of_title(meta) or self._predicted

    def _of_item(self, item_key: str | None) -> str | None:
        return self._awaited_citation_key(item_key) if item_key else None

    def _awaited_citation_key(self, item_key: str) -> str | None:
        deadline = time.monotonic() + self._timeout
        while True:
            citekey = zotero.get_citation_key(item_key)
            if citekey or time.monotonic() >= deadline:
                return citekey
            time.sleep(self._POLL_SECONDS)

    def _of_title(self, meta: dict) -> str | None:
        return zotero.find_existing_citekey(zotero.HeldWorkQuery.of_meta(meta))


class AttachmentWatcher:
    _POLL_SECONDS = 2
    _ENTRY_LINK_KEY = "open"
    _ENTRY_PATH_KEY = "path"

    def __init__(self, expected_pdf_name: str, timeout: float = ATTACH_SETTLE_SECONDS) -> None:
        self._expected_pdf_name = vault.nfc(expected_pdf_name)
        self._timeout = timeout

    @classmethod
    def for_filing(cls, pdf_path: Path, meta: dict) -> "AttachmentWatcher":
        return cls(FilingPreview(pdf_path, meta).library_filename())

    def await_placement(self, citekey: str) -> Placement:
        deadline = time.monotonic() + self._timeout
        while True:
            placement = self._placement(citekey)
            if placement.verified or time.monotonic() >= deadline:
                return placement
            time.sleep(self._POLL_SECONDS)

    def _placement(self, citekey: str) -> Placement:
        held = [found for found in self._attachments(citekey) if self.in_library(found.path)]
        expected = next((found for found in held if found.pdf_name == self._expected_pdf_name), None)
        return Placement(expected, self._other_name(held))

    def _other_name(self, held: list[PlacedAttachment]) -> str | None:
        others = [found.pdf_name for found in held if found.pdf_name != self._expected_pdf_name]
        return others[0] if others else None

    def _attachments(self, citekey: str) -> list[PlacedAttachment]:
        found = (self._attachment(entry) for entry in zotero.get_attachments(citekey))
        return [attachment for attachment in found if attachment]

    def _attachment(self, entry: dict) -> PlacedAttachment | None:
        link = str(entry.get(self._ENTRY_LINK_KEY, ""))
        return PlacedAttachment(Path(str(entry.get(self._ENTRY_PATH_KEY, ""))), link) if link else None

    def in_library(self, candidate: Path) -> bool:
        if not self._on_the_convention(candidate.name):
            return False
        return candidate.exists() and candidate.resolve().parent == self._library_dir()

    def _on_the_convention(self, name: str) -> bool:
        return vault.nfc(name) == self._expected_pdf_name or vault.parse_library_filename(name) is not None

    def _library_dir(self) -> Path:
        return Path(vault.LIBRARY_DIR).resolve()


class FilingCompletion:
    def collides(self, outcome: FilingOutcome) -> bool:
        basename = CorpusNote(outcome.placed.pdf_name).path.stem
        owned = self._owned_note(outcome)
        owned_path = owned.path if owned else None
        return vault.held_note_exists(basename) and vault.held_note_path(basename) != owned_path

    def complete(self, outcome: FilingOutcome) -> None:
        if self.collides(outcome):
            raise NoteCollision(f"a corpus file already exists for {outcome.placed.pdf_name}")
        self._write_note(outcome)
        DraftCard(outcome.source_pdf.name).delete()
        self._discard_source(outcome)
        self._carry_scratch_entries(outcome)

    def _carry_scratch_entries(self, outcome: FilingOutcome) -> None:
        basename = vault.basename_of(outcome.placed.path)
        vault.ScratchEntries(vault.SCRATCH_DIR, outcome.source_pdf.stem).rename_to(basename)
        batch_entries = vault.SCRATCH_DIR / INGEST_ENTRY
        vault.ScratchEntries(batch_entries, vault.basename_of(outcome.source_pdf)).rename_to(basename)

    def _write_note(self, outcome: FilingOutcome) -> None:
        previous = self._owned_note(outcome)
        kept = previous.fields() if previous else {}
        body = previous.body() if previous else ""
        fields = NoteFrontmatter(outcome.meta, outcome.citekey).preserving(kept)
        note = self._placed_note(outcome, previous)
        note.write(fields, outcome.placed.link, body)
        if previous and previous.path != note.path:
            previous.delete()

    def _placed_note(self, outcome: FilingOutcome, previous: CorpusNote | None) -> CorpusNote:
        placed = CorpusNote(outcome.placed.pdf_name)
        return previous if previous and previous.path == placed.path else placed

    def _owned_note(self, outcome: FilingOutcome) -> CorpusNote | None:
        if outcome.source_pdf.parent.resolve() == Path(vault.INBOX_DIR).resolve():
            return None
        earlier = CorpusNote(outcome.source_pdf.name)
        return earlier if earlier.exists() else None

    def _discard_source(self, outcome: FilingOutcome) -> None:
        if not outcome.source_pdf.exists():
            return
        if outcome.source_pdf.resolve() == outcome.placed.path.resolve():
            return
        outcome.source_pdf.unlink(missing_ok=True)


class Settlement:
    def __init__(self, completion: FilingCompletion, draft: DraftCard, outcome: FilingOutcome) -> None:
        self._completion = completion
        self._draft = draft
        self._outcome = outcome
        self._collides = outcome.is_verified and completion.collides(outcome)

    @property
    def completes(self) -> bool:
        return self._outcome.is_verified and not self._collides

    @property
    def status(self) -> str:
        return STATUS_NOTE_COLLISION if self._collides else self._outcome.status

    def settle(self) -> None:
        if self.completes:
            self._completion.complete(self._outcome)
        else:
            self._save_draft()

    def _save_draft(self) -> None:
        if self._outcome.filed:
            self._draft.mark_filed()
        self._draft.adopt(self._outcome.meta, self._outcome.citekey)
        self._draft.save()


class FilingAttempt:
    def __init__(self, draft: DraftCard, pdf_path: Path, meta: dict) -> None:
        self._draft = draft
        self._pdf_path = pdf_path
        self._meta = meta
        self._watcher = AttachmentWatcher.for_filing(pdf_path, meta)
        self._outcome: FilingOutcome | None = None

    def file(self) -> None:
        predicted = CitekeyAllocator().for_meta(self._meta, exclude_stem=self._pdf_path.stem)
        result = ItemFiler().file(self._meta, self._pdf_path)
        if result.item_saved:
            self._outcome = self._recorded(predicted, result)
        else:
            self._outcome = FilingOutcome(self._pdf_path, self._meta, predicted, result, Placement())

    def outcome(self) -> FilingOutcome:
        if self._outcome is None:
            raise RuntimeError(f"the filing of {self._pdf_path.name} has not been attempted")
        return self._outcome

    def _recorded(self, predicted: str, result: ConnectorResult) -> FilingOutcome:
        self._draft.mark_filed()
        self._draft.set_item_key(result.item_key)
        self._draft.adopt(self._meta, predicted)
        self._draft.save()
        citekey = AssignedCitekey(predicted).after(result, self._meta)
        self._draft.adopt(self._meta, citekey)
        self._draft.save()
        placement = self._placement(citekey) if result.attachment_saved else Placement()
        return FilingOutcome(self._pdf_path, self._meta, citekey, result, placement)

    def _placement(self, citekey: str) -> Placement:
        return self._watcher.await_placement(citekey)


class Filer:
    def __init__(self, completion: FilingCompletion) -> None:
        self._completion = completion

    def file(self, inbox_pdf: Path) -> dict:
        try:
            return self._filed_row(inbox_pdf)
        except vault.CreatorMissing as missing:
            return no_creator_row(inbox_pdf.name, missing)
        except vault.NoteChangedOnDisk as changed:
            return note_changed_row(inbox_pdf.name, changed)

    def _filed_row(self, inbox_pdf: Path) -> dict:
        if CorpusNote(inbox_pdf.name).exists():
            return {"file": inbox_pdf.name, "status": STATUS_ALREADY_FILED}
        draft = DraftCard(inbox_pdf.name).load()
        if draft.filed:
            return self._awaiting_placement_row(inbox_pdf)
        held_as = self._held_under_predicted_name(inbox_pdf)
        if held_as:
            return {"file": inbox_pdf.name, "status": STATUS_DUPLICATE, "held_as": held_as}
        return self._file_new(inbox_pdf, draft)

    def _awaiting_placement_row(self, inbox_pdf: Path) -> dict:
        return {"file": inbox_pdf.name, "status": STATUS_FILED_UNVERIFIED,
                "note": "the item exists; run `retry` to await placement"}

    def _held_under_predicted_name(self, inbox_pdf: Path) -> str | None:
        predicted = FilingPreview.of(inbox_pdf).library_filename()
        if (vault.LIBRARY_DIR / predicted).exists() or vault.held_note_exists(Path(predicted).stem):
            return predicted
        return None

    def _file_new(self, inbox_pdf: Path, draft: DraftCard) -> dict:
        meta = FilingPreview.merged(inbox_pdf, draft).meta
        duplicate = ZoteroHolding().duplicate_row(inbox_pdf.name, meta, draft)
        if duplicate:
            return duplicate
        attempt = FilingAttempt(draft, inbox_pdf, meta)
        attempt.file()
        settlement = Settlement(self._completion, draft, attempt.outcome())
        settlement.settle()
        return self._summary(attempt.outcome(), settlement.status)

    def _summary(self, outcome: FilingOutcome, status: str) -> dict:
        return {
            "file": outcome.placed.pdf_name if outcome.placed else outcome.source_pdf.name,
            "status": status,
            "citekey": outcome.citekey,
            "authors_complete": outcome.meta.get("authors_complete", False),
            "bib_missing": RequiredFields().missing_from_meta(outcome.meta),
            **outcome.placement.elsewhere(),
        }
