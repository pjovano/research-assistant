from __future__ import annotations

import json

import vault
from _vault.frontmatter import FrontmatterFields

from .maps import wikilink
from .notes import CorpusNote, WritingNote

FIELD_KEY = "field"


class FieldRewrite:
    def __init__(self, note: CorpusNote | WritingNote) -> None:
        self._stored = vault.GuardedNote(note.path)
        self._current = list(note.bibliographies)

    def moved(self, sources: list[str], target: str) -> None:
        names = [name for name in self._current if name not in sources]
        if target not in names:
            names.append(target)
        block, body = vault.split_note(self._stored.text())
        fields = {FIELD_KEY: [json.dumps(wikilink(name), ensure_ascii=False) for name in names]}
        self._stored.replace(vault.join_note(FrontmatterFields().replaced_in_place(block, fields), body))
