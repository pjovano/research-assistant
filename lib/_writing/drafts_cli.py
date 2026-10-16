from __future__ import annotations

import argparse
import json
from pathlib import Path

import vault

from .actions import DraftCut, Publication
from .citations import CitationReport, HeldCitekeys
from .conversion import DocxDiscard, DocxImport, InboxDocx, Trash, WordFile
from .docx_style import DEFAULT_STYLE, STYLES
from .manuscript import DOCX, KINDS, ManuscriptExport, ManuscriptFormat
from .pandoc import Pandoc
from .tree import ProjectTree, WritingFolders
from .word_count import DraftWordCount

APPLY_HELP = "write; without it, print the plan and write nothing"


class DraftsCommandLine:
    def __init__(self) -> None:
        self._parser = argparse.ArgumentParser()
        sub = self._parser.add_subparsers(dest="command", required=True)
        self._add_cut(sub)
        self._add_publish(sub)
        self._add_import(sub)
        self._add_discard(sub)
        self._add_export(sub)
        self._add_citations(sub)
        self._add_count(sub)

    def run(self, argv: list[str] | None = None) -> None:
        args = self._parser.parse_args(argv)
        try:
            args.handler(args)
        except ValueError as failure:
            raise SystemExit(str(failure)) from failure

    def _add_cut(self, sub) -> None:
        command = sub.add_parser("cut", help="cut the next version of a draft, copied from the latest")
        command.add_argument("project", help="the project's name")
        command.add_argument("--section", help="the section the draft covers; absent for a whole draft")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._cut)

    def _add_publish(self, sub) -> None:
        command = sub.add_parser("publish", help="copy a project's latest whole draft into the published folder")
        command.add_argument("project", help="the project's name")
        command.add_argument("--title", required=True, help="the published piece's title; names its file")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._publish)

    def _add_import(self, sub) -> None:
        command = sub.add_parser("import", help="convert a .docx of the inbox into a project's next draft version")
        command.add_argument("docx", help="the .docx file's name in the inbox")
        command.add_argument("project", help="the project's name")
        command.add_argument("--section", help="the section the draft covers; absent for a whole draft")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._import)

    def _add_discard(self, sub) -> None:
        command = sub.add_parser("discard", help="move an imported .docx of the inbox to the Trash")
        command.add_argument("docx", help="the .docx file's name in the inbox")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._discard)

    def _add_export(self, sub) -> None:
        command = sub.add_parser("export", help="convert a note of the writing folders into a styled .docx or .pdf")
        command.add_argument("note", help="the basename of a draft, a published piece, or an atomic note")
        command.add_argument("--to", required=True, help="the directory the file is written into")
        command.add_argument("--as", dest="kind", choices=KINDS, default=DOCX)
        command.add_argument("--style", choices=sorted(STYLES), default=DEFAULT_STYLE.name)
        command.add_argument("--csl", help="the name of a citation style of ~/Zotero/styles; absent, pandoc's default")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._export)

    def _add_citations(self, sub) -> None:
        command = sub.add_parser("citations", help="read-only: each citation of a draft, and the held work it names")
        command.add_argument("note", help="the basename of a draft or a published piece")
        command.set_defaults(handler=self._citations)

    def _add_count(self, sub) -> None:
        command = sub.add_parser("count", help="read-only: a draft's words in its body, notes, reference list, and abstract")
        command.add_argument("note", help="the basename of a draft or a published piece")
        command.set_defaults(handler=self._count)

    def _count(self, args: argparse.Namespace) -> None:
        self._print(DraftWordCount(self._projects().folders.note(args.note)).as_json())

    def _cut(self, args: argparse.Namespace) -> None:
        self._run(DraftCut(self._projects().named(args.project), args.section), args.apply)

    def _publish(self, args: argparse.Namespace) -> None:
        self._run(Publication(self._projects(), args.project, args.title), args.apply)

    def _import(self, args: argparse.Namespace) -> None:
        word_file = WordFile(InboxDocx(vault.INBOX_DIR, args.docx).checked(), Pandoc())
        self._run(DocxImport(self._projects().named(args.project), args.section, word_file), args.apply)

    def _discard(self, args: argparse.Namespace) -> None:
        self._run(DocxDiscard(InboxDocx(vault.INBOX_DIR, args.docx).checked(), Trash()), args.apply)

    def _export(self, args: argparse.Namespace) -> None:
        note = self._projects().folders.note(args.note)
        manuscript = ManuscriptFormat(args.kind, STYLES[args.style], args.csl)
        self._run(ManuscriptExport(note, Path(args.to).expanduser(), manuscript), args.apply)

    def _citations(self, args: argparse.Namespace) -> None:
        note = self._projects().folders.note(args.note)
        self._print(CitationReport(note, HeldCitekeys(vault.list_corpus_files()).by_key()).as_json())

    def _run(self, action, apply: bool) -> None:
        plan = action.plan()
        if apply:
            action.apply()
        self._print({**plan, "applied": apply})

    @staticmethod
    def _projects() -> ProjectTree:
        return ProjectTree(WritingFolders(vault.WRITING_DIR))

    @staticmethod
    def _print(payload: object) -> None:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


def main() -> None:
    DraftsCommandLine().run()
