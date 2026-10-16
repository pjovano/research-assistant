from __future__ import annotations

import shutil
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import vault
import zotero

from _file.notes import CorpusNote, NoteFrontmatter
from _file.filing import STATUS_ALREADY_FILED, STATUS_ZOTERO_OFFLINE

ZOTERO_DATA_DIR_KEY = "zotero_data_dir"
DEFAULT_ZOTERO_DATA_DIR = "~/Zotero"
STATUS_WOULD_WRITE = "would-write"
STATUS_NOTE_WRITTEN = "note-written"
STATUS_NO_RECORD = "no-record-attaches-pdf"
STATUS_NO_CITEKEY = "no-citekey"
STATUS_RECORD_UNREADABLE = "record-unreadable"
STATUS_UNKNOWN_ITEM_TYPE = "unknown-item-type"
STATUS_HELD_AS_TRANSCRIPT = "held-as-transcript"
_DATABASE_NAME = "zotero.sqlite"
_READ_ONLY_URI = "file:{path}?mode=ro"
_DATABASE_FILE_SUFFIXES = ("", "-wal", "-shm")
_SNAPSHOT_DIR_NAME = "zotero"
_LINKED_FILE_PREFIX = "attachments:"
_PARENT_KEY_SQL = """
    SELECT parent.key FROM itemAttachments AS attachment
    JOIN items AS parent ON parent.itemID = attachment.parentItemID
    WHERE (attachment.path = ? OR attachment.path LIKE ?)
      AND parent.itemID NOT IN (SELECT itemID FROM deletedItems)
"""
_ITEM_TYPES_BY_CSL_TYPE = {
    "book": "book",
    "chapter": "bookSection",
    "article-journal": "journalArticle",
    "article-magazine": "magazineArticle",
    "article-newspaper": "newspaperArticle",
    "paper-conference": "conferencePaper",
    "thesis": "thesis",
    "report": "report",
    "manuscript": "manuscript",
    "webpage": "webpage",
    "entry-encyclopedia": "encyclopediaArticle",
    "entry-dictionary": "dictionaryEntry",
    "document": "document",
    "posted-content": "preprint",
    "article": "preprint",
    "speech": "presentation",
    "dissertation": "thesis",
}


class RecordProblem(Exception):
    def __init__(self, status: str, detail: str | None = None) -> None:
        super().__init__(status)
        self.status = status
        self.detail = detail


class CslName:
    def __init__(self, name: dict) -> None:
        self._name = name

    def as_creator(self) -> dict:
        if self._name.get("literal"):
            return {"firstName": "", "lastName": self._name["literal"]}
        return {"firstName": self._joined("given", "dropping-particle"),
                "lastName": self._joined("non-dropping-particle", "family")}

    def _joined(self, *keys: str) -> str:
        return " ".join(part for part in (self._name.get(key, "") for key in keys) if part)


class CslRecord:
    def __init__(self, record: dict) -> None:
        self._record = record

    @property
    def csl_type(self) -> str:
        return str(self._record.get("type", ""))

    @property
    def item_type(self) -> str | None:
        return _ITEM_TYPES_BY_CSL_TYPE.get(self.csl_type)

    def meta(self) -> dict:
        return {"title": self._record.get("title", ""), "authors": self._creators(),
                "year": self.year("issued"), "orig_year": self.year("original-date"),
                "type": self.item_type, "aliases": [], "bib": {"extra": self._record.get("note")}}

    def _creators(self) -> list[dict]:
        for role in zotero.CREATOR_FALLBACK_ORDER:
            names = self._record.get(role) or []
            if names:
                return [CslName(name).as_creator() for name in names]
        return []

    def year(self, field: str) -> str | None:
        parts = (self._record.get(field) or {}).get("date-parts") or [[]]
        first = parts[0][0] if parts[0] else None
        return str(first) if first else None


class ZoteroDatabase:
    def __init__(self, path: Path) -> None:
        self._path = path

    @classmethod
    def configured(cls) -> "ZoteroDatabase":
        configured = vault.MACHINE.get(ZOTERO_DATA_DIR_KEY, DEFAULT_ZOTERO_DATA_DIR)
        return cls(Path(configured).expanduser() / _DATABASE_NAME)

    def parent_item_key(self, pdf_name: str) -> str | None:
        self._require_database()
        parameters = (f"{_LINKED_FILE_PREFIX}{pdf_name}", f"%/{pdf_name}")
        with closing(sqlite3.connect(_READ_ONLY_URI.format(path=self._snapshot()), uri=True)) as connection:
            row = connection.execute(_PARENT_KEY_SQL, parameters).fetchone()
        return row[0] if row else None

    def _snapshot(self) -> Path:
        snapshot_dir = vault.SCRATCH_DIR / _SNAPSHOT_DIR_NAME
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        for suffix in _DATABASE_FILE_SUFFIXES:
            self._copy_part(self._path.with_name(self._path.name + suffix), snapshot_dir)
        return snapshot_dir / self._path.name

    @staticmethod
    def _copy_part(source: Path, snapshot_dir: Path) -> None:
        if source.exists():
            shutil.copy2(source, snapshot_dir / source.name)
        else:
            (snapshot_dir / source.name).unlink(missing_ok=True)

    def _require_database(self) -> None:
        if not self._path.exists():
            raise SystemExit(f"Zotero database not found at {self._path}; "
                             f"name the data directory in machine.json under {ZOTERO_DATA_DIR_KEY}")


@dataclass(frozen=True)
class LocatedRecord:
    citekey: str
    link: str
    record: CslRecord


class RecordLocator:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def locate(self) -> LocatedRecord:
        item_key = ZoteroDatabase.configured().parent_item_key(self._pdf_path.name)
        if not item_key:
            raise RecordProblem(STATUS_NO_RECORD)
        citekey = zotero.get_citation_key(item_key)
        if not citekey:
            raise RecordProblem(STATUS_NO_CITEKEY, item_key)
        return LocatedRecord(citekey, self._link(citekey), self._record(citekey))

    def _record(self, citekey: str) -> CslRecord:
        exported = zotero.get_csl_record(citekey)
        if exported is None:
            raise RecordProblem(STATUS_RECORD_UNREADABLE, citekey)
        return CslRecord(exported)

    def _link(self, citekey: str) -> str:
        try:
            link = zotero.build_pdf_link(citekey)
        except zotero.BetterBibtexError as failure:
            raise RecordProblem(STATUS_RECORD_UNREADABLE, citekey) from failure
        if not link:
            raise RecordProblem(STATUS_RECORD_UNREADABLE, citekey)
        return link


@dataclass(frozen=True)
class NotePlan:
    citekey: str
    link: str
    fields: dict


class FiledRecordNote:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path
        self._note = CorpusNote(pdf_path.name)

    def preview(self) -> dict:
        return self._attempt(lambda plan: STATUS_WOULD_WRITE)

    def write(self) -> dict:
        return self._attempt(self._written)

    def _written(self, plan: NotePlan) -> str:
        self._note.write(plan.fields, plan.link, "")
        return STATUS_NOTE_WRITTEN

    def _attempt(self, status_of: Callable[[NotePlan], str]) -> dict:
        try:
            plan = self._plan()
        except RecordProblem as problem:
            return {"file": self._pdf_path.name, "status": problem.status, "detail": problem.detail}
        return {"file": self._pdf_path.name, "status": status_of(plan), "citekey": plan.citekey,
                "link": plan.link, "frontmatter": plan.fields, "note": str(self._note.path)}

    def _plan(self) -> NotePlan:
        self._require_unheld_basename()
        if not zotero.is_online():
            raise RecordProblem(STATUS_ZOTERO_OFFLINE)
        located = RecordLocator(self._pdf_path).locate()
        if located.record.item_type is None:
            raise RecordProblem(STATUS_UNKNOWN_ITEM_TYPE, located.record.csl_type)
        fields = NoteFrontmatter(located.record.meta(), located.citekey).fields()
        return NotePlan(located.citekey, located.link, fields)

    def _require_unheld_basename(self) -> None:
        if self._note.exists():
            raise RecordProblem(STATUS_ALREADY_FILED)
        basename = self._note.path.stem
        if vault.held_note_exists(basename):
            raise RecordProblem(STATUS_HELD_AS_TRANSCRIPT, str(vault.transcript_path(basename)))
