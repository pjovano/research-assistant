from __future__ import annotations

import re
from dataclasses import dataclass

ENGLISH = "en"
GERMAN = "de"
FRENCH = "fr"
ITALIAN = "it"
LATIN = "la"

_LANGUAGE_MARKER_WORDS = {
    ENGLISH: {"the", "of", "and", "in", "on", "a", "an", "to", "for", "with", "from", "by", "is", "its"},
    GERMAN: {"der", "die", "das", "und", "des", "dem", "den", "von", "zur", "zum", "im", "ein", "eine",
             "über", "für", "mit", "als", "zu", "einer", "eines", "oder"},
    FRENCH: {"le", "la", "les", "des", "du", "de", "et", "un", "une", "dans", "sur", "pour", "au", "aux",
             "à", "en", "ou", "chez"},
    ITALIAN: {"il", "lo", "la", "gli", "le", "dei", "delle", "degli", "del", "della", "e", "ed", "di",
              "un", "una", "nel", "nella", "per", "con", "sul", "sulla"},
    LATIN: {"de", "et", "in", "ad", "cum", "ex", "sive", "seu", "contra", "liber", "libri", "quaestio",
            "quaestiones", "summa", "ac", "atque", "est", "super", "commentaria", "commentarium"},
}

_ENGLISH_SMALL_WORDS = {
    "a", "an", "the", "and", "but", "or", "nor", "for", "so", "yet", "of", "on", "in", "at", "to", "by",
    "with", "from", "as", "into", "onto", "upon", "over", "via", "vs", "per", "than", "if", "up", "out", "off",
}

ROMAN_NUMERAL = re.compile(r"^[IVXLCDM]+$")
_WORD_BOUNDARY = re.compile(r"(\s+)")
_SUBWORD_BOUNDARY = re.compile(r"([-/])")
_LEADING_PUNCTUATION = re.compile(r"^[^\w]*")
_CAPITALIZE_AFTER = ":"


@dataclass(frozen=True)
class CasedTitle:
    text: str
    language: str | None
    changed: bool

    @property
    def language_unknown(self) -> bool:
        return self.language is None


def detect_language(title: str) -> str | None:
    words = {_bare(word).lower() for word in title.split()}
    scores = {language: len(words & stopwords) for language, stopwords in _LANGUAGE_MARKER_WORDS.items()}
    best = max(scores.values())
    leaders = [language for language, score in scores.items() if score == best]
    return leaders[0] if best and len(leaders) == 1 else None


def is_shouted(title: str) -> bool:
    letters = [character for character in title if character.isalpha()]
    return bool(letters) and all(character.isupper() for character in letters)


def title_case(title: str) -> CasedTitle:
    language = detect_language(title)
    if language in (None, ENGLISH):
        cased = _EnglishTitle(title).cased()
    else:
        cased = _other_language_case(title)
    return CasedTitle(cased, language, cased != title)


class _EnglishTitle:
    def __init__(self, title: str) -> None:
        self._words = _WORD_BOUNDARY.split(title)
        self._shouted = is_shouted(title)
        self._positions = [index for index, word in enumerate(self._words) if word and not word.isspace()]

    def cased(self) -> str:
        cased = list(self._words)
        for ordinal, index in enumerate(self._positions):
            cased[index] = self._cased_word(ordinal)
        return "".join(cased)

    def _cased_word(self, ordinal: int) -> str:
        word = self._words[self._positions[ordinal]]
        if self._is_edge(ordinal):
            return self._capitalized_word(word)
        return self._inner_word(word)

    def _is_edge(self, ordinal: int) -> bool:
        previous = self._words[self._positions[ordinal - 1]] if ordinal else ""
        return ordinal in (0, len(self._positions) - 1) or previous.endswith(_CAPITALIZE_AFTER)

    def _inner_word(self, word: str) -> str:
        if _bare(word).lower() in _ENGLISH_SMALL_WORDS and not self._keeps_its_case(word):
            return word.lower()
        return self._capitalized_word(word)

    def _capitalized_word(self, word: str) -> str:
        if self._keeps_its_case(word):
            return word
        if _bare(word)[:1].isdigit():
            return word.lower()
        return "".join(_capitalized(part) for part in _SUBWORD_BOUNDARY.split(word))

    def _keeps_its_case(self, word: str) -> bool:
        bare = _bare(word)
        if ROMAN_NUMERAL.match(bare):
            return True
        return not self._shouted and not bare.islower()


def _other_language_case(title: str) -> str:
    if is_shouted(title):
        return _sentence_case(title)
    return _first_letter_upper(title)


def _sentence_case(title: str) -> str:
    words = _WORD_BOUNDARY.split(title)
    return _first_letter_upper("".join(_lowered_unless_numeral(word) for word in words))


def _lowered_unless_numeral(word: str) -> str:
    return word if ROMAN_NUMERAL.match(_bare(word)) else word.lower()


def _first_letter_upper(text: str) -> str:
    lead = _LEADING_PUNCTUATION.match(text).end()
    return text[:lead] + text[lead:lead + 1].upper() + text[lead + 1:]


def _capitalized(part: str) -> str:
    return _first_letter_upper(part.lower())


def _bare(word: str) -> str:
    return word.strip(".,:;!?'\"()[]")
