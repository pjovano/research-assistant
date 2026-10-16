from __future__ import annotations

import re
import unicodedata

FRAKTUR = "fraktur"
SCRIPT = "script"
DOUBLE_STRUCK = "double-struck"
COMMAND_ALPHABETS = {"mathfrak": FRAKTUR, "mathcal": SCRIPT, "mathscr": SCRIPT, "mathbb": DOUBLE_STRUCK}
ALPHABET_COMMANDS = {FRAKTUR: "\\mathfrak", SCRIPT: "\\mathcal", DOUBLE_STRUCK: "\\mathbb"}
_LETTER_FONTS = ((re.compile(r"EUF[MB]|Fraktur|yfrak", re.IGNORECASE), FRAKTUR),
                 (re.compile(r"EUS[MB]|RSFS|MathScript|Calligraphic", re.IGNORECASE), SCRIPT),
                 (re.compile(r"MSBM|DoubleStruck|bbold", re.IGNORECASE), DOUBLE_STRUCK))
_CAPITALS_FONT_RE = re.compile(r"CMB?SY\d", re.IGNORECASE)
_NAME_PREFIXES = {FRAKTUR: ("MATHEMATICAL FRAKTUR", "BLACK-LETTER"), SCRIPT: ("MATHEMATICAL SCRIPT", "SCRIPT"),
                  DOUBLE_STRUCK: ("MATHEMATICAL DOUBLE-STRUCK", "DOUBLE-STRUCK")}
_NAME_WORDS = {"FRAKTUR": FRAKTUR, "BLACK-LETTER": FRAKTUR, "SCRIPT": SCRIPT, "DOUBLE-STRUCK": DOUBLE_STRUCK}


def lettered(char: str, font: str) -> str:
    alphabet = _font_alphabet(char, font)
    if alphabet is None:
        return char
    case = "CAPITAL" if char.isupper() else "SMALL"
    for prefix in _NAME_PREFIXES[alphabet]:
        try:
            return unicodedata.lookup(f"{prefix} {case} {char.upper()}")
        except KeyError:
            continue
    return char


def alphabet_of(char: str) -> str | None:
    words = unicodedata.name(char, "").split()
    return next((_NAME_WORDS[word] for word in words if word in _NAME_WORDS), None)


def _font_alphabet(char: str, font: str) -> str | None:
    if not (char.isascii() and char.isalpha()):
        return None
    if _CAPITALS_FONT_RE.search(font) and char.isupper():
        return SCRIPT
    return next((alphabet for pattern, alphabet in _LETTER_FONTS if pattern.search(font)), None)
