from __future__ import annotations

import re

from rapidfuzz import fuzz

import vault
from _references.works import normalize_phrase

IDENTICAL = 100.0
UNRELATED = 0.0

_LEADING_ARTICLES = frozenset({"the", "a", "an", "der", "die", "das", "le", "la", "les", "il", "el"})
_INVISIBLE_SPACES_RE = re.compile(r"[\s\u00a0\u200b]+")


class TitleTokens:
    def __init__(self, title: str) -> None:
        self._words = self._without_leading_article(self._main_title_words(title))

    @property
    def words(self) -> list[str]:
        return list(self._words)

    def is_extension_of(self, other: TitleTokens) -> bool:
        return bool(other._words) and self._words[:len(other._words)] == other._words

    def similarity_to(self, other: TitleTokens) -> float:
        if not self._words or not other._words:
            return UNRELATED
        if self.is_extension_of(other):
            return IDENTICAL
        return float(fuzz.token_sort_ratio(" ".join(self._words), " ".join(other._words)))

    @staticmethod
    def _main_title_words(title: str) -> list[str]:
        spaced = _INVISIBLE_SPACES_RE.sub(" ", title or "")
        return normalize_phrase(vault.strip_subtitle(spaced)).split()

    @staticmethod
    def _without_leading_article(words: list[str]) -> list[str]:
        if len(words) > 1 and words[0] in _LEADING_ARTICLES:
            return words[1:]
        return words


class HeldTitles:
    def __init__(self, titles: tuple[str, ...]) -> None:
        tokens = [TitleTokens(title) for title in titles]
        self._held = tuple(held for held in tokens if not self._shortened(held, tokens))

    @staticmethod
    def _shortened(held: TitleTokens, tokens: list[TitleTokens]) -> bool:
        return any(len(other.words) > len(held.words) and other.is_extension_of(held) for other in tokens)

    def best_for(self, cited: str) -> float:
        cited_tokens = TitleTokens(cited)
        return max((cited_tokens.similarity_to(held) for held in self._held), default=UNRELATED)
