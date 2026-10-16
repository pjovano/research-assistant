from __future__ import annotations

import yaml

from vault import WIKILINK_RE, parse_note

PARENTS = "parents"
CHILDREN = "children"
FIELD = "field"


def wikilink(target: str) -> str:
    return f"[[{target}]]"


class LinkedNote:
    def __init__(self, meta: dict, body: str) -> None:
        self.meta = meta
        self.body = body

    @classmethod
    def parsed(cls, text: str) -> "LinkedNote":
        return cls(*parse_note(text))

    @property
    def text(self) -> str:
        if not self.meta:
            return f"{self.body.strip()}\n"
        header = yaml.safe_dump(self.meta, sort_keys=False, allow_unicode=True)
        return f"---\n{header}---\n\n{self.body.strip()}\n"

    def links(self, field: str) -> list[str]:
        return [hit.group("target").strip() for value in self._values(field)
                for hit in WIKILINK_RE.finditer(str(value))]

    def with_link(self, field: str, target: str) -> "LinkedNote":
        if target in self.links(field):
            return self
        return self.with_meta(field, [*self._values(field), wikilink(target)])

    def with_links(self, field: str, targets: list[str]) -> "LinkedNote":
        return self.with_meta(field, [wikilink(target) for target in targets])

    def with_meta(self, key: str, value: object) -> "LinkedNote":
        return LinkedNote({**self.meta, key: value}, self.body)

    def with_body(self, body: str) -> "LinkedNote":
        return LinkedNote(self.meta, body)

    def _values(self, field: str) -> list:
        value = self.meta.get(field)
        return [value] if isinstance(value, str) else list(value or [])
