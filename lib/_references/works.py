from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


import vault

_UNIDENTIFYING_TITLE_WORDS = {
    "a", "an", "and", "the", "of", "on", "in", "to", "for", "from", "with", "its",
    "as", "at", "by", "is", "it", "or", "that", "this", "über", "und", "der", "die",
    "das", "des", "dem", "den", "zur", "zum", "eine", "einer",
}

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

MIN_TITLE_TOKEN_CHARS = 4

_PUNCTUATION_RE = re.compile(r"[^\w\s]+", re.UNICODE)

_WHITESPACE_RE = re.compile(r"\s+")

def normalize_phrase(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", _PUNCTUATION_RE.sub(" ", text.lower())).strip()


def surname_token(surname: str) -> str:
    words = normalize_phrase(surname).split()
    return words[-1] if words else ""


MIN_TITLE_PHRASE_CHARS = 3


@dataclass(frozen=True)
class LibraryWork:
    basename: str
    surnames: tuple[str, ...]
    years: tuple[str, ...]
    title_tokens: frozenset[str]
    titles: tuple[str, ...] = ()

    @property
    def surname_tokens(self) -> frozenset[str]:
        tokens = (surname_token(surname) for surname in self.surnames)
        return frozenset(token for token in tokens if token)

    @property
    def cited_year(self) -> int | None:
        return int(self.years[0]) if self.years and self.years[0].isdigit() else None


class WorkFactory:
    def of(self, note_path: Path) -> LibraryWork:
        return self._built(vault.basename_of(note_path), vault.read_frontmatter_only(note_path))

    def of_pdf(self, pdf_path: Path) -> LibraryWork:
        return self._built(vault.basename_of(pdf_path), {})

    def _built(self, basename: str, meta: dict) -> LibraryWork:
        parsed = vault.parse_library_filename(f"{basename}.pdf") or {}
        titles = self._titles(meta, parsed)
        return LibraryWork(basename,
                           self._surnames(meta, parsed),
                           self._years(meta, parsed),
                           self._title_tokens(titles),
                           self._title_phrases(titles))

    def _title_phrases(self, titles: list[str | None]) -> tuple[str, ...]:
        phrases = (normalize_phrase(vault.strip_subtitle(str(title))) for title in titles if title)
        return tuple(dict.fromkeys(phrase for phrase in phrases if len(phrase) >= MIN_TITLE_PHRASE_CHARS))

    def _titles(self, meta: dict, parsed: dict) -> list[str | None]:
        return [meta.get("title"), *self.listed(meta.get("aliases")), parsed.get("title")]

    def _surnames(self, meta: dict, parsed: dict) -> tuple[str, ...]:
        recorded = [str(name) for name in self.listed(meta.get("author")) if name]
        names = recorded or self._from_creator(parsed)
        return tuple(dict.fromkeys(name.lower() for name in names))

    @staticmethod
    def listed(value: str | list | None) -> list:
        if not value:
            return []
        return [value] if isinstance(value, str) else list(value)

    def _from_creator(self, parsed: dict) -> list[str]:
        return vault.creator_surnames(parsed.get("creator", ""))

    def _years(self, meta: dict, parsed: dict) -> tuple[str, ...]:
        candidates = [meta.get("orig_year"), meta.get("year"), parsed.get("year")]
        return tuple(dict.fromkeys(str(year) for year in candidates if year))

    def _title_tokens(self, titles: list[str | None]) -> frozenset[str]:
        tokens = set()
        for title in titles:
            tokens.update(self.tokens_of(str(title or "")))
        return frozenset(tokens)

    @staticmethod
    def tokens_of(text: str) -> set[str]:
        words = (word.lower() for word in _WORD_RE.findall(text))
        return {word for word in words
                if len(word) >= MIN_TITLE_TOKEN_CHARS and word not in _UNIDENTIFYING_TITLE_WORDS}


class HeldWorks:
    def __init__(self, works: list[LibraryWork]) -> None:
        self._works = works

    @classmethod
    def from_corpus(cls) -> HeldWorks:
        factory = WorkFactory()
        return cls([factory.of(note) for note in vault.list_corpus_files()])

    @classmethod
    def from_library(cls) -> HeldWorks:
        return cls([cls._work_of(pdf) for pdf in vault.list_pdfs(vault.LIBRARY_DIR)])

    @staticmethod
    def _work_of(pdf: Path) -> LibraryWork:
        factory = WorkFactory()
        note = vault.corpus_path(vault.basename_of(pdf))
        return factory.of(note) if note.exists() else factory.of_pdf(pdf)

    @property
    def works(self) -> list[LibraryWork]:
        return list(self._works)

    def find(self, basename: str) -> LibraryWork | None:
        wanted = vault.nfc(basename)
        return next((work for work in self._works if work.basename == wanted), None)
