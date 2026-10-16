from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import vault

from .cmap import HEX_RADIX
from .textkey import ENCODING

IDENTITIES_PATH = vault.LIBRARY_DIR / "glyph-identities.json"
TABLE_TEMPORARY_SUFFIX = ".json.partial"
DINGBATS = range(0x2700, 0x27C0)
PRIVATE_USE = range(0xE000, 0xF900)
SURROGATES = range(0xD800, 0xE000)
REPLACEMENT_CHARACTER = "\ufffd"
CONTROL_CATEGORY = "Cc"
EMPTY_LABEL = "(empty)"
UNICODE_LABEL_PREFIX = "U+"
METHOD_GLYPH_NAME = "glyph-name"
METHOD_TABLE = "table"
METHOD_WORKER = "worker"
METHOD_USER = "user"
LEARN_METHODS = (METHOD_WORKER, METHOD_USER)
KEY_SEPARATOR = "|"
CODE_KEY_PREFIX = "#"
UNICODE_FIELD = "unicode"
METHOD_FIELD = "method"
MARK_OPEN = "⟨"
MARK_CLOSE = "⟩"
UNI_GROUP_DIGITS = 4
LIGATURES = {
    "f_i": "fi", "fi": "fi", "f_l": "fl", "fl": "fl", "f_f": "ff", "ff": "ff",
    "f_f_i": "ffi", "ffi": "ffi", "f_f_l": "ffl", "ffl": "ffl", "f_t": "ft", "T_h": "Th", "s_t": "st",
}
FIGURES = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
}
SMALL_CAPITAL_RE = re.compile(r"^([A-Za-z]{1,3})\.(?:sc|smcp)$")
SMALL_SUFFIX_RE = re.compile(r"^([A-Z]{1,2})small$")
FIGURE_RE = re.compile(
    r"^(zero|one|two|three|four|five|six|seven|eight|nine)(?:oldstyle|\.oldstyle|\.onum|\.lf|\.fitted)$")
UNI_RE = re.compile(r"^uni((?:[0-9A-Fa-f]{4})+)$")
U_RE = re.compile(r"^u([0-9A-Fa-f]{4,6})$")
HEX_CODE_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}){1,2}$")


def is_suspect(char: str) -> bool:
    if char == "" or char == REPLACEMENT_CHARACTER or unicodedata.category(char) == CONTROL_CATEGORY:
        return True
    return ord(char) in DINGBATS or ord(char) in PRIVATE_USE


def is_ordinary(text: str) -> bool:
    return all(not is_suspect(char) and ord(char) not in SURROGATES for char in text)


def unicode_label(char: str) -> str:
    return EMPTY_LABEL if char == "" else f"{UNICODE_LABEL_PREFIX}{ord(char):04X}"


def char_of_label(label: str) -> str:
    return "" if label == EMPTY_LABEL else chr(int(label.removeprefix(UNICODE_LABEL_PREFIX), HEX_RADIX))


def marked(char: str) -> str:
    return f"{MARK_OPEN}{unicode_label(char)}{MARK_CLOSE}"


def normalize_glyph(glyph: str) -> str:
    return glyph.upper() if HEX_CODE_RE.match(glyph) else glyph


def glyph_code(text: str) -> str:
    if not HEX_CODE_RE.match(text):
        raise ValueError(f"{text!r} is not a glyph code of two or four hex digits")
    return text.upper()


def name_key(family: str, glyph_name: str) -> str:
    return _key(family, glyph_name)


def code_key(family: str, code: str) -> str:
    return _key(family, f"{CODE_KEY_PREFIX}{code.upper()}")


def legacy_key(family: str, glyph: str) -> str:
    return _key(family, normalize_glyph(glyph))


def legacy_of_code_key(key: str) -> str | None:
    family, _, glyph = key.rpartition(KEY_SEPARATOR)
    return _key(family, glyph.removeprefix(CODE_KEY_PREFIX)) if glyph.startswith(CODE_KEY_PREFIX) else None


@dataclass(frozen=True)
class Identity:
    unicode: str
    method: str


@dataclass(frozen=True)
class GlyphQuery:
    family: str
    glyph_name: str | None
    code: str
    char: str | None = None


class GlyphName:
    def __init__(self, name: str) -> None:
        self._name = name

    def identity(self) -> str | None:
        for rule in self._rules():
            found = rule()
            if found is not None:
                return found
        return None

    def _rules(self) -> tuple:
        return self._ligature, self._small_capital, self._figure, self._uni, self._u

    def _ligature(self) -> str | None:
        return LIGATURES.get(self._name)

    def _small_capital(self) -> str | None:
        found = SMALL_CAPITAL_RE.match(self._name) or SMALL_SUFFIX_RE.match(self._name)
        return found.group(1).lower() if found else None

    def _figure(self) -> str | None:
        found = FIGURE_RE.match(self._name)
        return FIGURES[found.group(1)] if found else None

    def _uni(self) -> str | None:
        found = UNI_RE.match(self._name)
        return _ordinary_or_none(_grouped_code_points(found.group(1))) if found else None

    def _u(self) -> str | None:
        found = U_RE.match(self._name)
        return _ordinary_or_none(_code_point(found.group(1))) if found else None


def _code_point(hex_text: str) -> str | None:
    try:
        return chr(int(hex_text, HEX_RADIX))
    except ValueError:
        return None


def _grouped_code_points(hex_text: str) -> str | None:
    groups = [hex_text[start:start + UNI_GROUP_DIGITS] for start in range(0, len(hex_text), UNI_GROUP_DIGITS)]
    points = [_code_point(group) for group in groups]
    return None if None in points else "".join(points)


def _ordinary_or_none(text: str | None) -> str | None:
    return text if text and is_ordinary(text) else None


class IdentityTable:
    def __init__(self, path: Path = IDENTITIES_PATH) -> None:
        self._path = path
        self._entries: dict | None = None

    @property
    def path(self) -> Path:
        return self._path

    def lookup(self, query: GlyphQuery) -> Identity | None:
        entries = self.entries()
        for key in self._keys(query):
            if key in entries:
                return Identity(entries[key][UNICODE_FIELD], METHOD_TABLE)
        return None

    def entry_for(self, family: str, glyph_name: str, identity: Identity) -> tuple[str, dict]:
        return name_key(family, glyph_name), self._entry(identity)

    def entry_for_code(self, family: str, code: str, identity: Identity) -> tuple[str, dict]:
        return code_key(family, code), self._entry(identity)

    @staticmethod
    def _entry(identity: Identity) -> dict:
        return {UNICODE_FIELD: identity.unicode, METHOD_FIELD: identity.method}

    def existing(self, key: str) -> dict | None:
        entries = self.entries()
        if key in entries:
            return entries[key]
        return entries.get(legacy_of_code_key(key))

    def conflicting(self, key: str, entry: dict) -> dict | None:
        held = self.existing(key)
        return held if held is not None and held[UNICODE_FIELD] != entry[UNICODE_FIELD] else None

    def entries(self) -> dict:
        if self._entries is None:
            self._entries = self._load()
        return self._entries

    def write(self, key: str, entry: dict) -> None:
        self._entries = {**self._load(), key: entry}
        self._save()

    def rewrite(self, rewritten: Callable[[dict], dict]) -> None:
        self._entries = rewritten(self._load())
        self._save()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(self._entries, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
        with vault.ReplacementFile(self._path, TABLE_TEMPORARY_SUFFIX) as replacement:
            replacement.path.write_text(rendered, encoding=ENCODING, newline="\n")
            replacement.commit()

    def _keys(self, query: GlyphQuery) -> list[str]:
        charwise = [_key(query.family, unicode_label(query.char))] if query.char else []
        return self._glyph_keys(query) + charwise

    @staticmethod
    def _glyph_keys(query: GlyphQuery) -> list[str]:
        if query.glyph_name:
            return [name_key(query.family, query.glyph_name), legacy_key(query.family, query.glyph_name)]
        return [code_key(query.family, query.code), legacy_key(query.family, query.code.upper())]

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding=ENCODING))
        except json.JSONDecodeError as failure:
            raise SystemExit(f"The identity table {self._path} is not valid JSON: {failure}") from failure


def _key(family: str, glyph: str) -> str:
    return f"{family}{KEY_SEPARATOR}{glyph}"


class IdentityResolver:
    def __init__(self, table: IdentityTable) -> None:
        self._table = table

    def resolve(self, query: GlyphQuery) -> Identity | None:
        named = GlyphName(query.glyph_name).identity() if query.glyph_name else None
        if named is not None:
            return Identity(named, METHOD_GLYPH_NAME)
        return self._table.lookup(query)
