from __future__ import annotations

import re

NOTE_NUMBER = r"\d{1,3}(?!\d)"
NOTE_SYMBOLS = "*†‡§¶"
NUMBER_CLOSE = r"[.)]?"
_NO_CITATION_CONTINUING = r"(?![a-z]|\s*(?:\.?\s*[–—-]\s*\d|[;,]))"

MARKDOWN_NOTE_OPENING_RE = re.compile(
    rf"^\s*(?P<emphasis>\*{{0,2}})(?:<sup>)?\s*(?P<bracket>\\?\[)?(?P<number>{NOTE_NUMBER})"
    rf"(?(bracket)\\?\]){_NO_CITATION_CONTINUING}\s*{NUMBER_CLOSE}\s*(?:</sup>)?\s*(?P=emphasis)\s*")
SIGN_OPENING_RE = re.compile(rf"^\s*({NOTE_NUMBER}|[{NOTE_SYMBOLS}]+)(?:\s+\S|\s*$)")
CORPUS_ENTRY_OPENING_RE = re.compile(rf"^(?:[-*]\s+)?({NOTE_NUMBER}){NUMBER_CLOSE}\s")
LAYER_LINE_OPENING_RE = re.compile(rf"^({NOTE_NUMBER}){NUMBER_CLOSE}\s")
