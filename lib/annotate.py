from __future__ import annotations

import sys

from vault import LibraryPdf

from _annotate.cli import AnnotateCli
from _annotate.crosspage import CrossPageResolver, CrossPageSegments, RequestResolver
from _annotate.editing import HighlightStamp, IncrementalEdit
from _annotate.markers import (
    EditionAnchorIndex,
    EditionMarker,
    InlineMarkerIndex,
    PageGrids,
    MarginalNumberIndex,
    MarkerGrammar,
    MarkerNumber,
)
from _annotate.notes import Note, NoteLedger, Tag
from _annotate.overlap import CoveredWords, OverlapResolver
from _annotate.pages import (
    BodyLines,
    ColumnEstimate,
    PageBody,
    PageCharacters,
    PageLayout,
    PageLines,
    TextColumn,
    VisualLine,
)
from _annotate.pairs import HighlightEdges, HighlightPairs, PairRule
from _annotate.palette import Colour, TagPalette
from _annotate.quotation_span import CrossPageQuotationSpan, FoldedWords, QuotationSpan
from _annotate.reader import (
    AnnotationInventory,
    AnnotationRecord,
    AnnotationRevision,
    RevisionChange,
    RevisionOutcome,
)
from _annotate.requests import AnnotationDecision, AnnotationRequest, DecisionReport
from _annotate.resolver import DocumentWorkspaces, PageWorkspace, SpanResolver
from _annotate.spans import (
    MarkerTail,
    SpanGeometry,
    SpanNormalizer,
    SpanValidator,
    WordBox,
    WordGrid,
    WordSpan,
)
from _annotate.specs import AnnotationSpec, RevisionSpec, SpecColour, SpecError
from _annotate.writer import AnnotationPlan, AnnotationWriter

__all__ = [
    "AnnotateCli", "AnnotationDecision", "AnnotationInventory", "AnnotationPlan",
    "AnnotationRecord", "AnnotationRequest", "AnnotationRevision", "AnnotationSpec",
    "AnnotationWriter", "BodyLines", "Colour", "ColumnEstimate", "CoveredWords",
    "CrossPageQuotationSpan", "CrossPageResolver", "CrossPageSegments", "DecisionReport", "DocumentWorkspaces",
    "EditionAnchorIndex", "EditionMarker", "FoldedWords", "HighlightEdges", "HighlightPairs", "HighlightStamp",
    "IncrementalEdit", "InlineMarkerIndex", "LibraryPdf", "MarginalNumberIndex", "MarkerGrammar",
    "MarkerNumber", "MarkerTail", "PageGrids",
    "Note", "NoteLedger", "OverlapResolver", "PageBody", "PageCharacters", "PageLayout",
    "PageLines", "PageWorkspace", "PairRule", "QuotationSpan", "RequestResolver", "RevisionChange",
    "RevisionOutcome", "RevisionSpec", "SpanGeometry", "SpanNormalizer", "SpanResolver",
    "SpanValidator", "SpecColour", "SpecError", "Tag", "TagPalette", "TextColumn", "VisualLine",
    "WordBox", "WordGrid", "WordSpan",
]


if __name__ == "__main__":
    sys.exit(AnnotateCli().run(sys.argv[1:]))
