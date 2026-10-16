from __future__ import annotations

import re
import unicodedata

_CITEKEY_FOLD = str.maketrans({
    "ł": "l", "ø": "o", "đ": "d", "ð": "d", "þ": "th",
    "æ": "ae", "œ": "oe", "ß": "ss", "ı": "i", "ħ": "h", "ŋ": "n", "ĸ": "k",
})

_KEEPS_HYPHEN_DROPS_THE_REST = re.compile(r"[^a-z-]")

_UNDATED = "n.d."

_DISAMBIGUATION_LETTERS = "abcdefghijklmnopqrstuvwxyz"


def citekey(surname: str, year_for_key: str) -> str:
    return f"{_fold_to_ascii(surname)}{year_for_key}"


def _fold_to_ascii(surname: str) -> str:
    folded = surname.lower().translate(_CITEKEY_FOLD)
    unaccented = "".join(
        character for character in unicodedata.normalize("NFKD", folded)
        if not unicodedata.combining(character)
    )
    return _KEEPS_HYPHEN_DROPS_THE_REST.sub("", unaccented)


def citekey_year(meta: dict) -> str:
    for key in ("orig_year", "year"):
        value = meta.get(key)
        if value:
            return str(value)
    return _UNDATED


def unique_citekey(base_key: str, taken: set[str]) -> str:
    if base_key not in taken:
        return base_key
    return _first_free_suffix(base_key, taken)


def _first_free_suffix(base_key: str, taken: set[str]) -> str:
    for letter in _DISAMBIGUATION_LETTERS:
        candidate = f"{base_key}{letter}"
        if candidate not in taken:
            return candidate
    raise ValueError(f"more than 26 works share the citekey {base_key}")
