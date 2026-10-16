from __future__ import annotations

import argparse
from pathlib import Path

from _drive.steps import JsonLine

from .commands import CleanCommands, PageCommands, TocCommands, VolumeCommands
from .drive import KINDS, CleanDriver
from .constants import MAX_SCAN_PAGES, SCAN_DPI
from .fontcommands import FontCommands
from .glyphs import LEARN_METHODS, glyph_code
from .ocr import VisionUnavailable, VisionUnresponsive
from .outline import OutlineError
from .readeranswers import LearnRefused
from .render import FIRST_PAGE
from .report import Report

DESCRIPTION = "Stage 0 -- de-annotate, judge the cover, bookmark: the inbox PDF, in place."
ENTRIES_HELP = "Path to a JSON list of {level, title, page}, or - for stdin"
FILTER_HELP = "<font>:<size>:<level>, one per level, as toc fonts prints the font and size"
ALL_OR_PDF_ATTRIBUTE = "requires_all_or_pdf"
STATUS_VISION_UNAVAILABLE = "vision-unavailable"
FAILURE_EXIT_STATUS = 1


class ParserBuilder:
    def __init__(self) -> None:
        self._clean = CleanCommands()
        self._pages = PageCommands()
        self._toc = TocCommands()
        self._volumes = VolumeCommands()
        self._fonts = FontCommands()

    def build(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description=DESCRIPTION)
        sub = parser.add_subparsers(dest="command", required=True)
        self._add_plan(sub)
        self._add_clean(sub)
        self._add_render(sub)
        self._add_add_cover(sub)
        self._add_drop_page(sub)
        self._add_toc(sub)
        self._add_volume(sub)
        self._add_fonts(sub)
        self._add_drive(sub)
        return parser

    def _add_drive(self, sub: argparse._SubParsersAction) -> None:
        for name, does, step in (("drive-fonts", "scan the fonts and list the glyphs to read", DriveSteps.fonts),
                                 ("drive-learn", "learn the glyph reader's answers and repair the fonts",
                                  DriveSteps.learn),
                                 ("drive-route", "route the cleaned PDF by its kind", DriveSteps.route)):
            p = sub.add_parser(name, help=f"ingest: {does}; one JSON line")
            p.add_argument("pdf")
            p.set_defaults(func=step)
        sub.choices["drive-route"].add_argument("--kind", required=True, choices=KINDS,
                                                help="the kind the pdf-cleaner worker judged the PDF")

    def _add_plan(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("plan")
        p.add_argument("--all", action="store_true")
        p.add_argument("pdf", nargs="?", default=None)
        p.set_defaults(func=self._clean.plan, **{ALL_OR_PDF_ATTRIBUTE: "plan"})

    def _add_clean(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("clean")
        p.add_argument("pdf")
        p.add_argument("--apply", action="store_true")
        p.set_defaults(func=self._clean.clean)

    def _add_render(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("render")
        p.add_argument("pdf")
        p.add_argument("--page", type=int, default=FIRST_PAGE,
                       help="1-based page number, the same convention as toc scan "
                            "and outline entries")
        p.set_defaults(func=self._pages.render)

    def _add_add_cover(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("add-cover")
        p.add_argument("pdf")
        p.add_argument("--image", required=True)
        p.add_argument("--force", action="store_true",
                       help="Add a cover even though the file looks like an article")
        p.add_argument("--crop-top", type=float, default=0.0, metavar="FRAC",
                       help="Fraction of image height to cut off the top")
        p.add_argument("--crop-bottom", type=float, default=0.0, metavar="FRAC",
                       help="Fraction of image height to cut off the bottom")
        p.add_argument("--apply", action="store_true")
        p.set_defaults(func=self._pages.add_cover)

    def _add_drop_page(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("drop-page")
        p.add_argument("pdf")
        p.add_argument("--page", type=int, required=True,
                       help="1-based file page to delete, the same convention as render --page "
                            "(render it first)")
        p.add_argument("--apply", action="store_true")
        p.set_defaults(func=self._pages.drop_page)

    def _add_toc(self, sub: argparse._SubParsersAction) -> None:
        inner = sub.add_parser("toc").add_subparsers(dest="toc_command", required=True)
        self._add_toc_probe(inner)
        self._add_toc_scan(inner)
        self._add_toc_fonts(inner)
        self._add_toc_suggest(inner)
        self._add_toc_write(inner)
        self._add_toc_clear(inner)

    def _add_volume(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("volume")
        p.add_argument("pdf")
        p.add_argument("--apply", action="store_true")
        p.set_defaults(func=self._volumes.move)

    def _add_fonts(self, sub: argparse._SubParsersAction) -> None:
        fonts = sub.add_parser("fonts")
        fonts.add_argument("--table", default=None, metavar="PATH",
                           help="Identity table to read and write instead of the vault's "
                                "library/glyph-identities.json; for tests only")
        inner = fonts.add_subparsers(dest="fonts_command", required=True)
        self._add_fonts_scan(inner)
        self._add_fonts_identify(inner)
        self._add_fonts_pages(inner)
        self._add_fonts_learn(inner)
        self._add_fonts_learn_reader(inner)
        self._add_fonts_migrate_keys(inner)
        self._add_fonts_repair(inner)

    def _add_toc_probe(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("probe")
        p.add_argument("pdf")
        p.set_defaults(func=self._toc.probe)

    def _add_toc_scan(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("scan")
        p.add_argument("pdf")
        p.add_argument("--from", dest="first", type=int, required=True,
                       help="First 1-based file page to render")
        p.add_argument("--to", dest="last", type=int, required=True,
                       help=f"Last 1-based file page to render (at most {MAX_SCAN_PAGES} per call)")
        p.add_argument("--dpi", type=int, default=SCAN_DPI)
        p.set_defaults(func=self._toc.scan)

    def _add_toc_fonts(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("fonts")
        p.add_argument("pdf")
        p.add_argument("--page", type=int, required=True, help="1-based file page to list the fonts of")
        p.set_defaults(func=self._toc.fonts)

    def _add_toc_suggest(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("suggest")
        p.add_argument("pdf")
        p.add_argument("--filter", action="append", required=True, metavar="SPEC", help=FILTER_HELP)
        p.add_argument("--out", default=None, metavar="PATH",
                       help="Also write the entry list as JSON to this path in the scratch directory")
        p.set_defaults(func=self._toc.suggest)

    def _add_toc_write(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("write")
        p.add_argument("pdf")
        p.add_argument("--entries", required=True, action="append",
                       help=f"{ENTRIES_HELP}; repeat to join several lists in the order given")
        p.add_argument("--apply", action="store_true")
        p.add_argument("--force", action="store_true",
                       help="Write even though the list of entries is empty")
        p.set_defaults(func=self._toc.write)

    def _add_toc_clear(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("clear")
        p.add_argument("pdf")
        p.add_argument("--apply", action="store_true")
        p.set_defaults(func=self._toc.clear)

    def _add_fonts_scan(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("scan")
        p.add_argument("--all", action="store_true",
                       help="Summarize every PDF in the library from its ToUnicode tables alone")
        p.add_argument("pdf", nargs="?", default=None)
        p.set_defaults(func=self._fonts.scan, **{ALL_OR_PDF_ATTRIBUTE: "fonts scan"})

    def _add_fonts_identify(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("identify")
        p.add_argument("pdf")
        p.set_defaults(func=self._fonts.identify)

    def _add_fonts_pages(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("pages", help="read-only: the file pages every flagged code occurs on, or null where "
                                         "a flagged code's pages are unknown")
        p.add_argument("pdf")
        p.set_defaults(func=self._fonts.pages)

    def _add_fonts_learn(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("learn")
        p.add_argument("--font", required=True, help="Font family: the BaseFont without its subset prefix")
        glyph = p.add_mutually_exclusive_group(required=True)
        glyph.add_argument("--glyph", help="Glyph name from /Differences, as written")
        glyph.add_argument("--code", type=glyph_code, help="Hex code of a glyph that has no name")
        p.add_argument("--unicode", required=True,
                       help='Replacement string; "" deletes the glyph from the text layer')
        p.add_argument("--method", required=True, choices=LEARN_METHODS)
        p.add_argument("--equals-sign", action="store_true",
                       help='The glyph is an equals sign: --unicode "=" names that character')
        p.add_argument("--apply", action="store_true")
        p.set_defaults(func=self._fonts.learn)

    def _add_fonts_migrate_keys(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("migrate-keys")
        p.add_argument("--apply", action="store_true",
                       help="Rewrite the identity table (default: print the planned key rewrites)")
        p.set_defaults(func=self._fonts.migrate_keys)

    def _add_fonts_learn_reader(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("learn-reader")
        p.add_argument("--answers", required=True, type=Path,
                       help="The glyph reader's JSON: a list for one PDF, or an object keyed by PDF basename")
        p.add_argument("--identify", required=True, type=Path, action="append",
                       help="An `identify` report for a PDF the answers name; repeat for each PDF")
        p.add_argument("--apply", action="store_true")
        p.set_defaults(func=self._fonts.learn_reader)

    def _add_fonts_repair(self, sub: argparse._SubParsersAction) -> None:
        p = sub.add_parser("repair")
        p.add_argument("pdf")
        p.add_argument("--apply", action="store_true")
        p.add_argument("--partial", action="store_true",
                       help="Patch the resolved codes even though some remain unresolved")
        p.set_defaults(func=self._fonts.repair)


class DriveSteps:
    @staticmethod
    def fonts(args: argparse.Namespace) -> None:
        JsonLine.emit(CleanDriver().fonts(args.pdf))

    @staticmethod
    def learn(args: argparse.Namespace) -> None:
        JsonLine.emit(CleanDriver().learn(args.pdf))

    @staticmethod
    def route(args: argparse.Namespace) -> None:
        JsonLine.emit(CleanDriver().route(args.pdf, args.kind))


class Cli:
    def __init__(self) -> None:
        self._parser = ParserBuilder().build()

    def run(self) -> None:
        args = self._parser.parse_args()
        self._validate_all_or_pdf(args)
        self._dispatch(args)

    def _validate_all_or_pdf(self, args: argparse.Namespace) -> None:
        verb = getattr(args, ALL_OR_PDF_ATTRIBUTE, None)
        if verb and not args.all and not args.pdf:
            self._parser.error(f"{verb} requires --all or a pdf name")

    def _dispatch(self, args: argparse.Namespace) -> None:
        try:
            args.func(args)
        except (OutlineError, LearnRefused, VisionUnresponsive) as rejection:
            raise SystemExit(str(rejection))
        except VisionUnavailable as unavailable:
            Report({"status": STATUS_VISION_UNAVAILABLE, "error": str(unavailable)}).print()
            raise SystemExit(FAILURE_EXIT_STATUS)


def main() -> None:
    Cli().run()
