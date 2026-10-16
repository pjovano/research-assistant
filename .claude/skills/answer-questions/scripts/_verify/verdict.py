from __future__ import annotations

from pathlib import Path

VERDICT_VERIFIED = "VERIFIED"
VERDICT_NEAR_MATCH = "NEAR MATCH ONLY"
VERDICT_AMBIGUOUS = "AMBIGUOUS"
VERDICT_NOT_FOUND = "NOT FOUND"
PROSE_ONLY_SUFFIX = " (prose only)"
PLACE_JOIN = ", "


def cited_place(page: dict) -> str:
    return page["printed_page"] or f"(file page {page['pdf_page']})"


class VerdictText:
    def __init__(self, payload: dict) -> None:
        self._name = Path(payload["pdf"]).name
        self._prose_only = payload["prose_only"]
        self._notation = payload["notation_read_from_page"]
        self._link_absent = payload["link_absent"]
        self._hits = payload["hits"]

    def rendered(self) -> str:
        if not self._hits:
            return self._not_found()
        if len(self._exact_hits()) > 1:
            return self._ambiguous()
        return self._top_hit(self._hits[0])

    def _exact_hits(self) -> list[dict]:
        return [hit for hit in self._hits if hit["exact"]]

    def _not_found(self) -> str:
        return (f"{VERDICT_NOT_FOUND} in {self._name}\n"
                "The quote does not appear in this source, even approximately.\n"
                "Do not cite it. Re-open the source and read the passage again.")

    def _ambiguous(self) -> str:
        places = PLACE_JOIN.join(self._place(hit) for hit in self._exact_hits())
        return (f"{VERDICT_AMBIGUOUS} in {self._name}\n"
                f"The quotation appears on {len(self._exact_hits())} pages: {places}.\n"
                "Quote a longer span that appears on one page only, then verify again.")

    @staticmethod
    def _place(hit: dict) -> str:
        folio = f" (p. {hit['printed_page']})" if hit["printed_page"] else ""
        return f"file page {hit['pdf_page']}{folio}"

    def _top_hit(self, hit: dict) -> str:
        lines = [f"{self._status(hit)} in {self._name}",
                 f"  printed folio : {self._folio_line(hit)}",
                 f"  file page     : {hit['pdf_page']}",
                 *self._span_lines(hit),
                 f"  link          : {hit['link'] or self._link_absent}",
                 f"  similarity    : {hit['similarity']}",
                 f"  context       : {hit['context']}",
                 f"  page text     : {hit['page_text']}",
                 *self._notation_lines(hit),
                 self._citation_advice(hit)]
        return "\n".join(lines)

    def _status(self, hit: dict) -> str:
        verdict = VERDICT_VERIFIED if hit["exact"] else VERDICT_NEAR_MATCH
        return verdict + PROSE_ONLY_SUFFIX if self._prose_only else verdict

    @staticmethod
    def _span_lines(hit: dict) -> list[str]:
        if not hit["spans_pages"]:
            return []
        first, second = hit["spans_pages"]
        return [f"  spans pages   : file pages {first} and {second}; the folio reported is page {first}'s"]

    @staticmethod
    def _folio_line(hit: dict) -> str:
        if not hit["printed_page"]:
            return "(no printed folio detected)"
        return f"{hit['printed_page']} ({hit['folio_source']})"

    def _notation_lines(self, hit: dict) -> list[str]:
        return [f"  read from the page, not verified by text (p. {cited_place(hit)}): {removed}"
                for removed in self._notation]

    @staticmethod
    def _citation_advice(hit: dict) -> str:
        if hit["exact"]:
            return f"\n  cite as       : p. {cited_place(hit)}"
        return ("\nThe quote differs from the source text. Correct it against the "
                "context above before citing, or quote a shorter exact span.")
