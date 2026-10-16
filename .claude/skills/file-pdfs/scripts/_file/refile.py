from __future__ import annotations

import filecmp
import shutil
from pathlib import Path

import vault
from zotero import ConnectorResult

from _file.bib import RequiredFields
from _file.notes import CorpusNote, DraftCard
from _file.citekeys import CitekeyAllocator
from _file.filing import (
    AssignedCitekey,
    AttachmentWatcher,
    FilingCompletion,
    FilingOutcome,
    ItemFiler,
    PlacedAttachment,
    Placement,
    note_changed_row,
)
from _file.preview import FilingPreview

REFILING_DIR_NAME = ".refiling"
STATUS_REFILE_FAILED = "refile-failed"
STATUS_REFILED = "refiled"

_RESTORED_NOTE = "the PDF was restored to the library; nothing was lost"
_KEPT_IN_HOLDING_NOTE = ("the library already holds another file under this name, so the PDF was not put back; "
                         "the original is kept at the holding path")
_BLOCKED_REASON = (
    "Delete the existing Zotero item for this citekey first, then re-run with "
    "--stale-item-deleted. Refiling over a live item creates a duplicate."
)


class RefileTarget:
    def __init__(self, library_name: str) -> None:
        self._library_name = library_name
        self._note = CorpusNote(library_name)
        self._draft = DraftCard(library_name).load()

    @property
    def library_name(self) -> str:
        return self._library_name

    @property
    def library_path(self) -> Path:
        return vault.LIBRARY_DIR / self._library_name

    @property
    def draft(self) -> DraftCard:
        return self._draft

    def meta(self) -> dict:
        self._require_filed_work()
        return FilingPreview.merged(self.library_path, self._draft).meta

    def citekey(self, meta: dict) -> str:
        return CitekeyAllocator().for_meta(meta, exclude_stem=Path(self._library_name).stem)

    def _require_filed_work(self) -> None:
        if not self.library_path.exists():
            raise SystemExit(f"PDF missing from the library: {self._library_name}")
        if not self._note.exists():
            raise SystemExit(f"No corpus file for {self._library_name} -- use `file` instead.")


class Refiler:
    def __init__(self, target: RefileTarget, completion: FilingCompletion) -> None:
        self._target = target
        self._completion = completion
        self._meta = target.meta()
        self._citekey = target.citekey(self._meta)
        self._holding = vault.LIBRARY_DIR / REFILING_DIR_NAME / target.library_name

    def require_complete_bib(self) -> None:
        missing = self._missing_bib()
        if missing:
            raise SystemExit(
                f"Refusing to refile {self._target.library_name}: missing {missing}. "
                f"Record them with `bib --set` first (they cannot be added afterwards), "
                f"or pass --allow-incomplete."
            )

    def blocked_report(self) -> dict:
        return {
            "status": "blocked",
            "file": self._target.library_name,
            "citekey": self._citekey,
            "reason": _BLOCKED_REASON,
            "item_to_be_filed": self._meta["bib"],
        }

    def execute(self) -> dict:
        self._withdraw_from_library()
        try:
            return self._filed_from_holding()
        except BaseException:
            self._put_back()
            raise

    def refused_row(self, changed: vault.NoteChangedOnDisk) -> dict:
        return {**self._restored_row(STATUS_REFILE_FAILED), **note_changed_row(self._target.library_name, changed)}

    def _filed_from_holding(self) -> dict:
        result = ItemFiler().file(self._meta, self._holding)
        if not result.item_saved:
            self._put_back()
            return self._restored_row(STATUS_REFILE_FAILED)
        self._record_assigned_citekey(result)
        placement = AttachmentWatcher(self._target.library_name).await_placement(self._citekey)
        self._settle(placement)
        return self._settled_row(placement)

    def _record_assigned_citekey(self, result: ConnectorResult) -> None:
        draft = self._target.draft
        draft.mark_filed()
        draft.set_item_key(result.item_key)
        draft.adopt(self._meta, self._citekey)
        draft.save()
        self._citekey = AssignedCitekey(self._citekey).after(result, self._meta)
        draft.adopt(self._meta, self._citekey)
        draft.save()

    def _settle(self, placement: Placement) -> None:
        if placement.verified:
            self._complete(placement.verified)
        elif not placement.other_name:
            self._put_back()

    def _settled_row(self, placement: Placement) -> dict:
        if placement.verified:
            return {"file": placement.verified.pdf_name, "status": STATUS_REFILED, "citekey": self._citekey}
        if placement.other_name:
            return self._renamed_row(placement.other_name)
        return {**self._restored_row("refiled-unverified"), "citekey": self._citekey}

    def _withdraw_from_library(self) -> None:
        self._holding.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self._target.library_path, self._holding)
        self._target.library_path.unlink()

    def _put_back(self) -> None:
        if self._holding.exists() and not self._target.library_path.exists():
            shutil.copy2(self._holding, self._target.library_path)

    def _complete(self, placed: PlacedAttachment) -> None:
        outcome = FilingOutcome(self._holding, self._meta, self._citekey, ConnectorResult.saved(), Placement(placed))
        self._completion.complete(outcome)

    def _restored_row(self, status: str) -> dict:
        row = {"file": self._target.library_name, "status": status}
        if self._holding_is_in_library():
            return {**row, "note": _RESTORED_NOTE}
        return {**row, "note": _KEPT_IN_HOLDING_NOTE, "holding": str(self._holding)}

    def _holding_is_in_library(self) -> bool:
        library_pdf = self._target.library_path
        return library_pdf.exists() and filecmp.cmp(self._holding, library_pdf, shallow=False)

    def _renamed_row(self, placed_as: str) -> dict:
        return {"file": self._target.library_name, "status": "refile-renamed",
                "placed_as": placed_as, "citekey": self._citekey, "holding": str(self._holding),
                "note": "the corpus file and the bibliographies still carry the old basename"}

    def _missing_bib(self) -> list[str]:
        return RequiredFields().missing_for_a_new_record(self._meta)
