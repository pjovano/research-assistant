from __future__ import annotations

FORBIDDEN_NAME_CHARACTERS = "/\\:[]|#^*\"<>?"
MAX_NAME_BYTES = 200


class NoteName:
    def __init__(self, name: str) -> None:
        self._name = name.strip()

    def checked(self) -> str:
        if not self._name or any(character in self._name for character in FORBIDDEN_NAME_CHARACTERS):
            raise ValueError(f"a name is non-empty and holds none of {FORBIDDEN_NAME_CHARACTERS!r}")
        if len(self._name.encode("utf-8")) > MAX_NAME_BYTES:
            raise ValueError(f"a name runs to at most {MAX_NAME_BYTES} bytes: state the claim more briefly")
        return self._name
