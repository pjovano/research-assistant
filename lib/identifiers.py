from __future__ import annotations

import re
from dataclasses import dataclass

DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s\"<>]+")
ISBN_PATTERN = re.compile(r"(?<![\d-])(?:97[89][-\s]?)?(?:\d[-\s]?){9}[\dXx](?![\d-])")
ARXIV_NEW_PATTERN = re.compile(r"(?<![\d.])\d{2}(?:0[1-9]|1[0-2])\.\d{4,5}(?:v\d+)?(?![\d.])")
ARXIV_OLD_PATTERN = re.compile(
    r"\b(?:astro-ph|cond-mat|cs|econ|eess|gr-qc|hep-ex|hep-lat|hep-ph|hep-th|math|math-ph|nlin|"
    r"nucl-ex|nucl-th|physics|q-bio|q-fin|quant-ph|stat)(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?\b")

KIND_DOI = "doi"
KIND_ISBN = "isbn"
KIND_ARXIV = "arxiv"

_DOI_URL_PREFIX = re.compile(r"^(?:https?://)?(?:dx\.)?doi\.org/", re.IGNORECASE)
_DOI_TRAILING_PUNCTUATION = ".,;:'\""
_CLOSERS = {")": "(", "]": "[", "}": "{"}
_ISBN_SEPARATORS = re.compile(r"[-\s]")
_ISBN_LABEL_BEFORE = re.compile(r"isbn[^0-9A-Za-z]{0,10}$", re.IGNORECASE)
_ISBN10_LENGTH = 10
_ISBN13_LENGTH = 13
_ISBN13_BOOKLAND_PREFIX = "978"
_ISBN10_CHECK_MODULUS = 11
_ISBN13_CHECK_MODULUS = 10
_ISBN13_ODD_WEIGHT = 3


@dataclass(frozen=True)
class Identifier:
    kind: str
    value: str


def clean_doi(text: str) -> str:
    doi = _DOI_URL_PREFIX.sub("", text.strip()).rstrip(_DOI_TRAILING_PUNCTUATION)
    while _ends_with_unbalanced_closer(doi):
        doi = doi[:-1].rstrip(_DOI_TRAILING_PUNCTUATION)
    return doi.lower()


def _ends_with_unbalanced_closer(doi: str) -> bool:
    if not doi or doi[-1] not in _CLOSERS:
        return False
    closer = doi[-1]
    return doi.count(_CLOSERS[closer]) < doi.count(closer)


def find_dois(text: str) -> list[str]:
    return _distinct(clean_doi(match.group(0)) for match in DOI_PATTERN.finditer(text))


def find_isbns(text: str) -> list[str]:
    printed = (match for match in ISBN_PATTERN.finditer(text) if _is_printed_as_an_isbn(text, match))
    return _distinct(isbn for isbn in (canonical_isbn(match.group(0)) for match in printed) if isbn)


def _is_printed_as_an_isbn(text: str, match: re.Match) -> bool:
    digits = _ISBN_SEPARATORS.sub("", match.group(0))
    return len(digits) == _ISBN13_LENGTH or bool(_ISBN_LABEL_BEFORE.search(text[:match.start()]))


def find_arxiv_ids(text: str) -> list[str]:
    old = (match.group(0) for match in ARXIV_OLD_PATTERN.finditer(text))
    new = (match.group(0) for match in ARXIV_NEW_PATTERN.finditer(text))
    return _distinct(list(old) + list(new))


def canonical_isbn(text: str) -> str | None:
    digits = _ISBN_SEPARATORS.sub("", text).upper()
    if len(digits) == _ISBN10_LENGTH and _isbn10_checksum_holds(digits):
        return _isbn13_from_isbn10(digits)
    if len(digits) == _ISBN13_LENGTH and _isbn13_checksum_holds(digits):
        return digits
    return None


def _isbn10_checksum_holds(digits: str) -> bool:
    if not digits[:-1].isdigit() or not (digits[-1].isdigit() or digits[-1] == "X"):
        return False
    weighted = sum((_ISBN10_LENGTH - position) * _isbn_digit_value(digit)
                   for position, digit in enumerate(digits))
    return weighted % _ISBN10_CHECK_MODULUS == 0


def _isbn13_checksum_holds(digits: str) -> bool:
    if not digits.isdigit():
        return False
    return _isbn13_weighted_sum(digits) % _ISBN13_CHECK_MODULUS == 0


def _isbn13_from_isbn10(digits: str) -> str:
    body = _ISBN13_BOOKLAND_PREFIX + digits[:-1]
    check = (_ISBN13_CHECK_MODULUS - _isbn13_weighted_sum(body) % _ISBN13_CHECK_MODULUS) % _ISBN13_CHECK_MODULUS
    return body + str(check)


def _isbn13_weighted_sum(digits: str) -> int:
    return sum(int(digit) * (_ISBN13_ODD_WEIGHT if position % 2 else 1) for position, digit in enumerate(digits))


def _isbn_digit_value(digit: str) -> int:
    return _ISBN10_CHECK_MODULUS - 1 if digit == "X" else int(digit)


def _distinct(values) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen
