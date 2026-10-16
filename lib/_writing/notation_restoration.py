from __future__ import annotations

import re
from difflib import SequenceMatcher

from confusables import compatible
from notation import DELIMITED_SPAN_RE
from pagetext import typographic_form

QUOTED_TOKEN_RE = re.compile(f"{DELIMITED_SPAN_RE.pattern}|\\S+")
EQUAL = "equal"


class QuotationWording:
    def __init__(self, quotation: str, page_text: str, notation: tuple[str, ...]) -> None:
        self._quotation = quotation.strip()
        self._restoration = NotationRestoration(quotation, page_text, notation)
        self._agrees = typographic_form(self._restoration.quoted_prose()) == typographic_form(page_text)

    def written(self) -> str:
        return self._quotation if self._agrees else self._restoration.restored()


class NotationRestoration:
    def __init__(self, quotation: str, page_text: str, notation: tuple[str, ...]) -> None:
        characters = {item for item in notation if len(item) == 1}
        self._quoted = [QuotedToken(token, characters) for token in QUOTED_TOKEN_RE.findall(quotation)]
        self._prose = [token for token in self._quoted if not token.is_notation]
        self._page_text = page_text
        self._page = page_text.split()

    def restored(self) -> str:
        if not any(token.is_notation or token.carries_notation for token in self._quoted):
            return self._page_text
        leading = self._notation_leading_each_prose_token()
        written: list[str] = []
        for opcode in self._opcodes():
            written.extend(self._block(opcode, leading))
        written.extend(leading[len(self._prose)])
        return " ".join(written)

    def quoted_prose(self) -> str:
        return " ".join(token.prose for token in self._prose)

    def _notation_leading_each_prose_token(self) -> list[list[str]]:
        leading: list[list[str]] = [[]]
        for token in self._quoted:
            if token.is_notation:
                leading[-1].append(token.text)
            else:
                leading.append([])
        return leading

    def _opcodes(self) -> list[tuple[str, int, int, int, int]]:
        quoted = [token.prose_key for token in self._prose]
        page = [compatible(word) for word in self._page]
        return SequenceMatcher(a=quoted, b=page, autojunk=False).get_opcodes()

    def _block(self, opcode: tuple[str, int, int, int, int], leading: list[list[str]]) -> list[str]:
        tag, quoted_start, quoted_end, page_start, page_end = opcode
        words = self._page[page_start:page_end]
        if tag == EQUAL:
            return [part for offset, word in enumerate(words)
                    for part in (*leading[quoted_start + offset], self._prose[quoted_start + offset].restored(word))]
        return [*(text for notation in leading[quoted_start:quoted_end] for text in notation), *words]


class QuotedToken:
    def __init__(self, text: str, notation_characters: set[str]) -> None:
        self.text = text
        self._prose = "".join(char for char in text if char not in notation_characters)
        self._is_span = DELIMITED_SPAN_RE.fullmatch(text) is not None

    @property
    def is_notation(self) -> bool:
        return self._is_span or not self._prose

    @property
    def carries_notation(self) -> bool:
        return self._prose != self.text

    @property
    def prose(self) -> str:
        return self._prose

    @property
    def prose_key(self) -> str:
        return compatible(self._prose)

    def restored(self, page_word: str) -> str:
        return self.text if self.carries_notation and compatible(page_word) == self.prose_key else page_word
