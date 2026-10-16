from __future__ import annotations

import argparse
import json
from pathlib import Path

import vault
import zotero

from _drive.steps import JsonLine

from _file.bib import BibEditor, BibReport
from _file.drive import FileDriver
from _file.filing import Filer, FilingCompletion, note_changed_row, refuses_a_changed_note
from _file.identify import IdentifyReport
from _file.paths import NotePaths, PdfLocator
from _file.preview import FilingPreview
from _file.probe import OpeningPagesDump, PdfProbe
from _file.records import FiledRecordNote
from _file.refile import Refiler, RefileTarget
from _file.relink import Relinker, RelinkReport
from _file.retry import STATUS_ZOTERO_STILL_OFFLINE, PendingDrafts, RetryRunner
from _file.status import DoctorReport, StatusReport

_DESCRIPTION = "Stage 1 -- extract citation metadata, file with Zotero, write the corpus file's frontmatter."

_OPENING_PAGES = 6

_EXIT_FAILURE = 1

_RELINK_NEEDS_ZOTERO = "Zotero is not reachable; relink resolves links through the connector."


def main() -> None:
    args = CommandLine(Commands()).parse()
    try:
        args.func(args)
    except vault.NoteChangedOnDisk as changed:
        Commands().refuse_changed_note(changed)


class Commands:
    def doctor(self, args: argparse.Namespace) -> None:
        self._print(DoctorReport().render())

    def status(self, args: argparse.Namespace) -> None:
        self._print(StatusReport().render())

    def probe(self, args: argparse.Namespace) -> None:
        self._print(PdfProbe().of(self._resolved_pdf(args)))

    def opening(self, args: argparse.Namespace) -> None:
        OpeningPagesDump(self._resolved_pdf(args)).print_pages(args.pages)

    def name(self, args: argparse.Namespace) -> None:
        try:
            print(FilingPreview.of(self._resolved_pdf(args)).library_filename())
        except vault.CreatorMissing as missing:
            self._fail(str(missing))

    def citekey(self, args: argparse.Namespace) -> None:
        print(FilingPreview.of(self._resolved_pdf(args)).citekey())

    def bib(self, args: argparse.Namespace) -> None:
        pdf_path = self._resolved_pdf(args)
        if args.set:
            self._print(BibEditor(pdf_path).apply(args.set))
        else:
            self._print(BibReport(pdf_path).render())

    def identify(self, args: argparse.Namespace) -> None:
        report = IdentifyReport(self._resolved_pdf(args))
        self._print(report.write() if args.write else report.render())

    def file(self, args: argparse.Namespace) -> None:
        NotePaths().ensure_dirs()
        inbox_pdf = PdfLocator().in_inbox(args.pdf)
        completion = FilingCompletion()
        retried = [] if args.only else RetryRunner(completion).resume_unfiled_other_than(inbox_pdf.name)
        filed = [] if refuses_a_changed_note(retried) else [Filer(completion).file(inbox_pdf)]
        self._print({"retried_pending": retried, "filed": filed})
        self._fail_if_refused(retried + filed)

    def drive_card(self, args: argparse.Namespace) -> None:
        JsonLine.emit(FileDriver().card(args.pdf))

    def drive_file(self, args: argparse.Namespace) -> None:
        JsonLine.emit(FileDriver().file(args.pdf))

    def note(self, args: argparse.Namespace) -> None:
        pdf_path = PdfLocator().in_library(args.pdf)
        note = FiledRecordNote(pdf_path)
        try:
            row = note.write() if args.apply else note.preview()
        except vault.NoteChangedOnDisk as changed:
            row = note_changed_row(pdf_path.name, changed)
        self._print(row)
        self._fail_if_refused([row])

    def retry(self, args: argparse.Namespace) -> None:
        if not zotero.is_online():
            self._print({"status": STATUS_ZOTERO_STILL_OFFLINE,
                         "pending_count": PendingDrafts().count()})
            return
        runner = RetryRunner(FilingCompletion())
        rows = runner.run_for(args.only) if args.only else runner.run()
        self._print(rows)
        self._fail_if_refused(rows)

    def refile(self, args: argparse.Namespace) -> None:
        target = RefileTarget(self._resolved_pdf(args).name)
        refiler = Refiler(target, FilingCompletion())
        if not args.allow_incomplete:
            refiler.require_complete_bib()
        if not args.stale_item_deleted:
            self._print(refiler.blocked_report())
            return
        try:
            row = refiler.execute()
        except vault.NoteChangedOnDisk as changed:
            row = refiler.refused_row(changed)
        self._print(row)
        self._fail_if_refused([row])

    def relink(self, args: argparse.Namespace) -> None:
        if not zotero.is_online():
            raise SystemExit(_RELINK_NEEDS_ZOTERO)
        relinker = self._relinker(args)
        rows = relinker.rows()
        report = RelinkReport(rows)
        if args.apply:
            relinker.write(rows)
            self._print(report.render_applied())
        else:
            self._print(report.render())

    def _relinker(self, args: argparse.Namespace) -> Relinker:
        if args.pdf:
            return Relinker([args.pdf])
        return Relinker.over_all_notes()

    def _resolved_pdf(self, args: argparse.Namespace) -> Path:
        return PdfLocator().inbox_or_filed(args.pdf)

    def _print(self, payload: object) -> None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    def _fail(self, error: str) -> None:
        self._print({"error": error})
        raise SystemExit(_EXIT_FAILURE)

    def refuse_changed_note(self, changed: vault.NoteChangedOnDisk) -> None:
        self._print({"error": str(changed), "path": str(changed.path)})
        raise SystemExit(_EXIT_FAILURE)

    def _fail_if_refused(self, rows: list[dict]) -> None:
        if refuses_a_changed_note(rows):
            raise SystemExit(_EXIT_FAILURE)


class Argument:
    def __init__(self, *flags: str, **options: object) -> None:
        self._flags = flags
        self._options = options

    def add_to(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(*self._flags, **self._options)


class Subcommand:
    def __init__(self, name: str, handler: object, arguments: tuple = ()) -> None:
        self._name = name
        self._handler = handler
        self._arguments = arguments

    def register(self, subparsers: object) -> None:
        parser = subparsers.add_parser(self._name)
        for argument in self._arguments:
            argument.add_to(parser)
        parser.set_defaults(func=self._handler)


class CommandLine:
    def __init__(self, commands: Commands) -> None:
        self._subcommands = (self._reading_commands(commands) + self._draft_commands(commands)
                             + self._filing_commands(commands) + self._refiling_commands(commands))

    def _reading_commands(self, commands: Commands) -> tuple:
        return (
            Subcommand("doctor", commands.doctor),
            Subcommand("probe", commands.probe, (Argument("pdf"),)),
            Subcommand("opening", commands.opening, (
                Argument("pdf"),
                Argument("--pages", type=int, default=_OPENING_PAGES,
                         help=f"How many opening pages to dump (default {_OPENING_PAGES})"),
            )),
            Subcommand("name", commands.name, (Argument("pdf"),)),
            Subcommand("citekey", commands.citekey, (Argument("pdf"),)),
            Subcommand("status", commands.status),
        )

    def _draft_commands(self, commands: Commands) -> tuple:
        return (
            Subcommand("bib", commands.bib, (
                Argument("pdf"),
                Argument("--set", action="append", metavar="FIELD=VALUE",
                         help="Native Zotero field, or orig_year / aliases / creators (JSON). "
                              "Repeatable. Empty value clears the field."),
            )),
            Subcommand("identify", commands.identify, (
                Argument("pdf"),
                Argument("--write", action="store_true",
                         help="Record the normalized proposal on the draft card (default: print it only)"),
            )),
        )

    def _filing_commands(self, commands: Commands) -> tuple:
        return (
            Subcommand("file", commands.file, (
                Argument("pdf"),
                Argument("--only", action="store_true",
                         help="File the named PDF alone, without the resume pass over the other unfiled draft cards"),
            )),
            Subcommand("retry", commands.retry, (
                Argument("--only", default=None, metavar="PDF",
                         help="Retry the draft card of this inbox PDF alone"),
            )),
            Subcommand("drive-card", commands.drive_card, (Argument("pdf"),)),
            Subcommand("drive-file", commands.drive_file, (Argument("pdf"),)),
            Subcommand("note", commands.note, (
                Argument("pdf"),
                Argument("--apply", action="store_true",
                         help="Write the corpus file's frontmatter (default: print the frontmatter it would carry)"),
            )),
        )

    def _refiling_commands(self, commands: Commands) -> tuple:
        return (
            Subcommand("refile", commands.refile, (
                Argument("pdf"),
                Argument("--stale-item-deleted", action="store_true",
                         help="Confirm the pre-existing Zotero item was deleted by hand"),
                Argument("--allow-incomplete", action="store_true"),
            )),
            Subcommand("relink", commands.relink, (
                Argument("pdf", nargs="?", default=None),
                Argument("--apply", action="store_true",
                         help="Write the resolved links (default: report only)"),
            )),
        )

    def parse(self) -> argparse.Namespace:
        return self._parser().parse_args()

    def _parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description=_DESCRIPTION)
        subparsers = parser.add_subparsers(dest="command", required=True)
        for subcommand in self._subcommands:
            subcommand.register(subparsers)
        return parser
