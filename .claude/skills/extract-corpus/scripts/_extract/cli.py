from __future__ import annotations

import argparse
import sys
from pathlib import Path

import vault
from surya_servers import IdleReaper, SuryaServers

from _drive.steps import JsonLine
from _extract.backfill import BACKFILL_DIR, BackfillCommands
from _extract.backfillstep import RUN_COMMAND
from _extract.cache import CachedConversions
from _extract.console import EXIT_ENGINE_FAILED, EXIT_OK, EXIT_USAGE, FORCE_OCR_FLAG, JsonOutput
from _extract.correctioncommands import CorrectionCommands
from _extract.enginecost import CheapestFirst
from _extract.correctionoptions import CorrectionOptions
from _extract.failures import UsageFailure
from _extract.paths import LibraryPdfs, PdfLocator
from _extract.prefetch import BackfillPrefetch
from _extract.records import ExtractionRecords
from _extract.regression import DEFAULT_JOBS, SAMPLE_SIZE
from _extract.regressbaseline import BASELINE_MODES
from _extract.regresssample import DEFAULT_SEED
from _extract.request import FORCE_OCR_PAGES_FLAG
from _extract.reviewing import ReviewCommands
from _extract.stage import StageCommands

_PDF_HELP = "a library filename, or a path"
DRIVE_STEPS = {
    "prep": "probe; ask once for the font repair; convert, and list the scope",
    "fonts-checked": "record that the work's font repair is done, and how it settled the work's reading, so that "
                     "prefetch and prep convert it",
    "trial": "settle the scope, extract the trial, verify it, and list it for review",
    "retrial": "merge the page readings and extract the trial again",
    "cleanup": "apply the layout corrector's corrections to the trial, then accept and label it",
}
ENGINE_STEPS = ("prep", "trial", "retrial")


class Commands:
    def probe(self, args: argparse.Namespace) -> int:
        return StageCommands().probe(args)

    def extract(self, args: argparse.Namespace) -> int:
        return StageCommands().extract(args)

    def scope(self, args: argparse.Namespace) -> int:
        return StageCommands().scope(args)

    def labels(self, args: argparse.Namespace) -> int:
        return StageCommands().labels(args)

    def convert(self, args: argparse.Namespace) -> int:
        return StageCommands().convert(args)

    def layer_sample(self, args: argparse.Namespace) -> int:
        return StageCommands().layer_sample(args)


    def accept(self, args: argparse.Namespace) -> int:
        return ReviewCommands().accept(args)

    def regress(self, args: argparse.Namespace) -> int:
        return ReviewCommands().regress(args)

    def review_status(self, args: argparse.Namespace) -> int:
        return ReviewCommands().review_status(args)

    def regress_sample(self, args: argparse.Namespace) -> int:
        return ReviewCommands().regress_sample(args)

    def correct(self, args: argparse.Namespace) -> int:
        return CorrectionCommands().correct(args)

    def correction_listing(self, args: argparse.Namespace) -> int:
        return CorrectionCommands().correction_listing(args)

    def record(self, args: argparse.Namespace) -> int:
        basename = vault.basename_of(PdfLocator().resolve(args.pdf))
        JsonOutput().emit({"basename": basename, "record": ExtractionRecords().entry(basename)})
        return EXIT_OK

    def reap_servers(self, _args: argparse.Namespace) -> int:
        reaper = IdleReaper()
        reaper.watch()
        JsonOutput().emit({"stopped": reaper.stopped_pids})
        return EXIT_OK

    def prefetch(self, args: argparse.Namespace) -> int:
        prefetch = BackfillPrefetch(BACKFILL_DIR)
        prefetch.run(args.works, tuple(args.keys), args.await_fonts)
        JsonOutput().emit(prefetch.as_dict())
        return EXIT_OK if prefetch.halt is None else EXIT_ENGINE_FAILED

    def stop_servers(self, _args: argparse.Namespace) -> int:
        servers = SuryaServers()
        servers.stop_all()
        return JsonLine.emit({"stopped": servers.stopped_pids})

    def status(self, _args: argparse.Namespace) -> int:
        missing = LibraryPdfs().without_body()
        for pdf in missing:
            print(pdf.name)
        print(f"{len(missing)} library PDFs lack a corpus file body", file=sys.stderr)
        return EXIT_OK

    def cache_check(self, _args: argparse.Namespace) -> int:
        conversions = CachedConversions().with_empty_pages()
        JsonOutput().emit({"count": len(conversions), "conversions": conversions})
        return EXIT_OK

    def costs(self, args: argparse.Namespace) -> int:
        order = CheapestFirst.for_backfill(BACKFILL_DIR, directories=(vault.INBOX_DIR, vault.LIBRARY_DIR))
        return JsonLine.emit({"state": "costed", "costs": {pdf: order.cost(pdf).as_list() for pdf in args.pdfs}})

    def drive_queue(self, args: argparse.Namespace) -> int:
        return BackfillCommands().queue(args)

    def drive_prep(self, args: argparse.Namespace) -> int:
        return BackfillCommands().prep(args)

    def drive_trial(self, args: argparse.Namespace) -> int:
        return BackfillCommands().trial(args)

    def drive_cleanup(self, args: argparse.Namespace) -> int:
        return BackfillCommands().cleanup(args)

    def drive_retrial(self, args: argparse.Namespace) -> int:
        return BackfillCommands().retrial(args)

    def drive_fonts_checked(self, args: argparse.Namespace) -> int:
        return BackfillCommands().fonts_checked(args)


    def drive_wait(self, args: argparse.Namespace) -> int:
        return BackfillCommands().wait(args)

    def drive_run(self, args: argparse.Namespace) -> int:
        return BackfillCommands().run(args)


class CommandLine:
    def parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="extract.py",
                                         description="Stage 2: write the body of a filed PDF's corpus file.")
        subparsers = parser.add_subparsers(dest="command", required=True)
        self._add_probe(subparsers)
        self._add_convert(subparsers)
        self._add_layer_sample(subparsers)
        self._add_scope(subparsers)
        self._add_extract(subparsers)
        CorrectionOptions().add(subparsers)
        self._add_accept(subparsers)
        self._add_regress(subparsers)
        self._add_record(subparsers)
        self._add_labels(subparsers)
        self._add_listings(subparsers)
        subparsers.add_parser("stop-servers", help="stop the engine's model servers, once, at the end of a batch")
        subparsers.add_parser("reap-servers", help="wait for the engine's model servers to fall idle, then stop them")
        self._add_prefetch(subparsers)
        self._add_drive(subparsers)
        return parser

    @staticmethod
    def _add_listings(subparsers) -> None:
        subparsers.add_parser("status", help="list library PDFs whose corpus file has no body")
        subparsers.add_parser("review-status", help="list library PDFs whose corpus file body is not yet reviewed")
        subparsers.add_parser("cache-check", help="read-only: list each cached conversion holding a page with no "
                                                  "block, the most empty first")
        costs = subparsers.add_parser("costs", help="each PDF's engine cost, its predicted pixel pages and its page "
                                                    "count, null where its PDF does not open; one JSON line")
        costs.add_argument("pdfs", nargs="+", metavar="pdf", help="an inbox or library filename")

    def _add_prefetch(self, subparsers) -> None:
        prefetch = subparsers.add_parser("prefetch",
                                         help="convert the backfill queue's works into the engine's cache, the "
                                              "cheapest first, yielding the engine to every other conversion; writes only "
                                              "into the scratch directory")
        prefetch.add_argument("--works", type=positive_count, default=None, metavar="N",
                              help="stop after converting N works (default: walk the whole queue)")
        prefetch.add_argument("--keys", type=positive_count, nargs="+", default=[], metavar="KEY",
                              help="walk only the works listed under these keys, each a line number of the queue "
                                   "(default: every work of the queue)")
        prefetch.add_argument("--await-fonts", action="store_true",
                              help="wait for each work whose font repair is unsettled, and convert it once the "
                                   "repair settles how it is read (default: skip it)")

    def _add_drive(self, subparsers) -> None:
        subparsers.add_parser("drive-queue", help="write the PDFs `status` lists to the backfill queue; one JSON line")
        for step, does in DRIVE_STEPS.items():
            drive = subparsers.add_parser(f"drive-{step}", help=f"backfill: {does}; one JSON line")
            drive.add_argument("index", type=work_key_or_basename, metavar="work",
                               help="the work's key in the run's listing, or its library basename")
        self._add_prep_records(subparsers.choices["drive-prep"])
        self._add_pixels_only(subparsers.choices["drive-fonts-checked"])
        wait = subparsers.add_parser("drive-wait", help="backfill: wait for the work's running step; one JSON line")
        wait.add_argument("index", type=work_key_or_basename, metavar="work",
                          help="the work's key in the run's listing, or its library basename")
        run = subparsers.add_parser(RUN_COMMAND, help="internal: the detached child of an engine step")
        run.add_argument("step", choices=ENGINE_STEPS)
        run.add_argument("index", type=work_key_or_basename, metavar="work")

    def _add_prep_records(self, prep: argparse.ArgumentParser) -> None:
        prep.add_argument("--cleanup", action="store_true",
                          help="record that the work's trial goes through the cleanup before it is accepted; "
                               "without it, record that it does not")
        prep.add_argument("--fonts-checked", action="store_true",
                          help="first record that the work's font repair is done, as drive-fonts-checked does")
        self._add_pixels_only(prep)
        prep.add_argument("--one-chapter", action="store_true",
                          help="first record that the work's pages print no heading the bookmarker found, so that "
                               "the work is extracted as one chapter without an outline")

    @staticmethod
    def _add_pixels_only(step: argparse.ArgumentParser) -> None:
        reading = step.add_mutually_exclusive_group()
        reading.add_argument("--pixels-only", action="store_true",
                             help="record that the font repair cannot settle the work's codes, so that every "
                                  "conversion of the work reads its pages from pixels")
        reading.add_argument("--pixel-pages", type=Path, default=None, metavar="LISTING",
                             help="record that the font repair cannot settle the work's codes, so that every "
                                  "conversion of the work reads from pixels the pages the listing, the "
                                  "pixel-pages.json the font repair wrote, names")

    def _add_probe(self, subparsers) -> None:
        probe = subparsers.add_parser("probe", help="read-only: the text layer, the outline, the note's state")
        probe.add_argument("pdf", help=_PDF_HELP)

    def _add_convert(self, subparsers) -> None:
        convert = subparsers.add_parser("convert",
                                        help="run the engine over the PDF into the cache the scope listing and "
                                             "extract read; writes only into the scratch directory")
        convert.add_argument("pdf", help=_PDF_HELP)
        convert.add_argument(FORCE_OCR_FLAG, action="store_true", help="read every page from pixels (a scanned book)")
        self._add_forced_pages(convert)
        convert.add_argument("--fresh", action="store_true", help="ignore the cached engine output")

    @staticmethod
    def _add_layer_sample(subparsers) -> None:
        sample = subparsers.add_parser("layer-sample",
                                       help="a scan: read sample pages of each run of chapters from pixels, compare "
                                            "them with the text layer, and print the flags that read from pixels "
                                            "every run the layer does not match; writes only into the scratch "
                                            "directory")
        sample.add_argument("pdf", help=_PDF_HELP)

    @staticmethod
    def _add_forced_pages(command: argparse.ArgumentParser) -> None:
        command.add_argument(FORCE_OCR_PAGES_FLAG, default=None, metavar="RANGES",
                             help="file pages to read from pixels, as 12-40,55-60")

    def _add_scope(self, subparsers) -> None:
        scope = subparsers.add_parser("scope", help="read-only: list the pages the section scoper judges, with the "
                                                    "runs of pages the cached engine output labels")
        scope.add_argument("pdf", help=_PDF_HELP)
        scope.add_argument("--page", type=positive_count, action="append", default=[], metavar="FILE_PAGE",
                           help="a file page to list besides the pages the listing names; repeatable")

    def _add_extract(self, subparsers) -> None:
        extract = subparsers.add_parser("extract", help="convert the PDF and write the corpus file's body")
        extract.add_argument("pdf", help=_PDF_HELP)
        excluded = extract.add_mutually_exclusive_group()
        excluded.add_argument("--exclude", action="append", nargs=2, default=None, metavar=("START", "RESUME"),
                              help="a span the body leaves out, from START up to RESUME; each point is 'end', "
                                   "'FILE_PAGE', or 'FILE_PAGE: opening words of one line'; repeatable")
        excluded.add_argument("--exclude-nothing", action="store_true", help="the body leaves nothing out")
        extract.add_argument("--readings", default=None,
                             help="JSON list of worker readings: {page, text} or {page, unreadable: true}")
        extract.add_argument("--replace", action="store_true", help="rewrite the body when one already exists")
        extract.add_argument(FORCE_OCR_FLAG, action="store_true", help="read every page from pixels (a scanned book)")
        self._add_forced_pages(extract)
        extract.add_argument("--fresh", action="store_true", help="ignore the cached engine output")
        extract.add_argument("--trial", action="store_true",
                             help="write the body as a trial in the scratch directory, for review, not into the "
                                  "corpus file")

    def _add_accept(self, subparsers) -> None:
        accept = subparsers.add_parser("accept",
                                       help="write the trial's body into the corpus file and mark the work "
                                            "reviewed")
        accept.add_argument("pdf", help=_PDF_HELP)
        accept.add_argument("--replace", action="store_true", help="rewrite the body when a different one exists")

    def _add_record(self, subparsers) -> None:
        record = subparsers.add_parser("record", help="read-only: print the work's extraction record")
        record.add_argument("pdf", help=_PDF_HELP)

    def _add_labels(self, subparsers) -> None:
        labels = subparsers.add_parser("labels",
                                       help="read-only: plan the page labels the corpus file's page markers give the "
                                            "library PDF; with --apply, write them into the PDF")
        labels.add_argument("pdf", help=_PDF_HELP)
        labels.add_argument("--apply", action="store_true", help="write the planned labels into the library PDF")

    def _add_regress(self, subparsers) -> None:
        regress = subparsers.add_parser("regress",
                                        help="rebuild a sample of the reviewed works, or the ones named, and diff "
                                             "each against its corpus file; writes only into the scratch directory")
        regress.add_argument("pdf", nargs="*", help=f"{_PDF_HELP}; none for a sample of the reviewed works")
        regress.add_argument("--sample", type=int, default=SAMPLE_SIZE, metavar="N",
                             help="the sample size: N random reviewed works, taken first from those whose engine "
                                  f"output is cached (default {SAMPLE_SIZE})")
        regress.add_argument("--all", action="store_true", help="every reviewed work; converts each uncached one")
        regress.add_argument("--sample-set", action="store_true",
                             help="the fixed sample set `regress-sample` chose, instead of a random sample")
        regress.add_argument("--baseline", choices=BASELINE_MODES, default=None,
                             help="save: keep each rebuilt body as the baseline, beside the usual diff against the "
                                  "corpus file; compare: diff each rebuilt body against its saved baseline instead")
        sample = subparsers.add_parser("regress-sample",
                                       help="choose the fixed sample set of reviewed works, three or five for each "
                                            "property a work's corpus file and record show, and ten more at random; "
                                            "writes only into the scratch directory")
        sample.add_argument("--seed", type=int, default=DEFAULT_SEED, help="the random choice's seed")
        regress.add_argument("--jobs", type=positive_count, default=DEFAULT_JOBS, metavar="N",
                             help="rebuild from the engine's cache in N processes at once; a work the cache does not "
                                  f"hold is converted afterwards, one at a time (default {DEFAULT_JOBS}, one core "
                                  "short of this machine's)")


def positive_count(raw: str) -> int:
    count = int(raw)
    if count < 1:
        raise argparse.ArgumentTypeError(f"expected a count of at least 1, got {raw}")
    return count


def work_key_or_basename(raw: str) -> int | str:
    return positive_count(raw) if raw.isdigit() else raw


def main(argv: list[str] | None = None) -> int:
    args = CommandLine().parser().parse_args(argv)
    try:
        return getattr(Commands(), args.command.replace("-", "_"))(args)
    except (UsageFailure, vault.NoteChangedOnDisk) as failure:
        print(str(failure), file=sys.stderr)
        return EXIT_USAGE
