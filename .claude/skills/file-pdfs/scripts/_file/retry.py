from __future__ import annotations

from pathlib import Path

import vault
import zotero

from _file.notes import CorpusNote, DraftCard
from _file.filing import (
    STATUS_ALREADY_FILED,
    STATUS_NOTE_COLLISION,
    AttachmentWatcher,
    FilingAttempt,
    FilingCompletion,
    FilingOutcome,
    Placement,
    Settlement,
    ZoteroHolding,
    no_creator_row,
    note_changed_row,
    refuses_a_changed_note,
)
from _file.paths import NotePaths
from _file.preview import FilingPreview

STATUS_RETRIED_OK = "retried-ok"
STATUS_VERIFIED_ON_RETRY = "verified-on-retry"
STATUS_STILL_UNVERIFIED = "still-unverified"
STATUS_RETRIED_UNVERIFIED = "retried-unverified"
STATUS_RETRY_FAILED = "retry-failed"
STATUS_MISSING_FILE = "retry-skipped-missing-file"
STATUS_ZOTERO_STILL_OFFLINE = "zotero-still-offline"


class PendingDrafts:
    def drafts(self) -> list[DraftCard]:
        return [DraftCard.at(path).load() for path in NotePaths().drafts()]

    def unfiled(self) -> list[DraftCard]:
        return [draft for draft in self.drafts() if not draft.filed]

    def count(self) -> int:
        return len(self.drafts())


class RetryRunner:
    def __init__(self, completion: FilingCompletion) -> None:
        self._completion = completion

    def run(self) -> list[dict]:
        return self._run_over(PendingDrafts().drafts())

    def run_for(self, pdf_name: str) -> list[dict]:
        named = vault.nfc(pdf_name)
        return self._run_over([draft for draft in PendingDrafts().drafts() if vault.nfc(draft.pdf_name) == named])

    def resume_unfiled_other_than(self, pdf_name: str) -> list[dict]:
        return self._run_over([draft for draft in PendingDrafts().unfiled() if draft.pdf_name != pdf_name])

    def _run_over(self, drafts: list[DraftCard]) -> list[dict]:
        if not zotero.is_online():
            return [self._offline_row(draft) for draft in drafts]
        rows: list[dict] = []
        for draft in drafts:
            rows.append(self._guarded_resume(draft))
            if refuses_a_changed_note(rows):
                break
        return rows

    def _guarded_resume(self, draft: DraftCard) -> dict:
        try:
            return self._resume(draft)
        except vault.NoteChangedOnDisk as changed:
            return note_changed_row(draft.pdf_name, changed)

    def _offline_row(self, draft: DraftCard) -> dict:
        return {"file": draft.pdf_name, "status": STATUS_ZOTERO_STILL_OFFLINE,
                "citekey": draft.citekey}

    def _resume(self, draft: DraftCard) -> dict:
        source = self._source_pdf(draft)
        if source is None:
            return {"file": draft.pdf_name, "status": STATUS_MISSING_FILE}
        meta = FilingPreview.merged(source, draft).meta
        try:
            return self._resumed(draft, meta, source)
        except vault.CreatorMissing as missing:
            return no_creator_row(draft.pdf_name, missing)

    def _resumed(self, draft: DraftCard, meta: dict, source: Path) -> dict:
        if draft.filed:
            return self._reverify(draft, meta, source)
        return self._file_now(draft, meta, source)

    def _reverify(self, draft: DraftCard, meta: dict, source: Path) -> dict:
        self._record_assigned_citekey(draft, meta)
        placement = AttachmentWatcher.for_filing(source, meta).await_placement(draft.citekey)
        if not placement.verified:
            return self._unverified_row(draft, placement)
        outcome = FilingOutcome(source, meta, draft.citekey, zotero.ConnectorResult.saved(), placement)
        return self._completed(draft, outcome, STATUS_VERIFIED_ON_RETRY)

    def _record_assigned_citekey(self, draft: DraftCard, meta: dict) -> None:
        assigned = zotero.get_citation_key(draft.item_key) if draft.item_key else None
        if assigned and assigned != draft.citekey:
            draft.adopt(meta, assigned)
            draft.save()

    def _unverified_row(self, draft: DraftCard, placement: Placement) -> dict:
        return {"file": draft.pdf_name, "status": STATUS_STILL_UNVERIFIED,
                "citekey": draft.citekey, **placement.elsewhere()}

    def _file_now(self, draft: DraftCard, meta: dict, source: Path) -> dict:
        if CorpusNote(draft.pdf_name).exists():
            return {"file": draft.pdf_name, "status": STATUS_ALREADY_FILED}
        if self._holds_own_record(draft, meta):
            return self._reverify(draft, meta, source)
        duplicate = ZoteroHolding().duplicate_row(draft.pdf_name, meta, draft)
        if duplicate:
            return duplicate
        attempt = FilingAttempt(draft, source, meta)
        attempt.file()
        return self._attempted_row(draft, attempt.outcome())

    def _attempted_row(self, draft: DraftCard, outcome: FilingOutcome) -> dict:
        if not outcome.filed:
            return {"file": draft.pdf_name, "status": STATUS_RETRY_FAILED}
        if outcome.is_verified:
            return self._completed(draft, outcome, STATUS_RETRIED_OK)
        return {"file": draft.pdf_name, "status": STATUS_RETRIED_UNVERIFIED,
                "citekey": outcome.citekey, **outcome.placement.elsewhere()}

    def _holds_own_record(self, draft: DraftCard, meta: dict) -> bool:
        title = meta.get("title")
        return bool(draft.citekey and title and zotero.holds_titled_record(draft.citekey, title))

    def _completed(self, draft: DraftCard, outcome: FilingOutcome, status: str) -> dict:
        settlement = Settlement(self._completion, draft, outcome)
        settlement.settle()
        if settlement.completes:
            return {"file": outcome.placed.pdf_name, "status": status}
        return {"file": draft.pdf_name, "status": STATUS_NOTE_COLLISION,
                "citekey": outcome.citekey, "held_as": outcome.placed.pdf_name}

    def _source_pdf(self, draft: DraftCard) -> Path | None:
        in_inbox = vault.INBOX_DIR / draft.pdf_name
        if in_inbox.exists():
            return in_inbox
        filed = vault.LIBRARY_DIR / draft.pdf_name
        return filed if draft.filed and filed.exists() else None
