from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path

import vault
import zotero
from titlecase import title_case
from zotero import BetterBibtexError, ConnectorResult

from .checking import VERDICT_PASSED, ReviewCheck, TalkCard
from .listing import ReviewListing
from .mending import MarkerMend
from .raw import PARAGRAPH_JOIN
from .talk import TalkEntry

PRESENTATION_TYPE = "presentation"
PRESENTER_CREATOR_TYPE = "presenter"
RECORDING_LINK_TEXT = "Recording"
_RECORDING_LINK_RE = re.compile(rf"\A\[{RECORDING_LINK_TEXT}\]\((?P<url>[^)\s]+)\)")
_ENCODING = "utf-8"
_UNKNOWN_SURNAME = "unknown"
_PARTIAL_SUFFIX = ".partial"
_STAGED_SUFFIX = ".filing"


def recording_url_of(body: str) -> str | None:
    match = _RECORDING_LINK_RE.match(body.lstrip())
    return match.group("url") if match else None


class FilingRefused(RuntimeError):
    pass


class ZoteroLink:
    def save_item(self, meta: dict, source_uri: str) -> ConnectorResult:
        return zotero.save_item(meta, source_uri)

    def citekeys_beginning(self, prefix: str) -> set[str]:
        return zotero.held_citekeys_beginning(prefix)


class TalkRecord:
    def __init__(self, entry: TalkEntry) -> None:
        self._recording = entry.recording()
        self._card = TalkCard(entry).fields()

    @property
    def title(self) -> str:
        return title_case(str(self._card["title"]).strip()).text

    @property
    def presenters(self) -> list[dict]:
        return [{"firstName": str(presenter.get("firstName", "")).strip(),
                 "lastName": str(presenter["lastName"]).strip()}
                for presenter in self._card["presenters"]]

    @property
    def surnames(self) -> list[str]:
        return [presenter["lastName"] for presenter in self.presenters]

    @property
    def year(self) -> int:
        return int(self._card["year"])

    @property
    def meeting(self) -> str | None:
        return str(self._card.get("meeting") or "").strip() or None

    @property
    def url(self) -> str:
        return self._recording.url

    @property
    def basename(self) -> str:
        try:
            return vault.basename_of(Path(vault.library_filename(self.surnames, str(self.year), self.title)))
        except vault.CreatorMissing as missing:
            raise FilingRefused(f"the talk card names no presenters with a surname: {missing}") from missing

    @property
    def date(self) -> str:
        uploaded = self._recording.upload_date
        return uploaded if uploaded.startswith(str(self.year)) else str(self.year)

    def zotero_meta(self) -> dict:
        bib = {"url": self.url, "meetingName": self.meeting, "date": self.date,
               "accessDate": dt.date.today().isoformat()}
        return {"type": PRESENTATION_TYPE, "title": self.title, "authors": self.presenters, "year": self.year,
                "creator_type": PRESENTER_CREATOR_TYPE, "bib": bib}

    def frontmatter(self, citekey: str) -> dict:
        return {"title": self.title, "author": self.surnames, "year": self.year, "type": PRESENTATION_TYPE,
                "citekey": citekey, "meeting": self.meeting,
                "source_type": None, "source_role": None, "field": []}


class TranscriptCitekey:
    def __init__(self, record: TalkRecord, link: ZoteroLink) -> None:
        self._record = record
        self._link = link

    def allocated(self) -> str:
        surname = self._record.surnames[0] if self._record.surnames else _UNKNOWN_SURNAME
        base = vault.citekey(surname, str(self._record.year))
        return vault.unique_citekey(base, self._held_keys() | self._zotero_keys(base))

    def _zotero_keys(self, base: str) -> set[str]:
        try:
            return self._link.citekeys_beginning(base)
        except BetterBibtexError as error:
            raise FilingRefused(f"Better BibTeX did not answer the citekey lookup: {error}") from error

    @staticmethod
    def _held_keys() -> set[str]:
        keys = (vault.read_frontmatter_only(path).get("citekey") for path in vault.list_held_notes())
        return {str(key) for key in keys if key}


class TranscriptBody:
    def __init__(self, entry: TalkEntry, record: TalkRecord) -> None:
        self._entry = entry
        self._record = record

    def text(self) -> str:
        parts = [path.read_text(encoding=_ENCODING).strip() for path in ReviewListing(self._entry).reviewed_paths()]
        spoken = MarkerMend(PARAGRAPH_JOIN.join(parts)).mended()
        return f"[{RECORDING_LINK_TEXT}]({self._record.url}){PARAGRAPH_JOIN}{spoken}\n"


class SavedItem:
    def __init__(self, entry: TalkEntry) -> None:
        self._path = entry.saved_item

    @property
    def exists(self) -> bool:
        return self._path.exists()

    def fields(self) -> dict:
        return json.loads(self._path.read_text(encoding=_ENCODING))

    def record(self, fields: dict) -> None:
        with vault.ReplacementFile(self._path, _PARTIAL_SUFFIX) as replacement:
            replacement.path.write_text(json.dumps(fields), encoding=_ENCODING)
            replacement.commit()


class TalkFiling:
    def __init__(self, entry: TalkEntry, link: ZoteroLink | None = None) -> None:
        self._entry = entry
        self._link = link or ZoteroLink()
        self._record = TalkRecord(entry)
        self._saved = SavedItem(entry)

    def plan(self) -> dict:
        basename = self._record.basename
        citekey = self._citekey()
        return {"video_id": self._entry.video_id, "basename": basename, "citekey": citekey,
                "note": str(vault.transcript_path(basename)),
                "zotero_item": zotero.build_item(self._record.zotero_meta()),
                "frontmatter": self._record.frontmatter(citekey)}

    def apply(self) -> dict:
        self._require_passed_review()
        self._require_free_basename()
        plan = self.plan()
        reused = self._saved.exists
        saved = self._saved.fields() if reused else self._save_record(plan["citekey"])
        self._write_note(plan["frontmatter"], saved)
        return {**plan, "filed": True, "zotero_item_key": saved["item_key"], "zotero_reused": reused,
                **self._delete_entry()}

    def _delete_entry(self) -> dict:
        try:
            self._entry.delete()
        except OSError as error:
            return {"entry_deleted": False, "entry_error": f"the talk entry {self._entry.directory} was not "
                                                           f"deleted: {error}"}
        return {"entry_deleted": True, "entry_error": None}

    def _citekey(self) -> str:
        if self._saved.exists:
            return str(self._saved.fields()["citekey"])
        return TranscriptCitekey(self._record, self._link).allocated()

    def _require_passed_review(self) -> None:
        report = ReviewCheck(self._entry).report()
        if report["verdict"] != VERDICT_PASSED:
            raise FilingRefused(f"the review check did not pass; run review-check: {'; '.join(report['problems'])}")

    def _require_free_basename(self) -> None:
        held = vault.held_note_path(self._record.basename)
        if held.exists():
            raise FilingRefused(f"a note already holds the basename {self._record.basename!r}: {held}")

    def _save_record(self, citekey: str) -> dict:
        result = self._link.save_item(self._record.zotero_meta(), self._record.url)
        if not result.online:
            raise FilingRefused("Zotero is not running; start it and run file again")
        if not result.item_saved:
            raise FilingRefused("Zotero refused the item; nothing was written")
        saved = {"citekey": citekey, "item_key": result.item_key}
        self._saved.record(saved)
        return saved

    def _write_note(self, frontmatter: dict, saved: dict) -> None:
        path = vault.transcript_path(self._record.basename)
        try:
            NewNote(path).create(frontmatter, self._body())
        except FileExistsError as error:
            raise FilingRefused(f"a note already holds the basename {self._record.basename!r}: {path} appeared "
                                f"after the basename check and was left as it is; the Zotero item "
                                f"{saved['item_key']} is saved and the talk entry records it") from error
        except OSError as error:
            raise FilingRefused(f"the Zotero item {saved['item_key']} is saved but the note was not written: "
                                f"{error}; run file --apply again: it reuses the item") from error

    def _body(self) -> str:
        return TranscriptBody(self._entry, self._record).text()


class NewNote:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._staged = path.with_name(path.name + _STAGED_SUFFIX)

    def create(self, frontmatter: dict, body: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        vault.write_frontmatter(self._staged, frontmatter, body)
        try:
            os.link(self._staged, self._path)
        finally:
            self._staged.unlink(missing_ok=True)
