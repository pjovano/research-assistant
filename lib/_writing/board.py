from __future__ import annotations

import re
from dataclasses import dataclass

from .board_cards import CARD_WIDTH, RELATIONS_FROM_TARGET, CardFace, CardFactory, Point

ARROW, TEXT, EMBEDDABLE = "arrow", "text", "embeddable"
WIKILINK_RE = re.compile(r"^\[\[(?P<target>[^\]|#]+)[^\]]*\]\]$")
GAP = 360
SLOT_HEIGHT = 260
MAX_SLOTS = 400
COLUMNS = 6
ABOVE, LEFT_OF, RIGHT_OF = "above", "left-of", "right-of"
SIDES = (ABOVE, LEFT_OF, RIGHT_OF)
COLUMN_ORDER = (0, 1, -1, 2, -2)
ROWS = 80
MARKDOWN_SUFFIX = ".md"


def link_key(link: str) -> str:
    target = link.strip().removeprefix("[[").removesuffix("]]").split("|")[0]
    name, _, heading = target.partition("#")
    stem = name.rsplit("/", 1)[-1].removesuffix(MARKDOWN_SUFFIX)
    return f"{stem}#{heading}" if heading else stem


@dataclass(frozen=True)
class DrawnRelation:
    source: str
    kind: str
    target: str

    @property
    def triple(self) -> tuple[str, str, str]:
        return self.source, self.kind, self.target


class Board:
    def __init__(self, elements: list[dict]) -> None:
        self._elements = list(elements)
        self._by_id = {element["id"]: element for element in self._elements}

    @property
    def elements(self) -> list[dict]:
        return list(self._elements)

    def linked_titles(self) -> list[str]:
        return list(self._linked())

    def card(self, title: str) -> dict | None:
        return self._linked().get(title)

    def arrows(self) -> list[tuple[dict, DrawnRelation]]:
        drawn = [(arrow, self._relation_of(arrow)) for arrow in self._elements if arrow["type"] == ARROW]
        return [(arrow, relation) for arrow, relation in drawn if relation]

    def titled_cards(self) -> list[tuple[str, str]]:
        frames = [element for element in self._elements
                  if element["type"] == "rectangle" and element.get("groupIds") and not self._title_of(element)]
        return [texts for frame in frames if (texts := self._face_of(frame))]

    def _face_of(self, frame: dict) -> tuple[str, str] | None:
        group = frame["groupIds"][0]
        texts = sorted((element for element in self._elements
                        if element["type"] == TEXT and group in (element.get("groupIds") or [])), key=lambda each: each["y"])
        return (texts[0]["text"], " ".join(texts[1]["text"].split())) if len(texts) > 1 else None

    def embedded_links(self) -> list[str]:
        return [link_key(element["link"]) for element in self._elements
                if element["type"] == EMBEDDABLE and element.get("link")]

    def embedded(self, link: str) -> dict | None:
        return next((element for element in self._elements
                     if element["type"] == EMBEDDABLE and link_key(element.get("link") or "") == link_key(link)), None)

    def with_elements(self, added: list[dict]) -> "Board":
        return Board([*self._elements, *added])

    def bound_arrows(self, box: dict) -> list[dict]:
        return [element for element in self._elements if element["type"] == ARROW
                and box["id"] in ((element.get(end) or {}).get("elementId") for end in ("startBinding", "endBinding"))]

    def label_of(self, arrow: dict) -> str:
        return next((element["text"].strip().lower() for element in self._elements
                     if element["type"] == TEXT and element.get("containerId") == arrow["id"]), "")

    def element(self, element_id: str) -> dict | None:
        return self._by_id.get(element_id)

    def without_arrow(self, arrow: dict) -> "Board":
        gone = {arrow["id"], *(bound["id"] for bound in arrow.get("boundElements") or [])}
        kept = [self._unbound(element, arrow["id"]) for element in self._elements if element["id"] not in gone]
        return Board(kept)

    def relinked(self, renames: dict[str, str]) -> "Board":
        for element in self._elements:
            if element["type"] != ARROW and self._title_of(element) in renames and element.get("link"):
                element["link"] = f"[[{renames[self._title_of(element)]}]]"
        return Board(self._elements)

    def refaced(self, title: str, face: CardFace) -> "Board":
        frame = self.card(title)
        if frame is None or frame["type"] != "rectangle" or not frame.get("groupIds"):
            return self
        group = frame["groupIds"][0]
        factory = CardFactory()
        texts = factory.face_texts(Point(frame["x"], frame["y"]), face, group)
        kept = [element for element in self._elements
                if not (element["type"] == TEXT and group in (element.get("groupIds") or []))]
        frame.update(factory.frame_fields(face, texts, frame["y"]))
        return Board([*kept, *texts])

    def free_point(self, near: dict | None, height: float = SLOT_HEIGHT) -> Point:
        if near is None:
            origin = self._beside_everything()
            slots = (Point(origin.x + column * (CARD_WIDTH + GAP), origin.y + row * (SLOT_HEIGHT + GAP))
                     for row in range(MAX_SLOTS // COLUMNS) for column in range(COLUMNS))
            return next(slot for slot in slots if self._is_free(slot, height))
        trunk = near["x"] + near["width"] / 2 - CARD_WIDTH / 2
        slots = (Point(trunk + column * (CARD_WIDTH + GAP), near["y"] - GAP - height - row * (SLOT_HEIGHT + GAP))
                 for row in range(ROWS) for column in COLUMN_ORDER)
        return next(slot for slot in slots if self._is_free(slot, height))

    def point_beside(self, anchor: dict, side: str, height: float = SLOT_HEIGHT) -> Point:
        if side == ABOVE:
            first, step = Point(anchor["x"] + anchor["width"] / 2 - CARD_WIDTH / 2, anchor["y"] - GAP - height), (0, -1)
        elif side == LEFT_OF:
            first, step = Point(anchor["x"] - GAP - CARD_WIDTH, anchor["y"] + anchor["height"] - height), (-1, 0)
        else:
            first, step = Point(anchor["x"] + anchor["width"] + GAP, anchor["y"] + anchor["height"] - height), (1, 0)
        slots = (Point(first.x + step[0] * turn * (CARD_WIDTH + GAP), first.y + step[1] * turn * (height + GAP))
                 for turn in range(ROWS))
        return next(slot for slot in slots if self._is_free(slot, height))

    def moved(self, title: str, to: Point) -> "Board":
        frame = self.card(title)
        across, down = to.x - frame["x"], to.y - frame["y"]
        group = set(frame.get("groupIds") or [])
        for element in self._elements:
            if element is frame or group & set(element.get("groupIds") or []):
                element["x"] += across
                element["y"] += down
        return Board(self._elements)

    def without_card_boxes(self, title: str) -> "Board":
        frame = self.card(title)
        group = set(frame.get("groupIds") or [])
        return Board([element for element in self._elements
                      if not (element is frame or group & set(element.get("groupIds") or []))])

    def _linked(self) -> dict[str, dict]:
        linked: dict[str, dict] = {}
        for element in self._elements:
            title = self._title_of(element)
            if title and element["type"] not in (ARROW, EMBEDDABLE) and not element.get("containerId"):
                linked.setdefault(title, element)
        return linked

    @staticmethod
    def _title_of(element: dict) -> str | None:
        link = element.get("link") or (element.get("rawText") if element["type"] == TEXT else None)
        hit = WIKILINK_RE.match(link.strip()) if link else None
        return hit.group("target").strip() if hit else None

    def _relation_of(self, arrow: dict) -> DrawnRelation | None:
        ends = [self._card_title((arrow.get(binding) or {}).get("elementId")) for binding in ("startBinding", "endBinding")]
        label = self.label_of(arrow)
        if not all(ends):
            return None
        tail, head = ends
        return DrawnRelation(head, label, tail) if label in RELATIONS_FROM_TARGET else DrawnRelation(tail, label, head)

    def _card_title(self, element_id: str | None) -> str | None:
        element = self._by_id.get(element_id)
        if element is None:
            return None
        groups = set(element.get("groupIds") or [])
        mates = [each for each in self._elements if groups & set(each.get("groupIds") or [])]
        return next((title for each in (element, *mates) if (title := self._title_of(each))), None)

    @staticmethod
    def _unbound(element: dict, arrow_id: str) -> dict:
        bound = [each for each in element.get("boundElements") or [] if each.get("id") != arrow_id]
        return {**element, "boundElements": bound}

    def _boxes(self) -> list[dict]:
        return [element for element in self._elements if element["type"] not in (ARROW, TEXT)]

    def extent(self) -> tuple[Point, Point] | None:
        boxes = self._boxes()
        if not boxes:
            return None
        return (Point(min(box["x"] for box in boxes), min(box["y"] for box in boxes)),
                Point(max(box["x"] + box["width"] for box in boxes), max(box["y"] + box["height"] for box in boxes)))

    def _beside_everything(self) -> Point:
        boxes = self._boxes()
        if not boxes:
            return Point(0, 0)
        return Point(max(box["x"] + box["width"] for box in boxes) + GAP, min(box["y"] for box in boxes))

    def _is_free(self, slot: Point, height: float) -> bool:
        return not any(slot.x < box["x"] + box["width"] + GAP / 2 and box["x"] < slot.x + CARD_WIDTH + GAP / 2
                       and slot.y < box["y"] + box["height"] + GAP / 2 and box["y"] < slot.y + height + GAP / 2
                       for box in self._boxes())
