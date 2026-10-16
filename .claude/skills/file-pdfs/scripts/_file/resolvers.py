from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from http import HTTPStatus

import requests

import identifiers
import vault

CROSSREF_MAILTO_KEY = "crossref_mailto"
SERVICE_CROSSREF = "crossref"
SERVICE_GOOGLE_BOOKS = "google books"
SERVICE_OPEN_LIBRARY = "open library"
SERVICE_ARXIV = "arxiv"
ARXIV_ARCHIVE = "arXiv"
LOOKUP_TIMEOUT_SECONDS = 10.0

_CROSSREF_WORKS = "https://api.crossref.org/works/"
_GOOGLE_BOOKS_VOLUMES = "https://www.googleapis.com/books/v1/volumes?q=isbn:"
_OPEN_LIBRARY = "https://openlibrary.org"
_ARXIV_QUERY = "https://export.arxiv.org/api/query?id_list="
_USER_AGENT = "ResearchVault/1"
_ATOM = "{http://www.w3.org/2005/Atom}"
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"
_ARXIV_CSL_TYPE = "posted-content"
_BOOK_CSL_TYPE = "book"
_CSL_TYPES_BY_CROSSREF_TYPE = {
    "journal-article": "article-journal",
    "book-chapter": "chapter",
    "book-section": "chapter",
    "book-part": "chapter",
    "book": "book",
    "monograph": "book",
    "edited-book": "book",
    "reference-book": "book",
    "proceedings-article": "paper-conference",
    "posted-content": "posted-content",
    "dissertation": "dissertation",
    "report": "report",
}
_FIRST_OK_STATUS = HTTPStatus.OK
_FIRST_FAILING_STATUS = HTTPStatus.MULTIPLE_CHOICES
_YEAR = re.compile(r"\d{4}")


class LookupFailed(Exception):
    pass


@dataclass(frozen=True)
class Fetched:
    status: int
    text: str

    @property
    def ok(self) -> bool:
        return _FIRST_OK_STATUS <= self.status < _FIRST_FAILING_STATUS


class RequestsFetcher:
    def fetch(self, url: str) -> Fetched:
        try:
            response = requests.get(url, headers=self._headers(), timeout=LOOKUP_TIMEOUT_SECONDS)
        except requests.RequestException as error:
            raise LookupFailed(f"network failure: {error.__class__.__name__}") from error
        return Fetched(response.status_code, response.text)

    def _headers(self) -> dict:
        mailto = vault.MACHINE.get(CROSSREF_MAILTO_KEY)
        agent = f"{_USER_AGENT} (mailto:{mailto})" if mailto else _USER_AGENT
        return {"User-Agent": agent, "Accept": "application/json, application/atom+xml"}


@dataclass(frozen=True)
class Resolution:
    identifier: identifiers.Identifier
    service: str
    record: dict


class JsonEndpoint:
    def __init__(self, fetcher) -> None:
        self._fetcher = fetcher

    def payload(self, url: str) -> dict:
        fetched = self._fetcher.fetch(url)
        if not fetched.ok:
            raise LookupFailed(f"HTTP {fetched.status} from {url}")
        try:
            return json.loads(fetched.text)
        except json.JSONDecodeError as error:
            raise LookupFailed(f"unreadable response from {url}") from error


class CrossrefResolver:
    def __init__(self, fetcher) -> None:
        self._endpoint = JsonEndpoint(fetcher)

    def resolve(self, doi: str) -> Resolution:
        message = self._endpoint.payload(f"{_CROSSREF_WORKS}{doi}").get("message") or {}
        if not message:
            raise LookupFailed(f"Crossref returned no work for {doi}")
        return Resolution(identifiers.Identifier(identifiers.KIND_DOI, doi), SERVICE_CROSSREF,
                          CrossrefMessage(message).as_csl())


class CrossrefMessage:
    _LIST_VALUED_SCALARS = ("title", "container-title", "short-container-title", "publisher-location")

    def __init__(self, message: dict) -> None:
        self._message = message

    def as_csl(self) -> dict:
        csl = dict(self._message)
        for key in self._LIST_VALUED_SCALARS:
            if key in csl:
                csl[key] = self._first(csl[key])
        crossref_type = str(csl.get("type", ""))
        csl["type"] = _CSL_TYPES_BY_CROSSREF_TYPE.get(crossref_type, crossref_type)
        csl["publisher-place"] = csl.get("publisher-location", "")
        csl["issn-by-type"] = self._issn_by_type()
        return csl

    def _first(self, value: object) -> str:
        if isinstance(value, list):
            return str(value[0]) if value else ""
        return str(value or "")

    def _issn_by_type(self) -> dict:
        return {entry.get("type", ""): entry.get("value", "")
                for entry in self._message.get("issn-type") or [] if entry.get("value")}


class IsbnResolver:
    def __init__(self, fetcher) -> None:
        self._endpoint = JsonEndpoint(fetcher)

    def resolve(self, isbn: str) -> Resolution:
        identifier = identifiers.Identifier(identifiers.KIND_ISBN, isbn)
        try:
            return self._from_google_books(identifier, isbn)
        except LookupFailed:
            return Resolution(identifier, SERVICE_OPEN_LIBRARY, self._open_library(isbn))

    def _from_google_books(self, identifier: identifiers.Identifier, isbn: str) -> Resolution:
        return Resolution(identifier, SERVICE_GOOGLE_BOOKS, self._google_books(isbn))

    def _google_books(self, isbn: str) -> dict:
        items = self._endpoint.payload(f"{_GOOGLE_BOOKS_VOLUMES}{isbn}").get("items") or []
        if not items:
            raise LookupFailed(f"Google Books holds no volume for {isbn}")
        return GoogleVolume(items[0].get("volumeInfo") or {}).as_csl()

    def _open_library(self, isbn: str) -> dict:
        edition = self._endpoint.payload(f"{_OPEN_LIBRARY}/isbn/{isbn}.json")
        authors = [self._endpoint.payload(f"{_OPEN_LIBRARY}{ref['key']}.json").get("name", "")
                   for ref in edition.get("authors") or [] if ref.get("key")]
        return OpenLibraryEdition(edition, authors).as_csl()


class PersonName:
    def __init__(self, full_name: str) -> None:
        self._full_name = full_name.strip()

    def as_csl(self) -> dict:
        if "," in self._full_name:
            family, _, given = self._full_name.partition(",")
            return {"family": family.strip(), "given": given.strip()}
        given, _, family = self._full_name.rpartition(" ")
        return {"family": family, "given": given, "split-on-whitespace": True}


class GoogleVolume:
    def __init__(self, info: dict) -> None:
        self._info = info

    def as_csl(self) -> dict:
        return {
            "type": _BOOK_CSL_TYPE,
            "title": self._info.get("title", ""),
            "subtitle": _subtitle_list(self._info),
            "author": _csl_authors(self._info.get("authors") or []),
            "publisher": self._info.get("publisher", ""),
            "issued": _date_parts(self._info.get("publishedDate", "")),
            "ISBN": [entry.get("identifier", "") for entry in self._info.get("industryIdentifiers") or []],
            "language": self._info.get("language", ""),
        }


class OpenLibraryEdition:
    def __init__(self, edition: dict, author_names: list[str]) -> None:
        self._edition = edition
        self._author_names = author_names

    def as_csl(self) -> dict:
        publishers = self._edition.get("publishers") or []
        return {
            "type": _BOOK_CSL_TYPE,
            "title": self._edition.get("title", ""),
            "subtitle": _subtitle_list(self._edition),
            "author": _csl_authors(self._author_names),
            "publisher": publishers[0] if publishers else "",
            "publisher-place": (self._edition.get("publish_places") or [""])[0],
            "issued": _date_parts(self._edition.get("publish_date", "")),
            "ISBN": list(self._edition.get("isbn_13") or []) + list(self._edition.get("isbn_10") or []),
        }


class ArxivResolver:
    def __init__(self, fetcher) -> None:
        self._fetcher = fetcher

    def resolve(self, arxiv_id: str) -> Resolution:
        fetched = self._fetcher.fetch(f"{_ARXIV_QUERY}{arxiv_id}")
        if not fetched.ok:
            raise LookupFailed(f"HTTP {fetched.status} from arXiv for {arxiv_id}")
        entry = ArxivFeed(fetched.text).entry()
        return Resolution(identifiers.Identifier(identifiers.KIND_ARXIV, arxiv_id), SERVICE_ARXIV,
                          ArxivEntry(entry, arxiv_id).as_csl())


class ArxivFeed:
    def __init__(self, atom: str) -> None:
        self._atom = atom

    def entry(self) -> ElementTree.Element:
        try:
            root = ElementTree.fromstring(self._atom)
        except ElementTree.ParseError as error:
            raise LookupFailed("unreadable arXiv feed") from error
        entry = root.find(f"{_ATOM}entry")
        if entry is None or entry.find(f"{_ATOM}title") is None:
            raise LookupFailed("arXiv returned no entry")
        return entry


class ArxivEntry:
    def __init__(self, entry: ElementTree.Element, arxiv_id: str) -> None:
        self._entry = entry
        self._arxiv_id = arxiv_id

    def as_csl(self) -> dict:
        return {
            "type": _ARXIV_CSL_TYPE,
            "title": " ".join(self._text("title").split()),
            "author": _csl_authors([author.findtext(f"{_ATOM}name") or ""
                                    for author in self._entry.findall(f"{_ATOM}author")]),
            "issued": _date_parts(self._text("published")),
            "URL": self._text("id"),
            "DOI": self._entry.findtext(f"{_ARXIV_NS}doi") or "",
            "archive": ARXIV_ARCHIVE,
            "archive_location": self._arxiv_id,
        }

    def _text(self, tag: str) -> str:
        return (self._entry.findtext(f"{_ATOM}{tag}") or "").strip()


def _date_parts(text: str) -> dict:
    match = _YEAR.search(text or "")
    return {"date-parts": [[int(match.group(0))]]} if match else {}


def _subtitle_list(record: dict) -> list[str]:
    return [record["subtitle"]] if record.get("subtitle") else []


def _csl_authors(names: list[str]) -> list[dict]:
    return [PersonName(name).as_csl() for name in names]
