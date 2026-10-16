from __future__ import annotations

from dataclasses import dataclass

from .atomic_note import NOTE_RELATIONS, TASKS, AtomicNote, Relation
from .board import SIDES, Board
from .board_cards import (
    ANSWERS, GREY, SETTLED, SMALL_TITLE_SIZE, TO_REVIEW, TWO_WAY_RELATIONS, UNRESEARCHED, ArrowFactory, CardFace, CardFactory,
    Point, RelationStyle,
)
from .board_file import BoardFile, BoardState
from .board_sections import LIVE, SectionCardDrawing, SectionCards, map_root
from .claims import CLAIM_MARK, EXPLICATION_MARK, REVIEW_MARK, marked_for_review
from .drafts import MARKDOWN_SUFFIX
from .project_file import (
    ABSTRACT, ADDED, IN_PROJECT, LINE_BREAK, OPEN_QUESTIONS, PROJECT, QUESTION, REMOVED, Change, ProjectFile,
)
from .reading_list import ReadingListFile
from .relations import NoteRelation, RelationLine
from .tree import Project, WritingFolders
from .saved import save_board, save_text

PROJECTS = "projects"
CLAIM_BULLET = "• "
EXPLICATION_BULLET = "   – "
OPEN_TASK = "- [ ]"
Triple = tuple[str, str, str]


class ProjectNotes:
    def __init__(self, folders: WritingFolders, project: str) -> None:
        self._folders = folders
        self._project = project
        files = sorted(folders.notes.glob(f"*{MARKDOWN_SUFFIX}")) if folders.notes.is_dir() else []
        self._notes = {file.stem: AtomicNote(file.read_text(encoding="utf-8")) for file in files}

    def titles(self) -> set[str]:
        return set(self._notes)

    def members(self) -> set[str]:
        return {title for title, note in self._notes.items() if self._project in note.links(PROJECTS)}

    def relations(self, among: set[str]) -> set[Triple]:
        return {(title, relation.kind, relation.target) for title in among & set(self._notes)
                for relation in self._notes[title].relations() if relation.target in among}

    def reviewed_relations(self, among: set[str]) -> set[Triple]:
        return {triple for triple in self.relations(among) if not self._notes[triple[0]].awaits_review()}

    def proposed(self) -> set[Triple]:
        return {(title, relation.kind, relation.target) for title, note in self._notes.items()
                for relation in note.proposed_relations()}

    def face(self, title: str) -> CardFace:
        note = self._notes[title]
        references, tasks = len(note.reference_blocks()), note.lines(TASKS).count(OPEN_TASK)
        return CardFace(title, LINE_BREAK.join(self._bullets(note)),
                        self._footer(references, tasks, note.awaits_review()), self._state(note, references),
                        link=f"[[{title}]]")

    @staticmethod
    def _bullets(note: AtomicNote) -> list[str]:
        lines = [line.removesuffix(REVIEW_MARK) for line in note.claims_block.splitlines() if line.strip()]
        return [EXPLICATION_BULLET + line.strip()[len(CLAIM_MARK):] if line.startswith(EXPLICATION_MARK)
                else CLAIM_BULLET + line[len(CLAIM_MARK):] for line in lines]

    def join(self, title: str) -> None:
        self._write(title, self._notes[title].with_links(PROJECTS, [*self._notes[title].links(PROJECTS), self._project]))

    def leave(self, title: str) -> None:
        kept = [project for project in self._notes[title].links(PROJECTS) if project != self._project]
        self._write(title, self._notes[title].with_links(PROJECTS, kept))

    def relate(self, triple: Triple) -> None:
        NoteRelation(self._folders, triple[0], RelationLine(triple[1], triple[2])).apply()

    def unrelate(self, triple: Triple) -> bool:
        note = self._notes[triple[0]]
        written = note.without_relation(Relation(triple[1], triple[2]))
        if written.text == note.text:
            return False
        self._write(triple[0], written)
        return True

    def _write(self, title: str, note: AtomicNote) -> None:
        self._notes[title] = note
        save_text(self._folders.atomic_note(title), note.text)

    @staticmethod
    def _footer(references: int, tasks: int, to_review: bool) -> str:
        parts = [f"{references} references" if references else "not yet researched",
                 f"{tasks} tasks" if tasks else "", "to review" if to_review else ""]
        return " · ".join(part for part in parts if part)

    @staticmethod
    def _state(note: AtomicNote, references: int) -> str:
        if not references:
            return UNRESEARCHED
        return TO_REVIEW if note.awaits_review() else SETTLED


@dataclass(frozen=True)
class SyncPlan:
    cards_to_add: list[str]
    notes_to_join: list[str]
    notes_to_leave: list[str]
    arrows_to_draw: list[Triple]
    arrows_to_erase: list[Triple]
    relations_to_write: list[Triple]
    relations_to_remove: list[Triple]
    section_cards_to_add: list[str]

    def as_json(self) -> dict:
        return {key: [list(item) if isinstance(item, tuple) else item for item in value]
                for key, value in self.__dict__.items()}


class BoardSync:
    def __init__(self, project: Project, folders: WritingFolders) -> None:
        self._project = project
        self._file = BoardFile(self._held(project))
        self._notes = ProjectNotes(folders, project.name)
        self._board = Board(self._file.elements())
        self._last = self._file.state()
        self._renames = self._renamed_notes()
        self._board = self._board.relinked(self._renames)
        self._last = self._last.renamed(self._renames)
        self._cards = SectionCards(project.name)
        self._reading_list = ReadingListFile(folders.reading_lists, project.name)
        self._planned = self._plan()

    def plan(self) -> dict:
        return {"project": self._project.name, **self._planned.as_json(),
                "cards_to_relink": [list(pair) for pair in self._renames.items()]}

    @staticmethod
    def _held(project: Project) -> str:
        text = project.file.read_text(encoding="utf-8")
        if not text.strip():
            raise ValueError(f"the project file of {project.name!r} is empty: restore it before any sync, "
                             "since a sync would draw a new board in its place")
        return text

    def _renamed_notes(self) -> dict[str, str]:
        lost = [title for title in self._last.notes if title not in self._notes.titles() and self._board.card(title)]
        carded = set(self._board.linked_titles())
        found = sorted(self._notes.members() - carded - set(self._last.notes))
        return {lost[0]: found[0]} if len(lost) == 1 and len(found) == 1 else {}

    def apply(self) -> None:
        plan = self._planned
        for title in plan.notes_to_join:
            self._notes.join(title)
        for title in plan.notes_to_leave:
            self._notes.leave(title)
        kept_inline = [triple for triple in plan.relations_to_remove if not self._notes.unrelate(triple)]
        for triple in plan.relations_to_write:
            self._notes.relate(triple)
        side = ProjectFile(self._markdown_side()).with_changes(self._changes(plan)).text
        self._cards = self._cards.with_contents(self._contents(side))
        board = self._cards.fitted(self._redrawn(plan, kept_inline))
        written = ProjectFile(self._file.written(board.elements, self._state(board), side)).with_defaults()
        save_board(self._project.file, written.text)
        self._reading_list.create_if_absent()

    @staticmethod
    def _changes(plan: SyncPlan) -> list[Change]:
        return [*(Change.of_note(ADDED, title) for title in [*plan.cards_to_add, *plan.notes_to_join]),
                *(Change.of_note(REMOVED, title) for title in plan.notes_to_leave)]

    @staticmethod
    def _contents(markdown_side: str) -> dict[str, str]:
        side = ProjectFile(markdown_side)
        return {QUESTION: side.body(QUESTION), PROJECT: side.body(PROJECT)}

    def _state(self, board: Board) -> BoardState:
        relations = sorted(relation.triple for _, relation in board.arrows() if relation.kind in NOTE_RELATIONS)
        state = BoardState(tuple(sorted(self._members())), tuple(relations), self._last.cards)
        return state.with_cards(self._planned.section_cards_to_add)

    def _plan(self) -> SyncPlan:
        on_board = self._on_board()
        in_notes = self._notes.members()
        last_notes, last_relations = set(self._last.notes), set(self._last.relations)
        members = on_board | (in_notes - last_notes)
        written = self._notes.relations(members)
        drawn = {self._as_written(relation.triple, written) for _, relation in self._board.arrows()
                 if relation.kind in NOTE_RELATIONS and {relation.source, relation.target} <= members}
        reviewed = self._notes.reviewed_relations(members)
        return SyncPlan(sorted(in_notes - on_board - last_notes), sorted(on_board - in_notes),
                        sorted((in_notes - on_board) & last_notes), sorted(reviewed - drawn - last_relations),
                        sorted((drawn - written) & last_relations), sorted(drawn - written - last_relations),
                        sorted((written - drawn) & last_relations), self._cards.unseen(self._board, self._last.cards))

    @staticmethod
    def _as_written(drawn: Triple, written: set[Triple]) -> Triple:
        turned = (drawn[2], drawn[1], drawn[0])
        return turned if drawn[1] in TWO_WAY_RELATIONS and turned in written and drawn not in written else drawn

    def _on_board(self) -> set[str]:
        return set(self._board.linked_titles()) & self._notes.titles()

    def _members(self) -> set[str]:
        return self._on_board() | set(self._planned.cards_to_add)

    def _redrawn(self, plan: SyncPlan, kept_inline: list[Triple]) -> Board:
        board = self._board
        for arrow, relation in board.arrows():
            if relation.triple in plan.arrows_to_erase:
                board = board.without_arrow(arrow)
        board = self._cards.drawn(board, plan.section_cards_to_add)
        for title in plan.cards_to_add:
            face = self._notes.face(title)
            at = board.free_point(self._neighbour(board, title), CardFactory().height(face))
            board = board.with_elements(CardFactory().card(at, face))
        for title in sorted(self._members()):
            board = board.refaced(title, self._notes.face(title))
        return self._with_arrows(board, [*plan.arrows_to_draw, *kept_inline])

    def _with_arrows(self, board: Board, triples: list[Triple]) -> Board:
        proposed = self._notes.proposed()
        for triple in triples:
            source, target = board.card(triple[0]), board.card(triple[2])
            board = board.with_elements(ArrowFactory().arrow(source, target, RelationStyle(triple[1], triple in proposed)))
        return self._restyled(board, proposed)

    @staticmethod
    def _restyled(board: Board, proposed: set[Triple]) -> Board:
        for arrow, relation in board.arrows():
            if relation.kind in NOTE_RELATIONS:
                arrow.update(ArrowFactory.line_style(RelationStyle(relation.kind, relation.triple in proposed)))
        return board

    def _neighbour(self, board: Board, title: str) -> dict | None:
        related = [triple[2] if triple[0] == title else triple[0]
                   for triple in self._notes.relations(self._members()) if title in (triple[0], triple[2])]
        return next((card for other in related if (card := board.card(other))), self._cards.root(board))

    def _old_project_file(self) -> ProjectFile:
        return ProjectFile(self._file.markdown_side)

    def _markdown_side(self) -> str:
        return self._old_project_file().markdown_side(self._project.name)


class BoardReading:
    def __init__(self, project: Project, folders: WritingFolders) -> None:
        self._project = project
        self._sections = project.read()
        self._board = Board(BoardFile(self._sections.text).elements())
        self._notes = ProjectNotes(folders, project.name)

    def as_json(self) -> dict:
        linked = self._board.linked_titles()
        drawn = [{"title": title, "body": body} for title, body in self._board.titled_cards()]
        return {"project": self._project.name,
                "notes": [title for title in linked if title in self._notes.titles()],
                "other_links": [title for title in linked if title not in self._notes.titles()],
                "cards": [*self._section_cards(), *drawn],
                "relations": [list(relation.triple) for _, relation in self._board.arrows()],
                "positions": self._positions(linked)}

    def _positions(self, linked: list[str]) -> dict[str, list[int]]:
        cards = SectionCards(self._project.name)
        boxes = {**{name: cards.card(self._board, name) for name in LIVE},
                 **{title: self._board.card(title) for title in linked}}
        return {name: [round(box[side]) for side in ("x", "y", "width", "height")] for name, box in boxes.items() if box}

    def _section_cards(self) -> list[dict]:
        shown = SectionCards(self._project.name).shown(self._board)
        headings = [*([QUESTION] if QUESTION in shown else []), *(IN_PROJECT if PROJECT in shown else [])]
        return [{"title": heading, "body": self._sections.body(heading)} for heading in headings
                if heading in self._sections.headings()]


@dataclass(frozen=True)
class Beside:
    side: str
    anchor: str

    def __post_init__(self) -> None:
        if self.side not in SIDES:
            raise ValueError(f"a card stands {list(SIDES)} another")

    def point(self, board: Board, project: str, height: float) -> Point:
        box = map_root(board, project) if self.anchor == QUESTION else board.card(self.anchor)
        if box is None:
            raise ValueError(f"the board of {project!r} holds no card of {self.anchor!r}")
        return board.point_beside(box, self.side, height)


class NotePlacement:
    def __init__(self, project: Project, folders: WritingFolders, title: str, beside: Beside | None = None) -> None:
        self._project = project
        self._title = title
        self._beside = beside
        self._notes = ProjectNotes(folders, project.name)
        self._file = BoardFile(project.file.read_text(encoding="utf-8"))
        if title not in self._notes.titles():
            raise ValueError(f"no note named {title!r} in {folders.notes}")
        if Board(self._file.elements()).card(title):
            raise ValueError(f"{title!r} has a card on the board of {project.name!r} already")
        self._at = self._point(Board(self._file.elements()))

    def plan(self) -> dict:
        return {"project": self._project.name, "note": self._title, "at": [round(self._at.x), round(self._at.y)]}

    def apply(self) -> None:
        board = Board(self._file.elements())
        placed = board.with_elements(CardFactory().card(self._at, self._notes.face(self._title)))
        written = ProjectFile(self._file.written(placed.elements, self._file.state()))
        save_board(self._project.file, written.with_changes([Change.of_note(ADDED, self._title)]).text)
        if self._title not in self._notes.members():
            self._notes.join(self._title)

    def _point(self, board: Board) -> Point:
        height = CardFactory().height(self._notes.face(self._title))
        if self._beside:
            return self._beside.point(board, self._project.name, height)
        return board.free_point(map_root(board, self._project.name), height)


class CardMove:
    def __init__(self, project: Project, title: str, beside: Beside) -> None:
        self._project = project
        self._title = title
        self._file = BoardFile(project.file.read_text(encoding="utf-8"))
        self._board = Board(self._file.elements())
        if self._board.card(title) is None:
            raise ValueError(f"the board of {project.name!r} holds no card of {title!r}")
        height = self._board.card(title)["height"]
        self._at = beside.point(self._board.without_card_boxes(title), project.name, height)

    def plan(self) -> dict:
        return {"project": self._project.name, "note": self._title, "to": [round(self._at.x), round(self._at.y)],
                "arrows_to_redraw": [self._board.label_of(arrow) for arrow in self._touching()]}

    def apply(self) -> None:
        touching = [(arrow, RelationStyle(self._board.label_of(arrow), arrow.get("strokeStyle") == "dashed"))
                    for arrow in self._touching()]
        board = self._board
        for arrow, _ in touching:
            board = board.without_arrow(arrow)
        board = board.moved(self._title, self._at)
        for arrow, style in touching:
            tail, head = (board.element(arrow[end]["elementId"]) for end in ("startBinding", "endBinding"))
            board = board.with_elements(ArrowFactory().between(tail, head, style))
        save_board(self._project.file, self._file.written(board.elements, self._file.state()))

    def _touching(self) -> list[dict]:
        bound = self._board.bound_arrows(self._board.card(self._title))
        return [arrow for arrow in bound if all((arrow.get(end) or {}).get("elementId") for end in ("startBinding", "endBinding"))]


class AnswerArrow:
    def __init__(self, project: Project, title: str, question: str = QUESTION) -> None:
        self._project = project
        self._title = title
        self._question = question
        self._file = BoardFile(project.file.read_text(encoding="utf-8"))
        self._board = Board(self._file.elements())
        self._answer = self._card(title)
        self._asked = map_root(self._board, project.name) if question == QUESTION else self._card(question)
        if self._asked is None:
            raise ValueError(f"the board of {project.name!r} holds no card of {question!r}")
        if any(arrow in self._board.bound_arrows(self._asked) and self._board.label_of(arrow) == ANSWERS
               for arrow in self._board.bound_arrows(self._answer)):
            raise ValueError(f"{title!r} answers {question!r} on the board of {project.name!r} already")

    def plan(self) -> dict:
        return {"project": self._project.name, "note": self._title, ANSWERS: self._question}

    def apply(self) -> None:
        drawn = self._board.with_elements(ArrowFactory().between(self._answer, self._asked, RelationStyle(ANSWERS)))
        save_board(self._project.file, self._file.written(drawn.elements, self._file.state()))

    def _card(self, title: str) -> dict:
        card = self._board.card(title)
        if card is None:
            raise ValueError(f"the board of {self._project.name!r} holds no card of {title!r}")
        return card


SECTION_BY_KIND = {"abstract": ABSTRACT, "question": QUESTION, "open-question": OPEN_QUESTIONS}
LISTED_SECTIONS = (QUESTION, OPEN_QUESTIONS)
SOURCE_CARD = "source"
CARD_KINDS = (*SECTION_BY_KIND, SOURCE_CARD)


@dataclass(frozen=True)
class CardText:
    kind: str
    text: str
    proposed: bool = True


class CardAddition:
    def __init__(self, project: Project, card: CardText) -> None:
        if card.kind not in CARD_KINDS or not card.text.strip():
            raise ValueError(f"a card is one of {list(CARD_KINDS)}, and holds words")
        self._addition = SourceCard(project, card) if card.kind == SOURCE_CARD else SectionWords(project, card)

    def plan(self) -> dict:
        return self._addition.plan()

    def apply(self) -> None:
        self._addition.apply()


class SourceCard:
    def __init__(self, project: Project, card: CardText) -> None:
        self._project = project
        self._card = card
        self._file = BoardFile(project.file.read_text(encoding="utf-8"))

    def plan(self) -> dict:
        face = self._face()
        return {"project": self._project.name, "card": face.title, "body": face.body, "link": face.link}

    def apply(self) -> None:
        board = Board(self._file.elements())
        beneath = map_root(board, self._project.name)
        added = board.with_elements(CardFactory().card(board.free_point(beneath), self._face()))
        save_board(self._project.file, self._file.written(added.elements, self._file.state()))

    def _face(self) -> CardFace:
        basename = self._card.text.strip()
        return CardFace(basename, "", state=TO_REVIEW if self._card.proposed else SETTLED, link=f"[[{basename}]]",
                        fill=GREY, title_size=SMALL_TITLE_SIZE)


class SectionWords:
    def __init__(self, project: Project, card: CardText) -> None:
        self._project = project
        self._card = card
        self._heading = SECTION_BY_KIND[card.kind]

    def plan(self) -> dict:
        return {"project": self._project.name, "card": self._heading, "body": self._words(), "link": None}

    def apply(self) -> None:
        written = self._with_words(self._project.read())
        save_board(self._project.file, SectionCardDrawing(written.text, self._project.name).written())

    def _with_words(self, project_file: ProjectFile) -> ProjectFile:
        if self._heading in LISTED_SECTIONS:
            return project_file.with_line_last(self._heading, self._words())
        return project_file.with_block_last(self._heading, self._words())

    def _words(self) -> str:
        text = self._card.text.strip()
        words = marked_for_review(text) if self._card.proposed else text
        return f"{CLAIM_MARK}{words}" if self._heading in LISTED_SECTIONS else words
