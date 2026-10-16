from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from _workflow_source import REQUIRED_VARIABLE, JsRuntime


class AbsentRuntime(JsRuntime):
    def __init__(self) -> None:
        self._name = None


class JsRuntimeRequiredWhereCiRequiresIt(unittest.TestCase):
    def outcome(self, environment: dict) -> unittest.TestResult:
        class RuntimeProbe(unittest.TestCase):
            def test_probe(self) -> None:
                AbsentRuntime().require(self)

        result = unittest.TestResult()
        with patch.dict(os.environ, environment, clear=True):
            RuntimeProbe("test_probe").run(result)
        return result

    def test_a_missing_runtime_fails_the_test_where_ci_requires_one(self) -> None:
        self.assertEqual(1, len(self.outcome({REQUIRED_VARIABLE: "1"}).failures))

    def test_a_missing_runtime_skips_the_test_elsewhere(self) -> None:
        self.assertEqual(1, len(self.outcome({}).skipped))


if __name__ == "__main__":
    unittest.main()
