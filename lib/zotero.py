from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from enum import Enum
from http import HTTPStatus
from pathlib import Path

import requests

BASE_URL = "http://127.0.0.1:23119"
HEADERS = {"Zotero-Allowed-Request": "true", "Content-Type": "application/json"}
BBT_RPC_URL = f"{BASE_URL}/better-bibtex/json-rpc"
CSL_JSON_TRANSLATOR = "bc03b4fe-436d-4a1f-ba59-de4d2d7a63f7"

PING_TIMEOUT = 1.0
SAVE_TIMEOUT = 5.0
ATTACHMENT_TIMEOUT = 120.0
_FIRST_FAILING_STATUS = HTTPStatus.MULTIPLE_CHOICES
_FIRST_SERVER_ERROR_STATUS = HTTPStatus.INTERNAL_SERVER_ERROR
_CITEKEY_FIELD = "citationKey"
_DOI_FIELD = "DOI"
_ISBN_FIELD = "ISBN"
_TITLE_FIELD = "title"
_IS = "is"
_CONTAINS = "contains"
_CSL_CHAPTER_TYPE = "chapter"
CREATOR_FALLBACK_ORDER = ("author", "editor", "translator")
_ZOTERO_CHAPTER_TYPE = "bookSection"
DEFAULT_CREATOR_TYPE = "author"
EMPTY_FIELD_VALUES = (None, "", [])
DEFAULT_ITEM_TYPE = "book"
_ATTACHMENT_TITLE = "PDF"
_ITEM_URI_SEPARATOR = "/"


class BetterBibtexError(RuntimeError):
    pass


class _Post(Enum):
    ACCEPTED = "accepted"
    REFUSED = "refused"
    LOST = "lost"


@dataclass(frozen=True)
class ConnectorResult:
    online: bool
    item_saved: bool
    attachment_saved: bool
    connection_lost: bool = False
    item_key: str | None = None

    @classmethod
    def offline(cls) -> ConnectorResult:
        return cls(False, False, False)

    @classmethod
    def refused(cls) -> ConnectorResult:
        return cls(True, False, False)

    @classmethod
    def lost(cls) -> ConnectorResult:
        return cls(True, False, False, True)

    @classmethod
    def saved(cls) -> ConnectorResult:
        return cls(True, True, True)


@dataclass(frozen=True)
class HeldWorkQuery:
    title: str | None
    doi: str | None = None
    isbn: str | None = None
    first_creator: str | None = None
    chapter: bool = False

    @classmethod
    def of_meta(cls, meta: dict, doi: str | None = None, isbn: str | None = None) -> "HeldWorkQuery":
        authors = meta.get("authors") or []
        first_creator = authors[0].get("lastName") if authors else None
        return cls(meta.get("title"), doi, isbn, first_creator, meta.get("type") == _ZOTERO_CHAPTER_TYPE)


def build_item(meta: dict) -> dict:
    return _ZoteroItem(meta).as_dict()


class _ZoteroItem:
    def __init__(self, meta: dict) -> None:
        self._meta = meta
        self._bib = meta.get("bib") or {}

    def as_dict(self) -> dict:
        item = self._base()
        item.update(self._present_bib_fields())
        extra = self._extra(item.get("extra"))
        if extra:
            item["extra"] = extra
        return item

    def _base(self) -> dict:
        return {
            "itemType": self._meta.get("type") or DEFAULT_ITEM_TYPE,
            "title": self._meta.get("title", ""),
            "creators": self._creators(),
            "date": str(self._meta.get("year", "")),
        }

    def _creators(self) -> list[dict]:
        creator_type = self._meta.get("creator_type") or DEFAULT_CREATOR_TYPE
        return [{"creatorType": creator_type, "firstName": author.get("firstName", ""),
                 "lastName": author["lastName"]}
                for author in self._meta.get("authors", [])]

    def _present_bib_fields(self) -> dict:
        return {field: value for field, value in self._bib.items() if value not in EMPTY_FIELD_VALUES}

    def _extra(self, recorded: str | None) -> str:
        lines = [line for line in [recorded] if line]
        orig_year = self._meta.get("orig_year")
        if orig_year and str(orig_year) != str(self._meta.get("year", "")):
            lines.append(f"Original date: {orig_year}")
        return "\n".join(lines)


@dataclass(frozen=True)
class _SavedItem:
    outcome: _Post
    item_key: str | None = None

    @property
    def accepted(self) -> bool:
        return self.outcome is _Post.ACCEPTED

    def refusal(self) -> ConnectorResult:
        return ConnectorResult.lost() if self.outcome is _Post.LOST else ConnectorResult.refused()


class _SavedItemKey:
    def in_response(self, response) -> str | None:
        return self._first_key(self._items(response))

    def _items(self, response) -> list:
        try:
            body = response.json()
        except ValueError:
            return []
        return body.get("items") or [] if isinstance(body, dict) else []

    def _first_key(self, items: list) -> str | None:
        keys = (item.get("key") for item in items if isinstance(item, dict))
        return next((str(key) for key in keys if key), None)


@dataclass(frozen=True)
class _ConnectorSession:
    source_uri: str
    session_id: str
    connector_key: str


class Connector:
    def __init__(self, timeout: float = ATTACHMENT_TIMEOUT) -> None:
        self._timeout = timeout

    def is_online(self, timeout: float = PING_TIMEOUT) -> bool:
        try:
            return self._ping_answered(timeout)
        except requests.RequestException:
            return False

    def _ping_answered(self, timeout: float) -> bool:
        resp = requests.get(f"{BASE_URL}/connector/ping", headers=HEADERS, timeout=timeout)
        return resp.status_code < _FIRST_SERVER_ERROR_STATUS

    def save_item_with_attachment(self, meta: dict, pdf_path: Path) -> ConnectorResult:
        if not self.is_online():
            return ConnectorResult.offline()
        session = _ConnectorSession(Path(pdf_path).as_uri(), str(uuid.uuid4()), str(uuid.uuid4()))
        saved = self._save_item(build_item(meta), session)
        if not saved.accepted:
            return saved.refusal()
        attached = self._posted(lambda: self._save_attachment(session, Path(pdf_path)))
        return ConnectorResult(True, True, attached is _Post.ACCEPTED, item_key=saved.item_key)

    def save_item(self, meta: dict, source_uri: str) -> ConnectorResult:
        if not self.is_online():
            return ConnectorResult.offline()
        session = _ConnectorSession(source_uri, str(uuid.uuid4()), str(uuid.uuid4()))
        saved = self._save_item(build_item(meta), session)
        if not saved.accepted:
            return saved.refusal()
        return ConnectorResult(True, True, False, item_key=saved.item_key)

    def _posted(self, post) -> _Post:
        try:
            return _Post.ACCEPTED if post() else _Post.REFUSED
        except (requests.RequestException, OSError):
            return _Post.LOST

    def _save_item(self, item: dict, session: _ConnectorSession) -> _SavedItem:
        try:
            return self._posted_item(item, session)
        except (requests.RequestException, OSError):
            return _SavedItem(_Post.LOST)

    def _posted_item(self, item: dict, session: _ConnectorSession) -> _SavedItem:
        item["id"] = session.connector_key
        payload = {"items": [item], "uri": session.source_uri, "sessionID": session.session_id}
        resp = requests.post(f"{BASE_URL}/connector/saveItems", headers=HEADERS, json=payload,
                             timeout=self._timeout)
        if resp.status_code >= _FIRST_FAILING_STATUS:
            return _SavedItem(_Post.REFUSED)
        return _SavedItem(_Post.ACCEPTED, _SavedItemKey().in_response(resp))

    def _save_attachment(self, session: _ConnectorSession, pdf_path: Path) -> bool:
        resp = requests.post(f"{BASE_URL}/connector/saveAttachment",
                             headers=self._attachment_headers(session),
                             data=pdf_path.read_bytes(), timeout=self._timeout)
        return resp.status_code < _FIRST_FAILING_STATUS

    def _attachment_headers(self, session: _ConnectorSession) -> dict:
        metadata = {"sessionID": session.session_id, "parentItemID": session.connector_key,
                    "title": _ATTACHMENT_TITLE, "url": session.source_uri}
        return {**HEADERS, "Content-Type": "application/pdf", "X-Metadata": json.dumps(metadata)}


class BetterBibtex:
    def __init__(self, timeout: float = SAVE_TIMEOUT) -> None:
        self._timeout = timeout

    def item_key(self, citekey: str) -> str | None:
        for item in self._search(_CITEKEY_FIELD, _IS, citekey):
            if item.get("citekey") == citekey and item.get("id"):
                return str(item["id"]).rsplit(_ITEM_URI_SEPARATOR, 1)[-1]
        return None

    def holds_titled(self, citekey: str, title: str) -> bool:
        found = self._search(_CITEKEY_FIELD, _IS, citekey)
        return any(item.get("citekey") == citekey and self._titled(item, title) for item in found)

    def citekeys_beginning(self, prefix: str) -> set[str]:
        found = self._search(_CITEKEY_FIELD, _CONTAINS, prefix)
        return {str(item["citekey"]) for item in found if str(item.get("citekey", "")).startswith(prefix)}

    def existing_citekey(self, query: HeldWorkQuery) -> str | None:
        return (self._citekey_with_doi(query.doi) or self._citekey_with_isbn(query)
                or self._citekey_with_title(query))

    def _citekey_with_doi(self, doi: str | None) -> str | None:
        return self._first_citekey(self._search(_DOI_FIELD, _IS, doi)) if doi else None

    def _citekey_with_isbn(self, query: HeldWorkQuery) -> str | None:
        if query.chapter or not query.isbn:
            return None
        found = self._search(_ISBN_FIELD, _CONTAINS, query.isbn)
        return self._first_citekey([item for item in found if item.get("type") != _CSL_CHAPTER_TYPE])

    def _citekey_with_title(self, query: HeldWorkQuery) -> str | None:
        if not query.title:
            return None
        found = self._search(_TITLE_FIELD, _CONTAINS, query.title)
        return self._first_citekey([item for item in found
                                    if self._titled(item, query.title) and self._by(item, query.first_creator)])

    def _titled(self, item: dict, title: str) -> bool:
        return str(item.get("title", "")).strip().casefold() == title.strip().casefold()

    def _by(self, item: dict, first_creator: str | None) -> bool:
        held_creator = self._first_family(item)
        if first_creator is None or held_creator is None:
            return True
        return held_creator.casefold() == first_creator.strip().casefold()

    @staticmethod
    def _first_family(item: dict) -> str | None:
        people = next((item[role] for role in CREATOR_FALLBACK_ORDER if item.get(role)), [])
        family = people[0].get("family") or people[0].get("literal") if people else None
        return str(family) if family else None

    def _first_citekey(self, items: list[dict]) -> str | None:
        return next((str(item["citekey"]) for item in items if item.get("citekey")), None)

    def _search(self, field: str, operator: str, value: str) -> list[dict]:
        found = self._required("item.search", [[[field, operator, value]]]) or []
        return [item for item in found if isinstance(item, dict)]

    def _required(self, method: str, params: list):
        try:
            response, payload = self._posted(method, params)
        except (requests.RequestException, ValueError) as failure:
            raise BetterBibtexError(f"Better BibTeX {method} failed: {failure}") from failure
        if response.status_code >= _FIRST_FAILING_STATUS or "error" in payload:
            raise BetterBibtexError(f"Better BibTeX {method} failed: {payload.get('error') or response.status_code}")
        return payload.get("result")

    def _posted(self, method: str, params: list) -> tuple:
        response = self._post(method, params)
        return response, response.json()

    def attachments(self, citekey: str) -> list[dict]:
        return self._call("item.attachments", [citekey]) or []

    def pdf_attachment_link(self, citekey: str) -> str | None:
        for attachment in self._required("item.attachments", [citekey]) or []:
            link = attachment.get("open")
            if link and str(attachment.get("path", "")).lower().endswith(".pdf"):
                return str(link)
        return None

    def citation_key(self, item_key: str) -> str | None:
        keys = self._call("item.citationkey", [[item_key]]) or {}
        return keys.get(item_key) or None

    def csl_record(self, citekey: str) -> dict | None:
        exported = self._call("item.export", [[citekey], CSL_JSON_TRANSLATOR])
        records = json.loads(exported) if exported else []
        return records[0] if records else None

    def pdf_link(self, citekey: str) -> str | None:
        pdf_link = self.pdf_attachment_link(citekey)
        if pdf_link:
            return pdf_link
        item_key = self.item_key(citekey)
        return f"zotero://select/library/items/{item_key}" if item_key else None

    def _call(self, method: str, params: list):
        try:
            return self._required(method, params)
        except BetterBibtexError:
            return None

    def _post(self, method: str, params: list):
        return requests.post(BBT_RPC_URL, timeout=self._timeout,
                             json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1})


class ZoteroLibrary:
    @staticmethod
    def is_online(timeout: float = PING_TIMEOUT) -> bool:
        return Connector().is_online(timeout)

    @staticmethod
    def save_item_with_attachment(meta: dict, pdf_path, timeout: float = ATTACHMENT_TIMEOUT) -> ConnectorResult:
        return Connector(timeout).save_item_with_attachment(meta, pdf_path)

    @staticmethod
    def save_item(meta: dict, source_uri: str, timeout: float = SAVE_TIMEOUT) -> ConnectorResult:
        return Connector(timeout).save_item(meta, source_uri)

    @staticmethod
    def get_item_key(citekey: str) -> str | None:
        return BetterBibtex().item_key(citekey)

    @staticmethod
    def holds_titled_record(citekey: str, title: str) -> bool:
        return BetterBibtex().holds_titled(citekey, title)

    @staticmethod
    def held_citekeys_beginning(prefix: str) -> set[str]:
        return BetterBibtex().citekeys_beginning(prefix)

    @staticmethod
    def get_attachments(citekey: str) -> list[dict]:
        return BetterBibtex().attachments(citekey)

    @staticmethod
    def build_pdf_link(citekey: str) -> str | None:
        return BetterBibtex().pdf_link(citekey)

    @staticmethod
    def get_citation_key(item_key: str) -> str | None:
        return BetterBibtex().citation_key(item_key)

    @staticmethod
    def find_existing_citekey(query: HeldWorkQuery) -> str | None:
        return BetterBibtex().existing_citekey(query)

    @staticmethod
    def get_csl_record(citekey: str) -> dict | None:
        return BetterBibtex().csl_record(citekey)


is_online = ZoteroLibrary.is_online
save_item_with_attachment = ZoteroLibrary.save_item_with_attachment
save_item = ZoteroLibrary.save_item
get_item_key = ZoteroLibrary.get_item_key
holds_titled_record = ZoteroLibrary.holds_titled_record
held_citekeys_beginning = ZoteroLibrary.held_citekeys_beginning
get_attachments = ZoteroLibrary.get_attachments
build_pdf_link = ZoteroLibrary.build_pdf_link
get_citation_key = ZoteroLibrary.get_citation_key
find_existing_citekey = ZoteroLibrary.find_existing_citekey
get_csl_record = ZoteroLibrary.get_csl_record


if __name__ == "__main__":
    print("Zotero online:", is_online())
