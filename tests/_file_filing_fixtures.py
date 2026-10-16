from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from _support import LiveTree

LiveTree.activate()

import requests
from zotero import ConnectorResult
from _file_fixtures import (
    PDF_BYTES,
    saved_with_key,
)


class FakeResponse:
    def __init__(self, body: dict) -> None:
        self.status_code = HTTPStatus.OK
        self._body = body

    def json(self) -> dict:
        return self._body


class FakeHttp:
    RequestException = requests.RequestException

    def __init__(self, saved_body: dict) -> None:
        self._saved_body = saved_body

    def get(self, url: str, headers: dict = None, timeout: float = None) -> FakeResponse:
        return FakeResponse({})

    def post(self, url: str, headers: dict = None, json: dict = None,
             data: bytes = None, timeout: float = None) -> FakeResponse:
        return FakeResponse(self._saved_body)


class MovingConnector:
    def __init__(self, placed: Path) -> None:
        self._placed = placed

    def save(self, item: dict, pdf: Path) -> ConnectorResult:
        self._placed.write_bytes(PDF_BYTES)
        return saved_with_key()
