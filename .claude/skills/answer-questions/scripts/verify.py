from __future__ import annotations

import sys
from pathlib import Path


def _lib_dir() -> Path:
    here = Path(__file__).resolve()
    return next(parent / "lib" for parent in here.parents if (parent / "lib" / "vault.py").is_file())


sys.path.insert(0, str(_lib_dir()))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _verify.cli import (
    DEFAULT_LOCATE_LIMIT,
    DEFAULT_QUALITY_SAMPLE_PAGES,
    FAILURE_EXIT_CODE,
    NOT_VERIFIED_EXIT_CODE,
    POOR_TEXT_LAYER_EXIT_CODE,
    SUCCESS_EXIT_CODE,
    USAGE_EXIT_CODE,
    VerifyCli,
    main,
)
from _verify.corpus import PAGE_QUERY, CorpusBody, CorpusFolios, ZoteroDeepLink
from _verify.quotes import FOLIO_FROM_CORPUS, FOLIO_FROM_TEXT_LAYER, QuoteVerification
from _verify.textlayer import TermLocation, TextLayerQuality
from _verify.verdict import (
    PLACE_JOIN,
    PROSE_ONLY_SUFFIX,
    VERDICT_AMBIGUOUS,
    VERDICT_NEAR_MATCH,
    VERDICT_NOT_FOUND,
    VERDICT_VERIFIED,
    VerdictText,
    cited_place,
)

__all__ = [
    "DEFAULT_LOCATE_LIMIT", "DEFAULT_QUALITY_SAMPLE_PAGES", "FAILURE_EXIT_CODE", "FOLIO_FROM_CORPUS",
    "FOLIO_FROM_TEXT_LAYER", "NOT_VERIFIED_EXIT_CODE", "PAGE_QUERY", "PLACE_JOIN", "POOR_TEXT_LAYER_EXIT_CODE",
    "PROSE_ONLY_SUFFIX", "SUCCESS_EXIT_CODE", "USAGE_EXIT_CODE", "VERDICT_AMBIGUOUS", "VERDICT_NEAR_MATCH",
    "VERDICT_NOT_FOUND", "VERDICT_VERIFIED", "CorpusBody", "CorpusFolios", "QuoteVerification", "TermLocation",
    "TextLayerQuality", "VerdictText", "VerifyCli", "ZoteroDeepLink", "cited_place", "main",
]

if __name__ == "__main__":
    main()
