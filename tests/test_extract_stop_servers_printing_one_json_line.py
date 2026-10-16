from __future__ import annotations

import contextlib
import io
import json
import unittest
from unittest.mock import patch

from _support import LiveTree

LiveTree.activate()

from _extract.cli import main

STOPPED_PIDS = [111, 222]


class FakeServers:
    stopped_pids = STOPPED_PIDS

    def stop_all(self) -> None:
        pass


class StopServersPrintingOneJsonLine(unittest.TestCase):
    def setUp(self) -> None:
        printed = io.StringIO()
        with patch("_extract.cli.SuryaServers", FakeServers), contextlib.redirect_stdout(printed):
            main(["stop-servers"])
        self.lines = printed.getvalue().splitlines()

    def test_stop_servers_prints_one_line(self) -> None:
        self.assertEqual(1, len(self.lines))

    def test_the_line_names_the_stopped_pids(self) -> None:
        self.assertEqual({"stopped": STOPPED_PIDS}, json.loads(self.lines[-1]))


if __name__ == "__main__":
    unittest.main()
