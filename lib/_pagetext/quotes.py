from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import vault
from notation import DELIMITED_SPAN_RE
from scratch_cache import ScratchCache

from _pagetext.normalize import NormalizedText, normalize
from _pagetext.pages import document_fingerprint, page_records

MIN_QUOTE_LENGTH_CHARS = 12
MAX_QUOTE_HITS = 5
DEFAULT_NEAR_MATCH_THRESHOLD = 0.85
SIMILARITY_PRECISION = 3
FUZZY_WINDOW_SLACK = 1.15
CONTEXT_PAD_CHARS = 120
LOCATE_CONTEXT_PAD_CHARS = 90
CACHE_NAME = "normalized.json"
CACHE_VERSION = 3
PAGE_JOIN = " "
ELLIPSIS = "..."


@dataclass
class QuoteHit:
    pdf_page: int
    printed_page: str | None
    similarity: float
    exact: bool
    context: str
    page_text: str
    spans_pages: tuple[int, int] | None = None


@dataclass(frozen=True)
class NormalizedWording:
    raw: str
    text: str

    @staticmethod
    def of(raw: str) -> "NormalizedWording":
        return NormalizedWording(raw, normalize(raw))


class NormalizedPage:
    spanned = None

    def __init__(self, number: int, wording: NormalizedWording, label: str | None) -> None:
        self.number = number
        self.raw = wording.raw
        self.text = wording.text
        self.label = label

    @staticmethod
    def normalized(number: int, raw: str, label: str | None) -> "NormalizedPage":
        return NormalizedPage(number, NormalizedWording.of(raw), label)

    def page_text(self, start: int, length: int) -> str:
        return NormalizedText(self.raw).page_text(start, length)


class _JoinedPages:
    def __init__(self, first: NormalizedPage, second: NormalizedPage) -> None:
        self._first = first
        self._second = second
        self._boundary = len(first.text) + len(PAGE_JOIN)

    @property
    def number(self) -> int:
        return self._first.number

    @property
    def label(self) -> str | None:
        return self._first.label

    @property
    def spanned(self) -> tuple[int, int]:
        return self._first.number, self._second.number

    @property
    def text(self) -> str:
        return self._first.text + PAGE_JOIN + self._second.text

    def page_text(self, start: int, length: int) -> str:
        head = self._first.page_text(start, len(self._first.text) - start)
        tail = self._second.page_text(0, start + length - self._boundary)
        return head + PAGE_JOIN + tail


@dataclass
class _Span:
    start: int
    length: int


@dataclass
class _Match:
    similarity: float
    exact: bool


def find_quote(pdf_path: Path, quote: str, *, threshold: float = DEFAULT_NEAR_MATCH_THRESHOLD) -> list[QuoteHit]:
    return _ranked(quote, threshold, normalized_pages(pdf_path))


def find_quote_in_texts(pdf_path: Path, quote: str, texts: list[tuple[int, str]], *,
                        threshold: float = DEFAULT_NEAR_MATCH_THRESHOLD) -> list[QuoteHit]:
    labels = {record.pdf_page: record.printed_page for record in page_records(pdf_path)}
    pages = [NormalizedPage.normalized(number, raw, labels.get(number)) for number, raw in texts]
    return _ranked(quote, threshold, pages)


def find_quote_around_notation(pdf_path: Path, quote: str) -> list[QuoteHit]:
    pages = normalized_pages(pdf_path)
    pairs = [_JoinedPages(first, second) for first, second in zip(pages, pages[1:])]
    finder = _ProseAroundNotation(quote)
    return (finder.hits(pages) or finder.hits(pairs))[:MAX_QUOTE_HITS]


class _ProseAroundNotation:
    def __init__(self, quote: str) -> None:
        self._quote = quote
        self._pattern = re.compile(r"\s*".join(self._parts()), re.DOTALL)

    def hits(self, searched: list) -> list[QuoteHit]:
        return [_hit(page, _Span(found.start(), found.end() - found.start()), _Match(1.0, exact=True))
                for page in searched if page.text for found in self._pattern.finditer(page.text)]

    def _parts(self) -> list[str]:
        parts, position = [], 0
        for span in DELIMITED_SPAN_RE.finditer(self._quote):
            parts += [self._prose(self._quote[position:span.start()]), self._set_on_the_page(span.group(0))]
            position = span.end()
        parts.append(self._prose(self._quote[position:]))
        _require_locatable_length("".join(part for part in parts[::2]))
        return [part for part in parts if part]

    @staticmethod
    def _prose(text: str) -> str:
        return re.escape(normalize(text))

    @staticmethod
    def _set_on_the_page(span: str) -> str:
        return f".{{0,{len(span)}}}?"


def normalized_pages(pdf_path: Path) -> list[NormalizedPage]:
    return _NORMALIZED_PAGES.of(pdf_path)


def _ranked(quote: str, threshold: float, pages: list[NormalizedPage]) -> list[QuoteHit]:
    needle = normalize(quote)
    _require_locatable_length(needle)
    hits = _QuoteFinder(needle, threshold, pages).hits(MAX_QUOTE_HITS)
    hits.sort(key=lambda h: h.similarity, reverse=True)
    return hits[:MAX_QUOTE_HITS]


def _require_locatable_length(needle: str) -> None:
    if len(needle) < MIN_QUOTE_LENGTH_CHARS:
        raise ValueError(f"quote too short to locate reliably (need at least {MIN_QUOTE_LENGTH_CHARS} characters)")


class _PageCache:
    def __init__(self, pdf_path: Path) -> None:
        self._file = ScratchCache(vault.SCRATCH_DIR / pdf_path.stem / CACHE_NAME)

    def loaded(self, key: list) -> list[NormalizedPage] | None:
        entry = self._file.entry()
        if entry is None or entry.get("key") != key:
            return None
        return [NormalizedPage(number, NormalizedWording(raw, text), label)
                for number, raw, text, label in entry["pages"]]

    def save(self, key: list, pages: list[NormalizedPage]) -> None:
        self._file.save({"key": key, "pages": [[page.number, page.raw, page.text, page.label] for page in pages]})


class _NormalizedPages:
    def __init__(self) -> None:
        self._fingerprint = None
        self._pages: list[NormalizedPage] = []

    def of(self, pdf_path: Path) -> list[NormalizedPage]:
        key = [CACHE_VERSION, *document_fingerprint(pdf_path)]
        if key != self._fingerprint:
            self._pages = self._read(pdf_path, key)
            self._fingerprint = key
        return self._pages

    @staticmethod
    def _read(pdf_path: Path, key: list) -> list[NormalizedPage]:
        cache = _PageCache(pdf_path)
        cached = cache.loaded(key)
        if cached is not None:
            return cached
        pages = [NormalizedPage.normalized(record.pdf_page, record.text, record.printed_page)
                 for record in page_records(pdf_path)]
        cache.save(key, pages)
        return pages


_NORMALIZED_PAGES = _NormalizedPages()


class _QuoteFinder:
    def __init__(self, needle: str, threshold: float, pages: list[NormalizedPage]) -> None:
        self._needle = needle
        self._threshold = threshold
        self._pages = pages

    def hits(self, max_hits: int) -> list[QuoteHit]:
        return (self._exact_hits(self._pages, max_hits) or self._exact_hits(self._page_pairs(), max_hits)
                or self._near_hits())

    def _exact_hits(self, searched: list, max_hits: int) -> list[QuoteHit]:
        found: list[QuoteHit] = []
        for page in searched:
            index = page.text.find(self._needle) if page.text else -1
            if index != -1:
                found.append(_hit(page, _Span(index, len(self._needle)), _Match(1.0, exact=True)))
            if len(found) >= max_hits:
                break
        return found

    def _page_pairs(self) -> list[_JoinedPages]:
        return [_JoinedPages(first, second) for first, second in zip(self._pages, self._pages[1:])]

    def _near_hits(self) -> list[QuoteHit]:
        found = (self._fuzzy_match(page) for page in self._pages if page.text)
        return [hit for hit in found if hit is not None]

    def _fuzzy_match(self, page: NormalizedPage) -> QuoteHit | None:
        block = self._longest_shared_run(page.text)
        if not block.size:
            return None
        window = self._fuzzy_window(page.text, block)
        similarity = round(SequenceMatcher(None, self._needle, window, autojunk=False).ratio(),
                           SIMILARITY_PRECISION)
        if similarity < self._threshold:
            return None
        span = _Span(block.b, max(block.size, len(self._needle)))
        return _hit(page, span, _Match(similarity, exact=False))

    def _longest_shared_run(self, haystack: str):
        matcher = SequenceMatcher(None, self._needle, haystack, autojunk=False)
        return matcher.find_longest_match(0, len(self._needle), 0, len(haystack))

    def _fuzzy_window(self, haystack: str, block) -> str:
        lo = max(0, block.b - block.a)
        hi = lo + int(len(self._needle) * FUZZY_WINDOW_SLACK)
        return haystack[lo:hi]

def _hit(page, span: _Span, match: _Match) -> QuoteHit:
    context = _context(page.text, span.start, span.length)
    page_text = page.page_text(span.start, span.length)
    return QuoteHit(page.number, page.label, match.similarity, match.exact, context, page_text, page.spanned)


class _ContextWindow:
    def __init__(self, pad: int) -> None:
        self._pad = pad

    def around(self, text: str, start: int, length: int) -> str:
        lo = max(0, start - self._pad)
        hi = min(len(text), start + length + self._pad)
        leading = ELLIPSIS if lo > 0 else ""
        trailing = ELLIPSIS if hi < len(text) else ""
        return f"{leading}{text[lo:hi]}{trailing}"


_QUOTE_WINDOW = _ContextWindow(CONTEXT_PAD_CHARS)
_LOCATE_WINDOW = _ContextWindow(LOCATE_CONTEXT_PAD_CHARS)


def _context(text: str, start: int, length: int) -> str:
    return _QUOTE_WINDOW.around(text, start, length)


def locate_context(text: str, start: int, length: int) -> str:
    return _LOCATE_WINDOW.around(text, start, length)
