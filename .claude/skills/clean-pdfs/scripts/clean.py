from __future__ import annotations

import sys
from pathlib import Path


def _lib_dir() -> Path:
    here = Path(__file__).resolve()
    return next(parent / "lib" for parent in here.parents if (parent / "lib" / "vault.py").is_file())


sys.path.insert(0, str(_lib_dir()))
import vault

from _clean.analysis import PdfAnalysis
from _clean.cleaning import CleanedCopy, InPlaceClean
from _clean.cli import Cli, ParserBuilder, main
from _clean.cmap import CMapError, ToUnicodeCMap
from _clean.commands import CleanCommands, PageCommands, TocCommands, VolumeCommands
from _clean.constants import (
    ARTICLE_ITEM_TYPE,
    BOOK_ITEM_TYPE,
    GUTTED_PAGE_MIN_CHARS,
    GUTTED_PAGE_RATIO,
    MAX_SCAN_PAGES,
    MAX_TITLE_CHARS,
    RENDER_DPI,
    SCAN_DPI,
    TOTAL_TEXT_RATIO,
    VERIFY_SAMPLE_PAGES,
)
from _clean.covers import CoverImage, CoverPage
from _clean.entries import EntrySource, OutlineProposal
from _clean.fontcommands import TABLE_OPTION, FontCommands
from _clean.fontfilter import FilterError, FontFace, FontFilter, FontReport, OutlineSuggestion
from _clean.fontrepair import (
    FONT_TEMPORARY_SUFFIX,
    RECORD_KEY,
    FontRepair,
    RepairCheck,
    RepairPlan,
    RepairRecord,
    VerificationFailed,
)
from _clean.fonts import MUPDF_FONT_NAME_LIMIT, FontRecord, PdfFonts
from _clean.fontscan import MISSING_FROM_TOUNICODE, FlaggedCode, FontScan, FontStatusRows
from _clean.glyphs import IDENTITIES_PATH, GlyphName, GlyphQuery, Identity, IdentityResolver, IdentityTable
from _clean.identification import (
    GLYPH_RENDER_DPI,
    IDENTIFY_SAMPLES,
    LINE_CROP_MARGIN,
    FontIdentification,
    GlyphRenders,
    RenderRequest,
    SampledOccurrences,
)
from _clean.inspection import OutlineDiff, ScanRange, Suspicions
from _clean.outline import Entry, Outline, OutlineError, ProposedOutline, TitleText
from _clean.paths import PdfLocation
from _clean.render import FIRST_PAGE, PageRender
from _clean.repair import QpdfRepair
from _clean.report import Report
from _clean.textlayer import CONTEXT_CHARS, CachedOccurrences, Occurrences, SuspectOccurrence, TextLayerOccurrences
from _clean.toc import TocDocument
from _clean.verification import GuttingCheck, SampledPages
from vault import ARTICLE_PAGE_THRESHOLD, ReplacementFile

__all__ = [
    "ARTICLE_ITEM_TYPE", "ARTICLE_PAGE_THRESHOLD", "BOOK_ITEM_TYPE", "CONTEXT_CHARS",
    "FONT_TEMPORARY_SUFFIX", "GLYPH_RENDER_DPI", "GUTTED_PAGE_MIN_CHARS", "GUTTED_PAGE_RATIO",
    "IDENTIFY_SAMPLES", "IDENTITIES_PATH", "LINE_CROP_MARGIN", "MAX_SCAN_PAGES", "MAX_TITLE_CHARS",
    "MISSING_FROM_TOUNICODE", "MUPDF_FONT_NAME_LIMIT", "RECORD_KEY", "RENDER_DPI", "SCAN_DPI",
    "TABLE_OPTION", "TOTAL_TEXT_RATIO", "VERIFY_SAMPLE_PAGES", "FIRST_PAGE",
    "CMapError", "CachedOccurrences", "CleanCommands", "CleanedCopy", "Cli", "CoverImage", "CoverPage", "Entry",
    "EntrySource", "FilterError", "FlaggedCode", "FontCommands", "FontFace", "FontFilter", "FontReport",
    "FontIdentification", "FontRecord", "FontRepair", "FontScan", "FontStatusRows", "GlyphName", "GlyphQuery",
    "GlyphRenders", "GuttingCheck", "Identity", "IdentityResolver",
    "IdentityTable", "InPlaceClean", "Occurrences", "Outline", "OutlineDiff", "OutlineError",
    "OutlineProposal", "OutlineSuggestion", "PageCommands", "PageRender", "ParserBuilder", "PdfAnalysis", "PdfFonts",
    "PdfLocation", "ProposedOutline", "QpdfRepair", "RenderRequest", "RepairCheck", "RepairPlan",
    "RepairRecord", "ReplacementFile", "Report", "SampledOccurrences", "SampledPages", "ScanRange",
    "SuspectOccurrence", "Suspicions", "TextLayerOccurrences", "TitleText", "ToUnicodeCMap",
    "TocCommands", "TocDocument", "VerificationFailed", "VolumeCommands", "main", "vault",
]


if __name__ == "__main__":
    main()
