from __future__ import annotations

import secrets
import string
import textwrap
from dataclasses import dataclass

FONT = 6
TITLE_FONT = 7
CARD_WIDTH = 520
PADDING = 30
LINE_HEIGHT = 1.35
CHARACTER_WIDTH = 0.5
HANGING_INDENT = "   "
BULLETS = ("•", "–")
TITLE_CHARACTER_WIDTH = 0.6
TITLE_SIZE = 32
SMALL_TITLE_SIZE = 26
BODY_SIZE = 22
FOOTER_SIZE = 16
LABEL_SIZE = 20
ARROW_WIDTH = 4
ARROW_BEND = 0.12
ARROWHEAD = "triangle"
TWO_WAY_RELATIONS = ("contradicts",)
RELATIONS_FROM_TARGET = ("extends", "example of", "presupposes", "descends from")
ANSWERS = "answers"
BLACK, INK, MUTED, FAINT = "#000000", "#212529", "#5c636a", "#adb5bd"
WHITE, WARM, GREY = "#ffffff", "#fffdf0", "#f1f3f5"
RELATION_COLOURS = {"supports": "#2f9e44", "contradicts": "#c92a2a", "extends": "#1971c2",
                    "example of": "#7048e8", "presupposes": "#d9730d", "descends from": "#0c8599"}
SETTLED, TO_REVIEW, UNRESEARCHED = "settled", "review", "open"
ID_ALPHABET = string.ascii_letters + string.digits
ID_LENGTH = 8
ARROW_GAP = 10


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class CardFace:
    title: str
    body: str
    footer: str = ""
    state: str = SETTLED
    link: str | None = None
    fill: str = WHITE
    title_size: int = TITLE_SIZE


@dataclass(frozen=True)
class RelationStyle:
    kind: str
    proposed: bool = False


class ElementFactory:
    def element(self, kind: str, box: tuple[float, float, float, float], **fields) -> dict:
        x, y, width, height = box
        base = {"id": self.new_id(), "type": kind,
                "x": x, "y": y, "width": width, "height": height, "angle": 0, "strokeColor": INK,
                "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
                "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None, "roundness": None,
                "seed": secrets.randbelow(2**31), "version": 1, "versionNonce": secrets.randbelow(2**31),
                "isDeleted": False, "boundElements": [], "updated": 1, "link": None, "locked": False}
        return {**base, **fields}

    @staticmethod
    def new_id() -> str:
        return "".join(secrets.choice(ID_ALPHABET) for _ in range(ID_LENGTH))

    def text(self, at: Point, content: str, size: int, **fields) -> dict:
        lines = content.split("\n")
        width = max(len(line) for line in lines) * size * CHARACTER_WIDTH
        written = {"text": content, "rawText": content, "originalText": content, "fontSize": size, "fontFamily": FONT,
                   "textAlign": "left", "verticalAlign": "top", "containerId": None, "lineHeight": LINE_HEIGHT,
                   "autoResize": True}
        return self.element("text", (at.x, at.y, width, len(lines) * size * LINE_HEIGHT), **{**written, **fields})


class CardFactory:
    def __init__(self) -> None:
        self._elements = ElementFactory()

    def card(self, at: Point, face: CardFace) -> list[dict]:
        group = self._elements.new_id()
        texts = self.face_texts(at, face, group)
        return [self._frame(at, face, texts), *texts]

    def height(self, face: CardFace) -> float:
        return self.card(Point(0, 0), face)[0]["height"]

    def face_texts(self, at: Point, face: CardFace, group: str) -> list[dict]:
        title = self._wrapped(face.title, face.title_size * TITLE_CHARACTER_WIDTH)
        body = self._wrapped(face.body, BODY_SIZE * CHARACTER_WIDTH)
        body_top = at.y + PADDING + self._height(title, face.title_size) + 14
        footer_top = body_top + self._height(body, BODY_SIZE) + 22
        left = at.x + PADDING
        placed = [(Point(left, body_top), body, BODY_SIZE, MUTED),
                  (Point(left, footer_top), face.footer, FOOTER_SIZE, FAINT if face.state == UNRESEARCHED else MUTED)]
        heading = self._elements.text(Point(left, at.y + PADDING), title, face.title_size, strokeColor=BLACK,
                                      fontFamily=TITLE_FONT, groupIds=[group])
        return [heading, *(self._elements.text(point, content, size, strokeColor=colour, groupIds=[group])
                           for point, content, size, colour in placed if content)]

    def frame_fields(self, face: CardFace, texts: list[dict], top: float) -> dict:
        bottom = max(text["y"] + text["height"] for text in texts)
        return {"height": bottom - top + PADDING, "backgroundColor": face.fill, "link": face.link,
                "strokeColor": FAINT if face.state == UNRESEARCHED else INK,
                "strokeStyle": "dashed" if face.state == TO_REVIEW else "solid"}

    def _frame(self, at: Point, face: CardFace, texts: list[dict]) -> dict:
        return self._elements.element("rectangle", (at.x, at.y, CARD_WIDTH, 0), groupIds=texts[0]["groupIds"],
                                      roundness={"type": 3}, **self.frame_fields(face, texts, at.y))

    @staticmethod
    def _wrapped(content: str, character_width: float) -> str:
        per_line = int((CARD_WIDTH - 2 * PADDING) / character_width)
        wrapped = [textwrap.wrap(line, per_line, subsequent_indent=HANGING_INDENT if line.lstrip()[:1] in BULLETS else "")
                   or [""] for line in content.split("\n")]
        return "\n".join(row for rows in wrapped for row in rows) if content else ""

    @staticmethod
    def _height(content: str, size: int) -> float:
        return (content.count("\n") + 1) * size * LINE_HEIGHT if content else 0


class ArrowFactory:
    def __init__(self) -> None:
        self._elements = ElementFactory()

    def arrow(self, source: dict, target: dict, style: RelationStyle) -> list[dict]:
        tail, head = (target, source) if style.kind in RELATIONS_FROM_TARGET else (source, target)
        return self.between(tail, head, style)

    def between(self, tail: dict, head: dict, style: RelationStyle) -> list[dict]:
        start, end = self._edge(tail, head), self._edge(head, tail)
        bend = self._bend(start, end)
        reach = [Point(0, 0), Point(bend.x - start.x, bend.y - start.y), Point(end.x - start.x, end.y - start.y)]
        line = self._elements.element(
            "arrow", (start.x, start.y, self._span([point.x for point in reach]), self._span([point.y for point in reach])),
            points=[[point.x, point.y] for point in reach], lastCommittedPoint=None, roundness={"type": 2},
            startBinding={"elementId": tail["id"], "focus": 0, "gap": ARROW_GAP},
            endBinding={"elementId": head["id"], "focus": 0, "gap": ARROW_GAP},
            strokeColor=RELATION_COLOURS.get(style.kind, INK), **self.line_style(style))
        labels = [self._label(line, style.kind, bend)] if style.kind else []
        line["boundElements"] = [{"type": "text", "id": label["id"]} for label in labels]
        for end_element in (tail, head):
            end_element["boundElements"] = [*(end_element.get("boundElements") or []), {"type": "arrow", "id": line["id"]}]
        return [line, *labels]

    @staticmethod
    def line_style(style: RelationStyle) -> dict:
        return {"strokeWidth": ARROW_WIDTH, "strokeStyle": "dashed" if style.proposed else "solid",
                "startArrowhead": ARROWHEAD if style.kind in TWO_WAY_RELATIONS else None, "endArrowhead": ARROWHEAD}

    @staticmethod
    def _bend(start: Point, end: Point) -> Point:
        across, along = end.x - start.x, end.y - start.y
        return Point((start.x + end.x) / 2 - along * ARROW_BEND, (start.y + end.y) / 2 + across * ARROW_BEND)

    @staticmethod
    def _span(reaches: list[float]) -> float:
        return max(reaches) - min(reaches)

    def _label(self, line: dict, kind: str, middle: Point) -> dict:
        return self._elements.text(Point(middle.x - 40, middle.y - 10), kind, LABEL_SIZE, strokeColor=line["strokeColor"],
                                   containerId=line["id"], textAlign="center", verticalAlign="middle")

    @staticmethod
    def _edge(box: dict, toward: dict) -> Point:
        centre = Point(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        other = Point(toward["x"] + toward["width"] / 2, toward["y"] + toward["height"] / 2)
        if abs(other.x - centre.x) * box["height"] > abs(other.y - centre.y) * box["width"]:
            return Point(box["x"] + (box["width"] + ARROW_GAP if other.x > centre.x else -ARROW_GAP), centre.y)
        return Point(centre.x, box["y"] + (box["height"] + ARROW_GAP if other.y > centre.y else -ARROW_GAP))
