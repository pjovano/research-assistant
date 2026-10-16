from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .linked_note import LinkedNote
from .lzstring import decompress_from_base64

DATA_HEADING = "# Excalidraw Data"
DATA_START_RE = re.compile(r"^(?:# Excalidraw Data|## Text Elements|## Element Links|## Embedded Files|%%\n## Drawing|## Drawing)$",
                           re.MULTILINE)
PLUGIN_WARNING_RE = re.compile(r"^==⚠.*$\n?", re.MULTILINE)
PLUGIN_KEY = "excalidraw-plugin"
PLUGIN_VALUE = "parsed"
TAGS_KEY = "tags"
PLUGIN_TAG = "excalidraw"
COMPRESSED = "compressed-json"
DRAWING_RE = re.compile(r"```(?P<kind>compressed-json|json)\n(?P<block>.*?)\n```", re.DOTALL)
EMBEDDED_FILES_RE = re.compile(r"^## Embedded Files\n.*?(?=^## |^%%)", re.DOTALL | re.MULTILINE)
STATE_RE = re.compile(r"%% board-state\n(?P<state>.*?)\n%%\n*", re.DOTALL)
TEXT_KIND = "text"
LONE_SURROGATE_RE = re.compile("[\ud800-\udfff]")
UNWRITABLE = "\ufffd"


def written_json(payload: dict, **layout) -> str:
    dumped = json.dumps(payload, ensure_ascii=False, **layout)
    return LONE_SURROGATE_RE.sub(lambda lone: f"\\u{ord(lone.group()):04x}", dumped)


BLANK_DRAWING = {"type": "excalidraw", "version": 2, "source": "https://github.com/zsviczian/obsidian-excalidraw-plugin",
                 "elements": [], "appState": {"theme": "light", "viewBackgroundColor": "#ffffff", "gridSize": None},
                 "files": {}}


@dataclass(frozen=True)
class BoardState:
    notes: tuple[str, ...] = ()
    relations: tuple[tuple[str, str, str], ...] = field(default_factory=tuple)
    cards: tuple[str, ...] = ()

    @classmethod
    def read(cls, block: str) -> "BoardState":
        payload = json.loads(block)
        return cls(tuple(payload.get("notes", [])), tuple(tuple(triple) for triple in payload.get("relations", [])),
                   tuple(payload.get("cards", [])))

    def renamed(self, renames: dict[str, str]) -> "BoardState":
        notes = tuple(renames.get(title, title) for title in self.notes)
        relations = tuple((renames.get(source, source), kind, renames.get(target, target))
                          for source, kind, target in self.relations)
        return BoardState(notes, relations, self.cards)

    def with_cards(self, cards: list[str]) -> "BoardState":
        return BoardState(self.notes, self.relations, tuple(sorted({*self.cards, *cards})))

    @property
    def rendered(self) -> str:
        payload = {"notes": list(self.notes), "relations": [list(triple) for triple in self.relations],
                   "cards": list(self.cards)}
        return f"%% board-state\n{written_json(payload)}\n%%"


class BoardFile:
    def __init__(self, text: str) -> None:
        self._note = LinkedNote.parsed(text)
        start = DATA_START_RE.search(self._note.body)
        front = self._note.body[:start.start()] if start else self._note.body
        self._data = self._note.body[start.start():] if start else ""
        self._state_block = STATE_RE.search(front)
        self._front = PLUGIN_WARNING_RE.sub("", STATE_RE.sub("", front)).strip()

    @property
    def markdown_side(self) -> str:
        return self._front

    def drawing(self) -> dict:
        hit = DRAWING_RE.search(self._data)
        if hit is None:
            return json.loads(json.dumps(BLANK_DRAWING))
        block = hit.group("block")
        return json.loads(decompress_from_base64("".join(block.split())) if hit.group("kind") == COMPRESSED else block)

    def elements(self) -> list[dict]:
        return [element for element in self.drawing()["elements"] if not element.get("isDeleted")]

    def state(self) -> BoardState:
        return BoardState.read(self._state_block.group("state")) if self._state_block else BoardState()

    def written(self, elements: list[dict], state: BoardState, markdown_side: str | None = None) -> str:
        front = self._front if markdown_side is None else markdown_side.rstrip()
        body = "\n\n".join(part for part in (state.rendered, front, self._data_section(elements)) if part)
        return self._with_plugin_keys().with_body(body).text

    def _with_plugin_keys(self) -> LinkedNote:
        tags = self._note.meta.get(TAGS_KEY) or []
        tags = [tags] if isinstance(tags, str) else list(tags)
        marked = self._note.with_meta(PLUGIN_KEY, PLUGIN_VALUE)
        return marked if PLUGIN_TAG in tags else marked.with_meta(TAGS_KEY, [*tags, PLUGIN_TAG])

    def _data_section(self, elements: list[dict]) -> str:
        drawing = {**self.drawing(), "elements": elements}
        embedded = EMBEDDED_FILES_RE.search(self._data)
        parts = [DATA_HEADING, self._text_elements(elements), self._element_links(elements),
                 embedded.group(0).rstrip() if embedded else "",
                 f"%%\n## Drawing\n```json\n{written_json(drawing, indent=chr(9))}\n```\n%%"]
        return "\n\n".join(part for part in parts if part)

    @staticmethod
    def _text_elements(elements: list[dict]) -> str:
        texts = [f"{element.get('rawText') or element['text']} ^{element['id']}"
                 for element in elements if element["type"] == TEXT_KIND]
        return LONE_SURROGATE_RE.sub(UNWRITABLE, "\n".join(["## Text Elements", "\n\n".join(texts)]))

    @staticmethod
    def _element_links(elements: list[dict]) -> str:
        links = [f"{element['id']}: {element['link']}"
                 for element in elements if element["type"] != TEXT_KIND and element.get("link")]
        return "\n".join(["## Element Links", "\n\n".join(links)])
