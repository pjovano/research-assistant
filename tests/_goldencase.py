from __future__ import annotations

import unittest

from _support import Golden

MAX_REPORTED_MISMATCHES = 5


class GoldenTestCase(unittest.TestCase):
    def assert_matches_golden(self, snapshot) -> None:
        golden = Golden(snapshot.name)
        self.assertTrue(golden.exists(), self._missing_message(golden))
        self._compare(golden.load(), snapshot.build())

    def _missing_message(self, golden) -> str:
        return (f"No golden at {golden.path}. Run: "
                "~/.research-vault/venv/bin/python tests/capture_goldens.py --apply")

    def _compare(self, expected: dict, actual: dict) -> None:
        self.assertEqual(sorted(expected), sorted(actual), "golden key set changed")
        differing = [k for k in expected if expected[k] != actual[k]]
        if differing:
            self.fail(self._report(expected, actual, differing))

    def _report(self, expected: dict, actual: dict, differing: list) -> str:
        lines = [f"{len(differing)} entr(ies) drifted from the golden:"]
        for key in differing[:MAX_REPORTED_MISMATCHES]:
            lines.append(f"  {key}\n    golden: {expected[key]!r}\n    actual: {actual[key]!r}")
        if len(differing) > MAX_REPORTED_MISMATCHES:
            lines.append(f"  ... and {len(differing) - MAX_REPORTED_MISMATCHES} more")
        return "\n".join(lines)
