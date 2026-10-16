from __future__ import annotations

import unittest
from unittest import mock

from _support import LiveTree

LiveTree.activate()

from _extract.cache import MarkerCache
from _extract.engine import MODE_TEXT_LAYER
from test_extract_review import TRIAL_BODY, ReportingBuild
from test_extract_scope_labels import (
    ALL_PAGES, BASENAME, KINDS_BY_PAGE, CapturedRun, FakeEngine, ScopeVaultCase, engine_payload,
)


class RecordedSessions:
    def __init__(self) -> None:
        self.entered = 0

    def __call__(self) -> RecordedSessions:
        return self

    def __enter__(self) -> RecordedSessions:
        self.entered += 1
        return self

    def __exit__(self, *_exception) -> None:
        return None


class SessionCase(ScopeVaultCase):
    def setUp(self) -> None:
        super().setUp()
        self.sessions = RecordedSessions()

    def cache_every_page(self) -> None:
        MarkerCache(self.pdf, MODE_TEXT_LAYER).save(ALL_PAGES, engine_payload(KINDS_BY_PAGE))

    def converted(self, *flags: str) -> int:
        with mock.patch("_extract.stage.EngineSession", self.sessions), \
                mock.patch("_extract.build.MarkerEngine", FakeEngine):
            CapturedRun(["convert", f"{BASENAME}.pdf", *flags]).go()
        return self.sessions.entered

    def extracted(self) -> int:
        with mock.patch("_extract.stage.EngineSession", self.sessions), \
                mock.patch("_extract.stage.StageCommands.build", return_value=ReportingBuild(TRIAL_BODY)):
            CapturedRun(["extract", f"{BASENAME}.pdf", "--exclude-nothing", "--trial"]).go()
        return self.sessions.entered


class TestTheEngineTurnOfAConversion(SessionCase):
    def test_a_conversion_the_cache_holds_whole_takes_no_engine_turn(self) -> None:
        self.cache_every_page()
        self.assertEqual(0, self.converted())

    def test_a_conversion_the_cache_lacks_takes_the_engine_turn(self) -> None:
        self.assertEqual(1, self.converted())

    def test_a_fresh_conversion_takes_the_engine_turn_though_the_cache_holds_the_work(self) -> None:
        self.cache_every_page()
        self.assertEqual(1, self.converted("--fresh"))

    def test_a_conversion_whose_pages_from_pixels_the_cache_lacks_takes_the_engine_turn(self) -> None:
        self.cache_every_page()
        self.assertEqual(1, self.converted("--force-ocr-pages", "2-3"))


class TestTheEngineTurnOfATrial(SessionCase):
    def test_a_trial_whose_conversion_the_cache_holds_takes_no_engine_turn(self) -> None:
        self.cache_every_page()
        self.assertEqual(0, self.extracted())

    def test_a_trial_whose_conversion_the_cache_lacks_takes_the_engine_turn(self) -> None:
        self.assertEqual(1, self.extracted())


if __name__ == "__main__":
    unittest.main()
