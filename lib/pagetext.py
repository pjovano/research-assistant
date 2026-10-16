from __future__ import annotations

from _pagetext.folio import BARE_FOLIO_RE
from _pagetext.normalize import NormalizedText, normalize, page_wording, typographic_form
from _pagetext.pages import (
    DEFAULT_RENDER_DPI,
    PageRecord,
    document_fingerprint,
    TOP_LEVEL,
    outline_entries,
    page_records,
    page_texts,
    printed_page_label,
    render_pages,
)
from _pagetext.prose import QuotedNotation, RemovedNotation
from _pagetext.classifier import ClassifierUnavailable, ClassifierVerdict, PageClassifier
from _pagetext.quality import (
    VERDICT_EMPTY,
    VERDICT_GOOD,
    VERDICT_POOR,
    VERDICT_UNAVAILABLE,
    Quality,
    assess,
    assess_all,
)
from _pagetext.quotes import (
    DEFAULT_NEAR_MATCH_THRESHOLD,
    MIN_QUOTE_LENGTH_CHARS,
    NormalizedPage,
    QuoteHit,
    find_quote,
    find_quote_around_notation,
    find_quote_in_texts,
    locate_context,
    normalized_pages,
)

__all__ = [
    "BARE_FOLIO_RE", "DEFAULT_RENDER_DPI", "ClassifierUnavailable", "ClassifierVerdict", "DEFAULT_NEAR_MATCH_THRESHOLD",
    "MIN_QUOTE_LENGTH_CHARS", "NormalizedPage", "NormalizedText", "PageClassifier", "PageRecord", "Quality",
    "QuoteHit", "QuotedNotation", "RemovedNotation", "VERDICT_EMPTY", "VERDICT_GOOD", "VERDICT_POOR",
    "VERDICT_UNAVAILABLE", "assess", "assess_all", "document_fingerprint", "find_quote", "find_quote_around_notation",
    "find_quote_in_texts",
    "TOP_LEVEL", "locate_context", "normalize", "normalized_pages", "outline_entries", "page_records", "page_texts",
    "page_wording", "printed_page_label", "render_pages", "typographic_form",
]
