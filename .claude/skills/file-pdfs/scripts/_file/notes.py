from __future__ import annotations

from pathlib import Path

import vault
import yaml
from zotero import EMPTY_FIELD_VALUES

from _file.paths import NotePaths

UNCITABLE_TOKEN = vault.UNCITABLE_TOKEN
UNCITABLE_FIELD = vault.UNCITABLE_FIELD
AMENDED_NAME_LABEL = "Amended name:"
AMENDED_NAME_FIELD = "amended_name"
ALIASES_FIELD = "aliases"
HAND_WRITTEN_FIELDS = ("source_type", "source_role", "commentary_on", "field", UNCITABLE_FIELD, ALIASES_FIELD)
IDENTIFIED_KEY = "identified"
ITEM_KEY_FIELD = "item_key"


class NoteFile:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._stored = vault.StoredNote(path)

    def read(self) -> tuple[dict, str]:
        try:
            return self._stored.read()
        except yaml.YAMLError as error:
            raise SystemExit(f"Unreadable frontmatter in {self._path}: {error}") from error

    def fields(self) -> dict:
        fields, _ = self.read()
        return fields

    def write(self, fields: dict, body: str) -> None:
        self._stored.write_guarded(fields, body)


class NoteFrontmatter:
    def __init__(self, meta: dict, citekey: str) -> None:
        self._meta = meta
        self._citekey = citekey

    def fields(self) -> dict:
        fields = {
            "title": self._meta.get("title", ""),
            "author": [author["lastName"] for author in self._meta.get("authors") or []],
            "year": self._as_year(self._meta.get("year")),
            "orig_year": self._as_year(self._meta.get("orig_year")),
            "type": self._meta.get("type"),
            "citekey": self._citekey,
            "source_type": None,
            "source_role": None,
            "field": [],
            ALIASES_FIELD: list(self._meta.get(ALIASES_FIELD) or []),
        }
        return {**fields, **self._fields_from_extra()}

    def preserving(self, previous: dict) -> dict:
        fields = self.fields()
        kept = {key: value for key, value in previous.items() if self._is_kept(key, value, fields)}
        return {**fields, **kept}

    def _is_kept(self, key: str, value: object, fields: dict) -> bool:
        if key not in fields:
            return True
        return key in HAND_WRITTEN_FIELDS and value not in EMPTY_FIELD_VALUES

    def _fields_from_extra(self) -> dict:
        extra = (self._meta.get("bib") or {}).get("extra")
        read = {UNCITABLE_FIELD: UncitableField().from_extra(extra),
                AMENDED_NAME_FIELD: AmendedNameField().from_extra(extra)}
        return {field: value for field, value in read.items() if value is not None}

    def _as_year(self, value: object) -> int | str | None:
        text = str(value or "").strip()
        if not text:
            return None
        return int(text) if text.isdigit() else text


class UncitableField:
    def from_extra(self, extra: object) -> str | bool | None:
        lines = str(extra or "").lstrip().splitlines()
        if not lines or not lines[0].startswith(UNCITABLE_TOKEN):
            return None
        return self._detail(lines) or True

    def _detail(self, lines: list[str]) -> str:
        return lines[1].strip() if len(lines) > 1 else ""


class AmendedNameField:
    def from_extra(self, extra: object) -> str | None:
        reasons = [self._reason(line) for line in str(extra or "").splitlines() if self._is_labelled(line)]
        return next((reason for reason in reasons if reason), None)

    def _is_labelled(self, line: str) -> bool:
        return line.strip().startswith(AMENDED_NAME_LABEL)

    def _reason(self, line: str) -> str:
        return line.strip()[len(AMENDED_NAME_LABEL):].strip()


class DraftCard:
    def __init__(self, pdf_name: str) -> None:
        self._pdf_name = pdf_name
        self._path = NotePaths().draft(pdf_name)
        self._file = NoteFile(self._path)
        self._fields: dict = {}

    @classmethod
    def at(cls, path: Path) -> "DraftCard":
        return cls(NotePaths().pdf_name_of(path))

    @property
    def pdf_name(self) -> str:
        return self._pdf_name

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.exists()

    def load(self) -> "DraftCard":
        if self._path.exists():
            self._fields = self._file.fields()
        else:
            self._fields = self._seed_from_note()
        return self

    def _seed_from_note(self) -> dict:
        note = CorpusNote(self._pdf_name)
        if not note.exists():
            return {}
        seed = note.fields()
        return {key: seed.get(key) for key in ("orig_year", "aliases")}

    @property
    def fields(self) -> dict:
        return dict(self._fields)

    @property
    def zotero(self) -> dict:
        return dict(self._fields.get("zotero") or {})

    @property
    def orig_year(self) -> str | None:
        value = self._fields.get("orig_year")
        return str(value) if value else None

    @property
    def aliases(self) -> list[str]:
        return list(self._fields.get("aliases") or [])

    @property
    def citekey(self) -> str | None:
        return self._fields.get("citekey") or None

    @property
    def item_type(self) -> str:
        return self.zotero.get("itemType") or self._fields.get("type") or ""

    @property
    def filed(self) -> bool:
        return bool(self._fields.get("filed"))

    @property
    def identified(self) -> dict | None:
        return self._fields.get(IDENTIFIED_KEY) or None

    @property
    def item_key(self) -> str | None:
        return self._fields.get(ITEM_KEY_FIELD) or None

    def set_item_key(self, item_key: str | None) -> None:
        if item_key:
            self._fields[ITEM_KEY_FIELD] = item_key

    def set_identified(self, provenance: dict) -> None:
        self._fields[IDENTIFIED_KEY] = provenance

    def set_orig_year(self, value: str | None) -> None:
        self._fields["orig_year"] = value or None

    def set_aliases(self, aliases: list[str]) -> None:
        self._fields["aliases"] = aliases

    def set_zotero_field(self, field: str, value: object) -> None:
        zotero = self.zotero
        if value in EMPTY_FIELD_VALUES:
            zotero.pop(field, None)
        else:
            zotero[field] = value
        self._fields["zotero"] = zotero

    def mark_filed(self) -> None:
        self._fields["filed"] = True

    def adopt(self, meta: dict, citekey: str) -> None:
        fields = NoteFrontmatter(meta, citekey).fields()
        fields["zotero"] = self.zotero
        fields["filed"] = self.filed
        if self.identified:
            fields[IDENTIFIED_KEY] = self.identified
        if self.item_key:
            fields[ITEM_KEY_FIELD] = self.item_key
        self._fields = fields

    def save(self) -> None:
        NotePaths().ensure_dirs()
        self._file.write(self._fields, "")

    def delete(self) -> None:
        self._path.unlink(missing_ok=True)


class CorpusNote:
    def __init__(self, pdf_name: str) -> None:
        self._pdf_name = pdf_name
        self._path = NotePaths().note(pdf_name)
        self._file = NoteFile(self._path)

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.exists()

    def fields(self) -> dict:
        return self._file.fields()

    @property
    def pdf_name(self) -> str:
        return self._pdf_name

    def body(self) -> str:
        _, body = self._file.read()
        return body

    def link(self) -> str | None:
        return vault.pdf_link_of(self.body())

    def write(self, fields: dict, link: str, body: str) -> None:
        NotePaths().ensure_dirs()
        self._file.write(fields, self._linked(body, link))

    def relink(self, link: str) -> None:
        fields, body = self._file.read()
        self._file.write(fields, self._linked(body, link))

    def _linked(self, body: str, link: str) -> str:
        return vault.upsert_pdf_link(body, Path(self._pdf_name).stem, link)

    def delete(self) -> None:
        self._path.unlink(missing_ok=True)
