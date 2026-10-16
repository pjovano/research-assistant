from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pymupdf
import vault

PLAIN_TEXT = "text"
ENCODING = "utf-8"
KEY_FIELD = "key"
PAYLOAD_FIELD = "payload"


class TextLayerDigest:
    def __init__(self, pdf_path: Path) -> None:
        self._path = pdf_path
        self._value: str | None = None

    def value(self) -> str:
        if self._value is None:
            self._value = self._computed()
        return self._value

    def _computed(self) -> str:
        digest = hashlib.sha256()
        with pymupdf.open(self._path) as doc:
            for page in doc:
                digest.update(page.get_text(PLAIN_TEXT).encode(ENCODING))
        return digest.hexdigest()


class TextLayerKey:
    def __init__(self, digest: TextLayerDigest, stamp: list) -> None:
        self._digest = digest
        self._stamp = stamp

    def value(self) -> list:
        return [*self._stamp, self._digest.value()]


class TextLayerCacheEntry:
    def __init__(self, pdf_path: Path, name: str, key: TextLayerKey) -> None:
        self._path = vault.SCRATCH_DIR / pdf_path.stem / name
        self._key = key

    def load(self) -> object | None:
        try:
            entry = json.loads(self._path.read_text(encoding=ENCODING))
        except (OSError, ValueError):
            return None
        return self._payload_of(entry)

    def save(self, payload: object) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        entry = {KEY_FIELD: self._key.value(), PAYLOAD_FIELD: payload}
        self._path.write_text(json.dumps(entry, ensure_ascii=True), encoding=ENCODING)

    def _payload_of(self, entry: object) -> object | None:
        if not isinstance(entry, dict) or entry.get(KEY_FIELD) != self._key.value():
            return None
        return entry.get(PAYLOAD_FIELD)
