from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pagetext

from .corpus import CorpusBody, CorpusFolios, ZoteroDeepLink
from .verdict import VerdictText

FOLIO_FROM_CORPUS = "corpus"
FOLIO_FROM_TEXT_LAYER = "text layer"


class QuoteVerification:
    def __init__(self, pdf: Path, quote: str, threshold: float) -> None:
        self._pdf = pdf
        self._quote = quote
        corpus = CorpusBody(pdf.stem)
        self._link = ZoteroDeepLink(corpus)
        self._folios = CorpusFolios(corpus)
        self._notation = pagetext.QuotedNotation(pdf, quote)
        self._removed = self._notation.removed()
        self._hits = self._searched(threshold)

    def verified(self) -> bool:
        return len(self._exact_hits()) == 1

    def ambiguous(self) -> bool:
        return len(self._exact_hits()) > 1

    def payload(self) -> dict:
        return {"pdf": str(self._pdf), "quote": self._quote, "verified": self.verified(),
                "ambiguous": self.ambiguous(),
                "prose_only": not self._removed.is_empty, "notation_read_from_page": self._removed.listed(),
                "link_absent": self._link.absence(), "hits": [self._linked(hit) for hit in self._hits]}

    def rendered(self) -> str:
        return VerdictText(self.payload()).rendered()

    def _exact_hits(self) -> list[pagetext.QuoteHit]:
        return [hit for hit in self._hits if hit.exact]

    def _linked(self, hit: pagetext.QuoteHit) -> dict:
        folio = self._folios.of(hit.pdf_page)
        source = FOLIO_FROM_CORPUS if folio else FOLIO_FROM_TEXT_LAYER
        return {**asdict(hit), "printed_page": folio or hit.printed_page, "folio_source": source,
                "link": self._link.at(hit.pdf_page)}

    def _searched(self, threshold: float) -> list[pagetext.QuoteHit]:
        if self._removed.is_empty:
            return pagetext.find_quote(self._pdf, self._quote, threshold=threshold)
        without_notation = pagetext.find_quote_in_texts(self._pdf, self._notation.prose(), self._notation.prose_pages(),
                                                        threshold=threshold)
        if any(hit.exact for hit in without_notation) or not self._removed.spans:
            return without_notation
        return pagetext.find_quote_around_notation(self._pdf, self._quote) or without_notation
