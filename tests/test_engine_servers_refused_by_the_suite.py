from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _engine_refusal import EngineServerRefused
from _support import LiveTree

LiveTree.activate()

from _extract.engine import MarkerEngine
from _vaults import TextPdf



class TestEngineServersRefusedByTheSuite(unittest.TestCase):
    def setUp(self) -> None:
        environment = mock.patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.pdf = TextPdf(Path(directory.name) / "unstubbed.pdf").write()

    def test_a_conversion_no_stub_covers_is_refused_naming_the_test(self) -> None:
        with self.assertRaises(EngineServerRefused) as refused:
            MarkerEngine().convert(self.pdf)
        self.assertIn(self.id(), str(refused.exception))
