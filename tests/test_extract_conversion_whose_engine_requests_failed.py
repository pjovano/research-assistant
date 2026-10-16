from __future__ import annotations

import json
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from _extract.build import PageConversion
from _extract.engine import INFERENCE_MANAGER, EngineModels, MarkerEngine
from engine_guard import FailedInferenceRequests, GuardedInferenceManager, SilenceWatch

PDF = Path("work.pdf")
FILE_PAGES = [1, 2]
PAGE_TEXT = "a page the server read"
SILENCE_LIMIT_SECONDS = 60.0
POLL_SECONDS = 0.01


@dataclass(frozen=True)
class Answer:
    raw: str
    error: bool = False


READ_PAGE = Answer(PAGE_TEXT)
FAILED_PAGE = Answer("", error=True)


class ServerAnswering:
    def __init__(self, *rounds: list[Answer]) -> None:
        self._rounds = list(rounds)

    def generate(self, batch: list) -> list[Answer]:
        return self._rounds.pop(0)[:len(batch)]

    def stop(self) -> None:
        return None


class NeverWrittenLogs:
    def last_active(self) -> float | None:
        return None


class IdleServers:
    def stop_all(self) -> None:
        return None


class ModelsOverServer(EngineModels):
    def __init__(self, server: ServerAnswering) -> None:
        super().__init__()
        self._server = server

    def _created(self) -> dict:
        watch = SilenceWatch(NeverWrittenLogs(), SILENCE_LIMIT_SECONDS, POLL_SECONDS)
        return {INFERENCE_MANAGER: GuardedInferenceManager(self._server, watch, IdleServers())}


class RenderedJson:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def model_dump_json(self, exclude: list[str]) -> str:
        return json.dumps(self._payload)


class PageRequestingConverter:
    def __init__(self, artifact_dict: dict, **_construction) -> None:
        self._manager = artifact_dict[INFERENCE_MANAGER]

    def __call__(self, _pdf: str) -> RenderedJson:
        answers = self._manager.generate(FILE_PAGES)
        return RenderedJson({"children": [self._page(answer) for answer in answers]})

    @staticmethod
    def _page(answer: Answer) -> dict:
        children = [{"block_type": "Text", "html": answer.raw}] if answer.raw else []
        return {"block_type": "Page", "children": children}


class OptionsParser:
    def __init__(self, options: dict) -> None:
        self._options = options

    def generate_config_dict(self) -> dict:
        return dict(self._options)

    def get_processors(self) -> list:
        return []

    def get_renderer(self) -> None:
        return None

    def get_llm_service(self) -> None:
        return None


class DictCache:
    def __init__(self) -> None:
        self.held: dict = {}

    def missing(self, file_pages: list[int]) -> list[int]:
        return [] if tuple(file_pages) in self.held else list(file_pages)

    def load(self, file_pages: list[int]) -> dict | None:
        return self.held.get(tuple(file_pages))

    def save(self, file_pages: list[int], payload: dict) -> None:
        self.held[tuple(file_pages)] = payload


def fake_marker_modules() -> dict[str, types.ModuleType]:
    parser = types.ModuleType("marker.config.parser")
    parser.ConfigParser = OptionsParser
    converters = types.ModuleType("marker.converters.pdf")
    converters.PdfConverter = PageRequestingConverter
    return {"marker": types.ModuleType("marker"), "marker.config": types.ModuleType("marker.config"),
            "marker.config.parser": parser, "marker.converters": types.ModuleType("marker.converters"),
            "marker.converters.pdf": converters}


class TestAConversionWhoseEngineRequestsFailed(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.dict(sys.modules, fake_marker_modules())
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cache = DictCache()

    def converted(self, *answers: Answer) -> dict:
        engine = MarkerEngine(ModelsOverServer(ServerAnswering(list(answers))))
        return PageConversion(PDF, engine, self.cache).payload(FILE_PAGES)

    def test_the_conversion_fails_naming_the_failed_requests(self) -> None:
        with self.assertRaisesRegex(FailedInferenceRequests, "1 engine requests failed"):
            self.converted(READ_PAGE, FAILED_PAGE)

    def test_nothing_is_cached(self) -> None:
        with self.assertRaises(FailedInferenceRequests):
            self.converted(FAILED_PAGE, FAILED_PAGE)
        self.assertEqual({}, self.cache.held)

    def test_a_conversion_whose_requests_all_answered_is_cached(self) -> None:
        payload = self.converted(READ_PAGE, READ_PAGE)
        self.assertEqual({tuple(FILE_PAGES): payload}, self.cache.held)

    def test_a_failure_before_this_conversion_does_not_refuse_it(self) -> None:
        models = ModelsOverServer(ServerAnswering([FAILED_PAGE], [READ_PAGE, READ_PAGE]))
        models.inference_manager().generate(["an earlier request"])
        self.assertTrue(MarkerEngine(models).convert(PDF, FILE_PAGES)["children"])


if __name__ == "__main__":
    unittest.main()
