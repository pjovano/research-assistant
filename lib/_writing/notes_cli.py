from __future__ import annotations

import argparse
import json

import vault
from _annotate.palette import TagPalette

from .acceptance import NoteAcceptance
from .chosen_tasks import ChosenTasks
from .claims import MAX_CLAIMS
from .highlight_colours import GROUP_COLOURS, HighlightChoices
from .highlights import NoteHighlighting, PdfHighlights
from .note_check import QUOTATION_RELATIONS, HeldSources, NoteCheck, NoteListing
from .note_lines import ClaimLine, ClaimWording, Explication, NoteFile, NoteTask, ReferenceFraming, ReferenceWriting
from .placement import NoteCreation
from .quotations import CompoundQuotation, HeldQuotations, PdfVerification, QuotationRequest
from .relations import RELATIONS, NoteRelation, RelationLine
from .tree import WritingFolders

APPLY_HELP = "write; without it, print the plan and write nothing"
FINDINGS_EXIT_CODE = 1
DEFAULT_CHOSEN_LIMIT = 8
SOURCE_ROLE = "source_role"


class NotesCommandLine:
    def __init__(self) -> None:
        self._parser = argparse.ArgumentParser()
        sub = self._parser.add_subparsers(dest="command", required=True)
        self._add_note(sub)
        self._add_check(sub)
        self._add_list(sub)
        self._add_claim(sub)
        self._add_explicate(sub)
        self._add_reference(sub)
        self._add_relate(sub)
        self._add_task(sub)
        self._add_highlight(sub)
        self._add_highlights(sub)
        self._add_chosen(sub)
        self._add_accept(sub)

    def run(self, argv: list[str] | None = None) -> None:
        args = self._parser.parse_args(argv)
        try:
            args.handler(args)
        except (ValueError, FileNotFoundError) as failure:
            raise SystemExit(str(failure)) from failure

    def _writing(self, sub, name: str, purpose: str) -> argparse.ArgumentParser:
        command = sub.add_parser(name, help=purpose)
        command.add_argument("title", help="the note's title")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        return command

    def _add_note(self, sub) -> None:
        command = self._writing(sub, "note", "create a blank atomic note: a claim bullet, # References, and # Tasks")
        command.set_defaults(handler=self._note)

    def _add_check(self, sub) -> None:
        command = sub.add_parser("check", help="read-only: an atomic note's counts and each break of its shape")
        command.add_argument("title", help="the note's title")
        command.set_defaults(handler=self._check)

    def _add_list(self, sub) -> None:
        command = sub.add_parser("list", help="read-only: every atomic note with its claims, projects, and counts")
        command.set_defaults(handler=self._list)

    def _add_claim(self, sub) -> None:
        command = self._writing(sub, "claim", "word a claim, marked for review: an existing one, or the next one")
        command.add_argument("number", type=int, choices=range(1, MAX_CLAIMS + 1), help="the claim's number")
        command.add_argument("wording", help="the claim's wording")
        command.set_defaults(handler=self._claim)

    def _add_explicate(self, sub) -> None:
        command = self._writing(sub, "explicate", "add an explication beneath a claim, marked for review")
        command.add_argument("number", type=int, choices=range(1, MAX_CLAIMS + 1), help="the claim's number")
        command.add_argument("explication", help="the explication's words")
        command.set_defaults(handler=self._explicate)

    def _add_reference(self, sub) -> None:
        command = self._writing(sub, "reference", "verify a quotation and write it as a reference, marked for review")
        command.add_argument("source", help="the basename of the corpus file or transcript quoted")
        command.add_argument("relation", choices=QUOTATION_RELATIONS)
        command.add_argument("quotation", help="the quotation, as the corpus file or the transcript writes it")
        command.add_argument("--comment", action="append", default=[], help="one line of the comment; repeat for each line")
        command.add_argument("--after", type=int, help="the number of the reference the new one follows, in its group")
        command.add_argument("--group", default="", help="the group of the references the new one stands last under")
        command.add_argument("--before", default="", help="the held group a group the note lacks is written before")
        command.add_argument("--locator", help="chapter and section, for a corpus file carrying uncitable:")
        command.set_defaults(handler=self._reference)

    def _add_relate(self, sub) -> None:
        command = self._writing(sub, "relate", "add an explication naming another note and the relation to it")
        command.add_argument("relation", choices=RELATIONS)
        command.add_argument("other", help="the title of the note it relates to")
        command.add_argument("gloss", nargs="?", default="", help="how the two notes relate; absent, none")
        command.add_argument("--stated", action="store_true", help="the user stated the relation: no review mark")
        command.set_defaults(handler=self._relate)

    def _add_task(self, sub) -> None:
        command = self._writing(sub, "task", "add a task under # Tasks")
        command.add_argument("task", help="the task, opening with the verb that names what to do")
        command.set_defaults(handler=self._task)

    def _add_highlight(self, sub) -> None:
        command = self._writing(sub, "highlight", "write a highlight into the PDF for each reference of the note")
        command.add_argument("--colour", choices=TagPalette().names,
                             help="a colour the user names for the case, a reserved one among them, for every work not named --generic")
        command.add_argument("--generic", action="append", default=[], metavar="BASENAME",
                             help="a work whose passages state its own core claims and take yellow; repeat per work")
        command.add_argument("--group", choices=GROUP_COLOURS,
                             help="the note's group: blue, theoretical philosophy; green, practical philosophy")
        command.set_defaults(handler=self._highlight)

    def _add_highlights(self, sub) -> None:
        command = sub.add_parser("highlights", help="read-only: every annotation of a library PDF, as JSON")
        command.add_argument("source", help="the PDF's basename")
        command.add_argument("--tag", default="", help="list the annotations carrying this tag alone")
        command.set_defaults(handler=self._highlights)

    def _add_chosen(self, sub) -> None:
        command = sub.add_parser("chosen", help="every checked task of every note, as one JSON line; --apply creates their notes")
        command.add_argument("--limit", type=int, default=DEFAULT_CHOSEN_LIMIT, help="the most further notes taken in one run")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._chosen)

    def _add_accept(self, sub) -> None:
        command = sub.add_parser("accept", help="accept every line marked for review of each note whose accept task is "
                                                "checked, and write the accept task first in each note lacking it")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._accept)

    def _note(self, args: argparse.Namespace) -> None:
        self._run(NoteCreation(self._folders(), args.title), args.apply)

    def _check(self, args: argparse.Namespace) -> None:
        report = NoteCheck(self._folders(), args.title, self._held_sources()).report()
        self._print(report)
        if report["findings"]:
            raise SystemExit(FINDINGS_EXIT_CODE)

    def _list(self, args: argparse.Namespace) -> None:
        self._print(NoteListing(self._folders()).as_json())

    def _claim(self, args: argparse.Namespace) -> None:
        self._run(ClaimWording(self._file(args), ClaimLine(args.number, args.wording)), args.apply)

    def _explicate(self, args: argparse.Namespace) -> None:
        self._run(Explication(self._file(args), ClaimLine(args.number, args.explication)), args.apply)

    def _reference(self, args: argparse.Namespace) -> None:
        file = self._file(args)
        request = QuotationRequest(vault.nfc(args.source), args.quotation, args.locator)
        quotation = CompoundQuotation(HeldQuotations(PdfVerification())).verified(request)
        framing = ReferenceFraming(args.relation, "\n".join(args.comment), args.after, args.group, args.before)
        self._run(ReferenceWriting(file, quotation, framing), args.apply)

    def _relate(self, args: argparse.Namespace) -> None:
        line = RelationLine(args.relation, args.other, args.gloss, proposed=not args.stated)
        self._run(NoteRelation(self._folders(), args.title, line), args.apply)

    def _task(self, args: argparse.Namespace) -> None:
        self._run(NoteTask(self._file(args), args.task), args.apply)

    def _highlight(self, args: argparse.Namespace) -> None:
        choices = HighlightChoices(args.colour, tuple(args.generic), args.group)
        self._run(NoteHighlighting(self._file(args), choices), args.apply)

    def _highlights(self, args: argparse.Namespace) -> None:
        self._print(PdfHighlights(vault.nfc(args.source), args.tag).as_json())

    def _chosen(self, args: argparse.Namespace) -> None:
        self._run_on_one_line(ChosenTasks(self._folders(), args.limit), args.apply)

    def _accept(self, args: argparse.Namespace) -> None:
        self._run_on_one_line(NoteAcceptance(self._folders()), args.apply)

    @staticmethod
    def _held_sources() -> HeldSources:
        corpus_files = vault.list_corpus_files()
        basenames = {vault.nfc(vault.basename_of(path)) for path in (*corpus_files, *vault.list_transcripts())}
        roles = {vault.nfc(vault.basename_of(path)): str(vault.read_frontmatter_only(path).get(SOURCE_ROLE) or "")
                 for path in corpus_files}
        return HeldSources(basenames, roles)

    def _file(self, args: argparse.Namespace) -> NoteFile:
        return NoteFile(self._folders(), args.title)

    def _run(self, action, apply: bool) -> None:
        plan = action.plan()
        if apply:
            action.apply()
        self._print({**plan, "applied": apply})

    @staticmethod
    def _run_on_one_line(action, apply: bool) -> None:
        plan = action.plan()
        if apply:
            action.apply()
        print(json.dumps({**plan, "applied": apply}, ensure_ascii=False))

    @staticmethod
    def _folders() -> WritingFolders:
        return WritingFolders(vault.WRITING_DIR)

    @staticmethod
    def _print(payload: object) -> None:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    NotesCommandLine().run()
