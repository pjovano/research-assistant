from __future__ import annotations

from .board import EMBEDDABLE, Board
from .board_cards import BLACK, TITLE_FONT, WARM, ElementFactory, Point
from .board_file import BoardFile
from .project_file import PROJECT, QUESTION

LIVE = (PROJECT, QUESTION)
TITLE_SIZE = 40
TITLE_BAND = 64
SCALES = {PROJECT: 1.25, QUESTION: 1.5}
WIDTHS = {PROJECT: 600, QUESTION: 900}
MIN_HEIGHT = 150
ROW_HEIGHT = 27
CHARACTER_WIDTH = 8.5
INSET = 28
HEADING_ROWS = 1.8
BLANK_ROWS = 0.5
QUERY_ROWS = 2
FENCE = "```"
GAP = 180
CLEARANCE = 880
SEE_THROUGH = {"useObsidianDefaults": False, "backgroundMatchCanvas": False, "backgroundMatchElement": False,
               "backgroundColor": "#fff", "backgroundOpacity": 0, "borderMatchElement": False, "borderColor": "#fff",
               "borderOpacity": 0, "filenameVisible": False}


def section_link(project: str, heading: str) -> str:
    return f"[[{project}#{heading}]]"


class MarkdownExtent:
    def __init__(self, markdown: str) -> None:
        self._lines = markdown.splitlines()

    def height(self, width: float, scale: float) -> float:
        per_row = max(1, int((width / scale - 2 * INSET) / CHARACTER_WIDTH))
        rows = sum(self._rows(line, per_row) for line in self._shown())
        return max(MIN_HEIGHT, rows * ROW_HEIGHT + 2 * INSET) * scale

    def _shown(self) -> list[str]:
        shown, fenced = [], False
        for line in self._lines:
            if line.startswith(FENCE):
                fenced = not fenced
                shown += [FENCE] if fenced else []
            elif not fenced:
                shown.append(line)
        return shown

    @staticmethod
    def _rows(line: str, per_row: int) -> float:
        if not line.strip():
            return BLANK_ROWS
        if line == FENCE:
            return QUERY_ROWS
        return HEADING_ROWS if line.startswith("#") else -(-len(line) // per_row)


class SectionCards:
    def __init__(self, project: str, contents: dict[str, str] | None = None) -> None:
        self._project = project
        self._links = {heading: section_link(project, heading) for heading in LIVE}
        self._contents = contents or {}

    def with_contents(self, contents: dict[str, str]) -> "SectionCards":
        return SectionCards(self._project, contents)

    def shown(self, board: Board) -> list[str]:
        return [name for name, link in self._links.items() if board.embedded(link)]

    def unseen(self, board: Board, seen: tuple[str, ...]) -> list[str]:
        return [name for name in self._links if name not in seen and name not in self.shown(board)]

    def card(self, board: Board, name: str) -> dict | None:
        return board.embedded(self._links[name])

    def root(self, board: Board) -> dict | None:
        return self.card(board, QUESTION)

    def corner(self, board: Board) -> dict | None:
        return self.card(board, PROJECT)

    def drawn(self, board: Board, names: list[str]) -> Board:
        for name in LIVE:
            if name in names:
                board = board.with_elements(self._card(name, self._place(board, name)))
        return board

    def fitted(self, board: Board) -> Board:
        for name, markdown in self._contents.items():
            card = board.embedded(self._links.get(name, ""))
            if card:
                needed = MarkdownExtent(markdown).height(card["width"], card["scale"][0])
                card["height"] += max(0, needed - card["height"])
        return board

    def _place(self, board: Board, name: str) -> Point:
        corner, root = self.corner(board), self.root(board)
        if name == QUESTION and corner:
            height = MarkdownExtent(self._contents.get(QUESTION, "")).height(WIDTHS[QUESTION], SCALES[QUESTION])
            return Point(corner["x"] + corner["width"] + CLEARANCE, corner["y"] - TITLE_BAND - GAP - height)
        if name == PROJECT and root:
            return Point(root["x"] - CLEARANCE - WIDTHS[PROJECT], root["y"] + root["height"] + GAP + TITLE_BAND)
        extent = board.extent()
        return Point(extent[1].x + GAP, extent[0].y) if extent else Point(0, 0)

    def _card(self, name: str, at: Point) -> list[dict]:
        factory = ElementFactory()
        group = factory.new_id()
        height = MarkdownExtent(self._contents.get(name, "")).height(WIDTHS[name], SCALES[name])
        title = factory.text(Point(at.x, at.y - TITLE_BAND), name, TITLE_SIZE, strokeColor=BLACK, fontFamily=TITLE_FONT,
                             groupIds=[group])
        card = factory.element(EMBEDDABLE, (at.x, at.y, WIDTHS[name], height), link=self._links[name],
                               backgroundColor=WARM, roundness={"type": 3}, scale=[SCALES[name], SCALES[name]],
                               groupIds=[group], customData={"mdProps": dict(SEE_THROUGH)})
        return [title, card]


def map_root(board: Board, project: str) -> dict | None:
    return SectionCards(project).root(board)


class SectionCardDrawing:
    def __init__(self, text: str, project: str) -> None:
        self._file = BoardFile(text)
        self._cards = SectionCards(project)

    def written(self) -> str:
        board, state = Board(self._file.elements()), self._file.state()
        unseen = self._cards.unseen(board, state.cards)
        return self._file.written(self._cards.drawn(board, unseen).elements, state.with_cards(unseen))
