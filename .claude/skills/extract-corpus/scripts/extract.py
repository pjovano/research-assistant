from __future__ import annotations

import importlib
import sys
from pathlib import Path

def _lib_dir() -> Path:
    here = Path(__file__).resolve()
    return next(parent / "lib" for parent in here.parents if (parent / "lib" / "vault.py").is_file())


sys.path.insert(0, str(_lib_dir()))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault

from _extract.cli import EXIT_OK, EXIT_USAGE, CommandLine, Commands, main
from _extract.console import EXIT_CHANGED, EXIT_DOUBTFUL
from _extract.ranges import PageRanges

_LAZY_EXPORTS = {
    "_extract.blocks": ("Block", "DocumentBlocks", "PageBlocks"),
    "_extract.build": ("ConversionPlan", "CorpusBuild", "DoubtfulPagesRemain"),
    "_extract.candidates": ("HeadingCandidate", "HeadingStyles", "OpenedHeadings"),
    "_extract.cache": ("MarkerCache",),
    "_extract.checks": ("STATUS_DOUBTFUL", "STATUS_KEPT", "PageChecks", "PageVerdict"),
    "_extract.engine": ("MarkerEngine",),
    "_extract.enginelabels": ("CachedLabels", "EngineLabels", "LabelledRun"),
    "_extract.pagefolios": ("FolioReader",),
    "_extract.pagelabels": ("LabelRanges", "PageLabelWriter"),
    "_extract.footnotes": ("FootnoteDefinition", "FootnoteLabels", "FootnoteLog", "FootnotePairer"),
    "_extract.hyphens": ("Hyphens",),
    "_extract.layer": ("LayerChar", "TextLayer"),
    "_extract.markdown": ("HtmlToMarkdown", "TableMarkdown"),
    "_extract.layerhtml": ("BlockHtml",),
    "_extract.layerlines": ("PageLines", "rows_of"),
    "_extract.outline": ("Heading", "Outline"),
    "_extract.paths": ("CorpusFile", "CorpusFileExists", "FrontmatterFields", "LibraryPdfs", "NoteMissing",
                       "PdfLocator", "PdfNotFound"),
    "_extract.readings": ("MalformedReadings", "Reading", "WorkerReadings"),
    "_extract.repairs": ("FontRepairRecord",),
    "_extract.report": ("DoubtfulReport", "ExtractReport", "ProbeReport", "WrittenBody"),
    "_extract.request": ("ExtractionRequest",),
    "_extract.trial": ("TrialNote",),
    "_extract.acceptance": ("Acceptance",),
    "_extract.regression": ("BodyComparison", "RegressionCheck", "RegressionSample", "ReviewedWorks"),
    "_extract.statements": ("StatementLabel",),
    "surya_servers": ("SuryaServers",),
    "_extract.structure": ("NoteStructure", "PageAssembler"),
    "_extract.enginemath": ("EngineNotation",),
    "_extract.writer": ("NoteWriter",),
}
_MODULE_OF = {name: module for module, names in _LAZY_EXPORTS.items() for name in names}

__all__ = [
    "vault", "EXIT_CHANGED", "EXIT_DOUBTFUL", "EXIT_OK", "EXIT_USAGE", "CommandLine", "Commands", "PageRanges", "main",
    *_MODULE_OF,
]


def __getattr__(name: str):
    try:
        module_name = _MODULE_OF[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    return getattr(importlib.import_module(module_name), name)


if __name__ == "__main__":
    sys.exit(main())
