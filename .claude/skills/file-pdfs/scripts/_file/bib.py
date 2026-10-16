from __future__ import annotations

import json
import re
from pathlib import Path

import vault
import zotero

from _file.notes import DraftCard
from _file.citekeys import CitekeyAllocator
from _file.probe import PdfProbe

REQUIRED_BIB_FIELDS = {
    "journalArticle": ["publicationTitle", "volume", "pages"],
    "bookSection": ["bookTitle", "publisher", "place", "pages"],
    "book": ["publisher", "place"],
    "thesis": ["university", "place"],
    "conferencePaper": ["proceedingsTitle", "publisher"],
    "report": ["institution", "place"],
}

ALWAYS_REQUIRED_BIB_FIELDS = ("date",)
RECORD_IDENTITY_FIELDS = ("title", "creators")

_ORIG_YEAR_FIELD = "orig_year"
_ALIASES_FIELD = "aliases"
_CREATORS_FIELD = "creators"
_SINGLE_FIELD_NAME = "name"

_ANY_YEAR = re.compile(r"\d{4}")

_ITEM_EXISTS = (
    "The Zotero item for {name} already exists; the connector cannot update it. "
    "Repair it in Zotero, or delete it and run `refile`."
)


class RequiredFields:
    def missing(self, item_type: str, bib: dict) -> list[str]:
        required = [*ALWAYS_REQUIRED_BIB_FIELDS, *REQUIRED_BIB_FIELDS.get(item_type, [])]
        return [field for field in required if not bib.get(field)]

    def missing_from_meta(self, meta: dict) -> list[str]:
        return self.missing(meta["type"], meta["bib"])

    def missing_for_a_new_record(self, meta: dict) -> list[str]:
        unidentified = [field for field in RECORD_IDENTITY_FIELDS if not meta["bib"].get(field)]
        return unidentified + self.missing_from_meta(meta)


class MetadataMerge:
    def into(self, meta: dict, draft: DraftCard) -> None:
        self._normalize_shouted_names(meta)
        meta[_ORIG_YEAR_FIELD] = draft.orig_year
        meta[_ALIASES_FIELD] = draft.aliases
        meta["bib"] = draft.zotero
        self._adopt_item_type(meta)
        self._adopt_title(meta)
        self._adopt_edition_year(meta)
        self._ensure_short_title(meta)
        self._adopt_recorded_creators(meta)

    def _normalize_shouted_names(self, meta: dict) -> None:
        for author in meta.get("authors") or []:
            author["lastName"] = vault.normalize_caps_name(author.get("lastName", ""))
            author["firstName"] = vault.normalize_caps_name(author.get("firstName", ""))

    def _adopt_item_type(self, meta: dict) -> None:
        item_type = meta["bib"].get("itemType")
        if item_type:
            meta["type"] = item_type

    def _adopt_title(self, meta: dict) -> None:
        title = meta["bib"].get("title")
        if title:
            meta["title"] = title

    def _adopt_edition_year(self, meta: dict) -> None:
        year = self._year_in(meta["bib"].get("date"))
        if year:
            meta["year"] = year

    def _year_in(self, date: object) -> str | None:
        match = _ANY_YEAR.search(str(date)) if date else None
        return match.group(0) if match else None

    def _ensure_short_title(self, meta: dict) -> None:
        if meta["bib"].get("shortTitle"):
            return
        short = vault.strip_subtitle(meta.get("title") or "")
        if short:
            meta["bib"]["shortTitle"] = short

    def _adopt_recorded_creators(self, meta: dict) -> None:
        creators = meta["bib"].get(_CREATORS_FIELD) or []
        for role in zotero.CREATOR_FALLBACK_ORDER:
            named = self._named_creators(creators, role)
            if named:
                meta["authors"] = named
                meta["authors_complete"] = True
                return

    def _named_creators(self, creators: list[dict], role: str) -> list[dict]:
        return [{"firstName": creator.get("firstName", ""), "lastName": self._surname(creator)}
                for creator in creators
                if creator.get("creatorType", "author") == role and self._surname(creator)]

    @staticmethod
    def _surname(creator: dict) -> str:
        return creator.get("lastName") or creator.get(_SINGLE_FIELD_NAME) or ""


class BibReport:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def render(self) -> dict:
        draft = DraftCard(self._pdf_path.name).load()
        bib = draft.zotero
        return {
            "file": self._pdf_path.name,
            "orig_year": draft.orig_year,
            "aliases": draft.aliases,
            "zotero": bib,
            "filed": draft.filed,
            "identified": draft.identified,
            "missing_for_type": RequiredFields().missing(self._item_type(bib), bib),
        }

    def _item_type(self, bib: dict) -> str:
        return bib.get("itemType") or PdfProbe().of(self._pdf_path)["type"]


class Assignment:
    def __init__(self, text: str) -> None:
        if "=" not in text:
            raise SystemExit(f"--set expects field=value, got: {text}")
        field, value = (part.strip() for part in text.split("=", 1))
        self._field = field
        self._value = value

    def apply_to(self, draft: DraftCard) -> None:
        if self._field == _ORIG_YEAR_FIELD:
            draft.set_orig_year(self._value)
        elif self._field == _ALIASES_FIELD:
            draft.set_aliases([self._value] if self._value else [])
        else:
            draft.set_zotero_field(self._field, self._zotero_value())

    def _zotero_value(self) -> object:
        if self._field == _CREATORS_FIELD and self._value:
            return self._parsed_creators()
        return self._value

    def _parsed_creators(self) -> list:
        try:
            return json.loads(self._value)
        except json.JSONDecodeError as error:
            raise SystemExit(f"--set creators expects a JSON array: {error}") from error


class BibEditor:
    def __init__(self, pdf_path: Path) -> None:
        self._pdf_path = pdf_path

    def apply(self, assignments: list[str]) -> dict:
        return self.edit(lambda draft: self._assign(draft, assignments))

    def edit(self, change) -> dict:
        draft = DraftCard(self._pdf_path.name).load()
        self._refuse_if_filed(draft)
        change(draft)
        self._save(draft)
        return {"file": self._pdf_path.name, "draft": draft.fields}

    def _assign(self, draft: DraftCard, assignments: list[str]) -> None:
        for text in assignments:
            Assignment(text).apply_to(draft)

    def _refuse_if_filed(self, draft: DraftCard) -> None:
        if draft.filed:
            raise SystemExit(_ITEM_EXISTS.format(name=self._pdf_path.name))

    def _save(self, draft: DraftCard) -> None:
        meta = PdfProbe().of(self._pdf_path)
        MetadataMerge().into(meta, draft)
        citekey = CitekeyAllocator().for_meta(meta, exclude_stem=self._pdf_path.stem)
        draft.adopt(meta, citekey)
        draft.save()
