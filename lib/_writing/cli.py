from __future__ import annotations

import argparse
import json

import vault

from .actions import ProjectCreation, ProjectLink
from .bibliography_placement import BibliographyPlacement
from .board import ABOVE, LEFT_OF, RIGHT_OF
from .board_sync import CARD_KINDS, AnswerArrow, Beside, BoardReading, BoardSync, CardAddition, CardMove, CardText, NotePlacement
from .placement import HeadingLine, StatusChange
from .reading_list import (
    SECTION_BY_KIND, ReadingAddition, ReadingEntry, ReadingListFile, ReadingListRefresh, ReadingListReport,
)
from .project_file import HEADINGS_BY_NAME, QUESTION, STATUSES
from .tree import Project, ProjectTree, WritingFolders

APPLY_HELP = "write; without it, print the plan and write nothing"


class CommandLine:
    def __init__(self) -> None:
        self._parser = argparse.ArgumentParser()
        self._add_commands()

    def run(self, argv: list[str] | None = None) -> None:
        args = self._parser.parse_args(argv)
        try:
            args.handler(args)
        except ValueError as failure:
            raise SystemExit(str(failure)) from failure

    def _add_commands(self) -> None:
        sub = self._parser.add_subparsers(dest="command", required=True)
        self._add_tree(sub)
        self._add_board(sub)
        self._add_sync(sub)
        self._add_card(sub)
        self._add_place(sub)
        self._add_move(sub)
        self._add_answer(sub)
        self._add_readings(sub)
        self._add_reading(sub)
        self._add_new(sub)
        self._add_link(sub)
        self._add_status(sub)
        self._add_add(sub)
        self._add_classify(sub)

    def _add_tree(self, sub) -> None:
        command = sub.add_parser("tree", help="read-only: every project, its parents, children, and drafts")
        command.set_defaults(handler=self._tree)

    def _add_board(self, sub) -> None:
        command = sub.add_parser("board", help="read-only: a project board's notes, other cards, and relations")
        command.add_argument("project", help="the project's name")
        command.set_defaults(handler=self._board)

    def _add_sync(self, sub) -> None:
        command = sub.add_parser("sync", help="bring a project's board and its atomic notes in step")
        command.add_argument("project", help="the project's name")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._sync)

    def _add_card(self, sub) -> None:
        command = sub.add_parser("card", help="add a card to a project's board")
        command.add_argument("project", help="the project's name")
        command.add_argument("kind", choices=CARD_KINDS)
        command.add_argument("text", help="the card's words, or a source's basename")
        command.add_argument("--stated", action="store_true", help="the user stated the card: drawn as accepted")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._card)

    def _add_place(self, sub) -> None:
        command = sub.add_parser("place", help="draw an atomic note's card on a project's board and name the project in the note")
        command.add_argument("note", help="the note's title")
        command.add_argument("project", help="the project's name")
        self._add_sides(command, required=False)
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._place)

    def _add_move(self, sub) -> None:
        command = sub.add_parser("move", help="move a note's card beside another card and redraw its arrows")
        command.add_argument("note", help="the note's title")
        command.add_argument("project", help="the project's name")
        self._add_sides(command, required=True)
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._move)

    def _add_answer(self, sub) -> None:
        command = sub.add_parser("answer", help="draw an arrow from a note's card to the question card the note answers")
        command.add_argument("note", help="the note's title")
        command.add_argument("project", help="the project's name")
        command.add_argument("--question", default=QUESTION, metavar="CARD",
                             help="the card of the question answered; absent, the research question")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._answer)

    @staticmethod
    def _add_sides(command, required: bool) -> None:
        sides = command.add_mutually_exclusive_group(required=required)
        for side in (ABOVE, LEFT_OF, RIGHT_OF):
            sides.add_argument(f"--{side}", metavar="CARD", help=f"the note's title, or Research question, the card stands {side}")

    @staticmethod
    def _beside(args: argparse.Namespace) -> Beside | None:
        named = [(side, getattr(args, side.replace("-", "_"))) for side in (ABOVE, LEFT_OF, RIGHT_OF)]
        return next((Beside(side, anchor) for side, anchor in named if anchor), None)

    def _add_readings(self, sub) -> None:
        command = sub.add_parser("readings", help="a project's reading list by status; --refresh moves the works now held")
        command.add_argument("project", help="the project's name")
        command.add_argument("--refresh", action="store_true", help="plan the wanted entries the library now holds")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._readings)

    def _add_reading(self, sub) -> None:
        command = sub.add_parser("reading", help="add an entry to a project's reading list")
        command.add_argument("project", help="the project's name")
        command.add_argument("kind", choices=sorted(SECTION_BY_KIND))
        command.add_argument("line", help="the entry, as it is to appear")
        command.add_argument("--group", default="", help="the group of held or wanted the entry stands under")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._reading)

    def _add_new(self, sub) -> None:
        command = sub.add_parser("new", help="create a project file")
        command.add_argument("name", help="the project's name; names its project file and its drafts")
        command.add_argument("--parent", help="the project the new one is a child of")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._new)

    def _add_link(self, sub) -> None:
        command = sub.add_parser("link", help="list a project as another's child, on both projects")
        command.add_argument("parent", help="the parent project's name")
        command.add_argument("child", help="the child project's name")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._link)

    def _add_status(self, sub) -> None:
        command = sub.add_parser("status", help="set a project's status")
        command.add_argument("project", help="the project's name")
        command.add_argument("status", choices=STATUSES)
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._status)

    def _add_add(self, sub) -> None:
        command = sub.add_parser("add", help="add a line last under one of a project file's headings")
        command.add_argument("project", help="the project's name")
        command.add_argument("heading", choices=sorted(HEADINGS_BY_NAME))
        command.add_argument("line", help="the line, written as it is to appear")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._add)

    def _add_classify(self, sub) -> None:
        command = sub.add_parser("classify", help="set the field: of an atomic note or a project file")
        command.add_argument("note", help="the atomic note's title or the project's name")
        command.add_argument("bibliographies", nargs="+", help="each bibliography's name; replaces its field:")
        command.add_argument("--apply", action="store_true", help=APPLY_HELP)
        command.set_defaults(handler=self._classify)

    def _tree(self, args: argparse.Namespace) -> None:
        tree = self._projects()
        self._print([ProjectListing(tree, project).as_json() for project in tree.all()])

    def _board(self, args: argparse.Namespace) -> None:
        tree = self._projects()
        self._print(BoardReading(tree.named(args.project), tree.folders).as_json())

    def _sync(self, args: argparse.Namespace) -> None:
        tree = self._projects()
        self._run(BoardSync(tree.named(args.project), tree.folders), args.apply)

    def _card(self, args: argparse.Namespace) -> None:
        card = CardText(args.kind, args.text, proposed=not args.stated)
        self._run(CardAddition(self._projects().named(args.project), card), args.apply)

    def _place(self, args: argparse.Namespace) -> None:
        tree = self._projects()
        self._run(NotePlacement(tree.named(args.project), tree.folders, args.note, self._beside(args)), args.apply)

    def _answer(self, args: argparse.Namespace) -> None:
        self._run(AnswerArrow(self._projects().named(args.project), args.note, args.question), args.apply)

    def _move(self, args: argparse.Namespace) -> None:
        self._run(CardMove(self._projects().named(args.project), args.note, self._beside(args)), args.apply)

    def _readings(self, args: argparse.Namespace) -> None:
        held = [vault.basename_of(path) for path in (*vault.list_corpus_files(), *vault.list_transcripts())]
        file = self._reading_list(args.project)
        if args.refresh:
            self._run(ReadingListRefresh(file, held), args.apply)
        else:
            self._print(ReadingListReport(file, held).as_json())

    def _reading(self, args: argparse.Namespace) -> None:
        self._run(ReadingAddition(self._reading_list(args.project), ReadingEntry(args.kind, args.line, args.group)), args.apply)

    def _reading_list(self, project: str) -> ReadingListFile:
        tree = self._projects()
        return ReadingListFile(tree.folders.reading_lists, tree.named(project).name)

    def _new(self, args: argparse.Namespace) -> None:
        self._run(ProjectCreation(self._projects(), args.name, args.parent), args.apply)

    def _link(self, args: argparse.Namespace) -> None:
        self._run(ProjectLink(self._projects(), args.parent, args.child), args.apply)

    def _status(self, args: argparse.Namespace) -> None:
        self._run(StatusChange(self._projects().named(args.project), args.status), args.apply)

    def _add(self, args: argparse.Namespace) -> None:
        self._run(HeadingLine(self._projects().named(args.project), args.heading, args.line), args.apply)

    def _classify(self, args: argparse.Namespace) -> None:
        chosen = [vault.nfc(name.strip()) for name in args.bibliographies]
        held = {vault.nfc(vault.basename_of(path)) for path in vault.list_bibliographies()}
        self._run(BibliographyPlacement(self._projects(), args.note, chosen, held), args.apply)

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


class ProjectListing:
    def __init__(self, tree: ProjectTree, project: Project) -> None:
        self._tree = tree
        self._project = project

    def as_json(self) -> dict:
        return {"project": self._project.name, "status": self._project.status,
                "field": self._project.read().bibliographies,
                "parents": [parent.name for parent in self._tree.parents(self._project)],
                "children": [child.name for child in self._tree.children(self._project)],
                "one_sided_links": self._tree.one_sided_links(self._project),
                "drafts": [name.basename for name in self._project.drafts.all()]}


def main() -> None:
    CommandLine().run()
