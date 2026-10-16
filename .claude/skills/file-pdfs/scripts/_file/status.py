from __future__ import annotations

import vault
import zotero

from _file.bib import RequiredFields
from _file.notes import DraftCard
from _file.paths import NotePaths
from _file.retry import PendingDrafts


class StatusReport:
    def render(self) -> dict:
        drafts = PendingDrafts().drafts()
        return {
            "filed_notes": len(NotePaths().notes()),
            "filed_unverified": [self._identity(d) for d in drafts if d.filed],
            "unfiled": [self._identity(d) for d in drafts if not d.filed],
            "incomplete_citation_fields": self._incomplete(drafts),
            "conflict_copies": vault.library_conflict_copies(),
        }

    def _incomplete(self, drafts: list[DraftCard]) -> list[dict]:
        rows = ({**self._identity(d), "missing": self._missing(d)} for d in drafts if not d.filed)
        return [row for row in rows if row["missing"]]

    def _identity(self, draft: DraftCard) -> dict:
        return {"file": draft.pdf_name, "citekey": draft.citekey}

    def _missing(self, draft: DraftCard) -> list[str]:
        return RequiredFields().missing(draft.item_type, draft.zotero)


class DoctorReport:
    def render(self) -> dict:
        return {
            "inbox_dir": str(vault.INBOX_DIR),
            "inbox_exists": vault.INBOX_DIR.exists(),
            "library_dir": str(vault.LIBRARY_DIR),
            "library_exists": vault.LIBRARY_DIR.exists(),
            "corpus_dir": str(vault.CORPUS_DIR),
            "zotero_online": zotero.is_online(),
            "conflict_copies": vault.library_conflict_copies(),
        }
