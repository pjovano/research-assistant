from __future__ import annotations

import re

from .glyphs import CODE_KEY_PREFIX, KEY_SEPARATOR, UNICODE_FIELD

LEGACY_GLYPH_RE = re.compile(r"^(?:[0-9A-F]{2}){1,2}$")


class LegacyKey:
    def __init__(self, key: str) -> None:
        self._key = key
        self._family, _, self._glyph = key.rpartition(KEY_SEPARATOR)

    @property
    def key(self) -> str:
        return self._key

    @property
    def code_key(self) -> str:
        return f"{self._family}{KEY_SEPARATOR}{CODE_KEY_PREFIX}{self._glyph}"

    def is_legacy(self) -> bool:
        return LEGACY_GLYPH_RE.match(self._glyph) is not None

    def is_certainly_a_code(self) -> bool:
        return self._glyph[0].isdigit()

    def move(self) -> dict:
        return {"from": self._key, "to": self.code_key}


class LegacyCodeKeys:
    def __init__(self, entries: dict) -> None:
        self._entries = entries
        self._legacy = [LegacyKey(key) for key in entries if LegacyKey(key).is_legacy()]

    def plan(self) -> dict:
        return {"rewrites": [key.move() for key in self._rewrites()],
                "duplicates": [key.move() for key in self._duplicates()],
                "conflicts": [self._conflict_row(key) for key in self._conflicts()],
                "ambiguous": [self._ambiguous_row(key) for key in self._ambiguous()]}

    def migrated(self) -> dict:
        moved = self._rewrites()
        dropped = {key.key for key in moved + self._duplicates()}
        kept = {key: entry for key, entry in self._entries.items() if key not in dropped}
        return {**kept, **{key.code_key: self._entries[key.key] for key in moved}}

    def _rewrites(self) -> list[LegacyKey]:
        return [key for key in self._codes() if key.code_key not in self._entries]

    def _duplicates(self) -> list[LegacyKey]:
        return [key for key in self._codes() if self._held_character(key) == self._legacy_character(key)]

    def _conflicts(self) -> list[LegacyKey]:
        return [key for key in self._codes() if self._held_character(key) not in (None, self._legacy_character(key))]

    def _codes(self) -> list[LegacyKey]:
        return [key for key in self._legacy if key.is_certainly_a_code()]

    def _ambiguous(self) -> list[LegacyKey]:
        return [key for key in self._legacy if not key.is_certainly_a_code()]

    def _held_character(self, key: LegacyKey) -> str | None:
        held = self._entries.get(key.code_key)
        return held[UNICODE_FIELD] if held is not None else None

    def _legacy_character(self, key: LegacyKey) -> str:
        return self._entries[key.key][UNICODE_FIELD]

    def _conflict_row(self, key: LegacyKey) -> dict:
        return {**key.move(), "legacy": self._entries[key.key], "held": self._entries[key.code_key]}

    def _ambiguous_row(self, key: LegacyKey) -> dict:
        return {"key": key.key, "entry": self._entries[key.key], "as_code": key.code_key}
