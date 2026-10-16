from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import unittest

from _support import PROJECT_ROOT

WORKFLOWS = PROJECT_ROOT / ".claude" / "workflows"
WORKFLOW = WORKFLOWS / "ingest.js"
RESOLVE_TASKS_WORKFLOW = WORKFLOWS / "resolve-tasks.js"
RUNTIME_ARGUMENTS = {"node": ["-e"], "deno": ["eval"]}
REQUIRED_VARIABLE = "REQUIRE_JS_RUNTIME"
MISSING_RUNTIME = "neither node nor deno is installed"
DECLARATION_START = r"^(?:const|(?:async )?function) {name}\b"
CLOSING_LINE = re.compile(r"^[}\])]")
OPENING_ENDS = ("{", "[", "(")


class WorkflowSource:
    def __init__(self, text: str) -> None:
        self._lines = text.splitlines()

    @classmethod
    def ingest(cls) -> "WorkflowSource":
        return cls(WORKFLOW.read_text(encoding="utf-8"))

    @classmethod
    def resolve_tasks(cls) -> "WorkflowSource":
        return cls(RESOLVE_TASKS_WORKFLOW.read_text(encoding="utf-8"))

    def declarations(self, *names: str) -> str:
        return "\n".join(self._declaration(name) for name in names)

    def _declaration(self, name: str) -> str:
        start = self._start_of(name)
        return "\n".join(self._lines[start:self._end_of(start) + 1])

    def _start_of(self, name: str) -> int:
        pattern = re.compile(DECLARATION_START.format(name=re.escape(name)))
        return next(index for index, line in enumerate(self._lines) if pattern.match(line))

    def _end_of(self, start: int) -> int:
        if not self._lines[start].rstrip().endswith(OPENING_ENDS):
            return start
        return next(index for index in range(start + 1, len(self._lines)) if CLOSING_LINE.match(self._lines[index]))


class JsRuntime:
    def __init__(self) -> None:
        self._name = next((name for name in RUNTIME_ARGUMENTS if shutil.which(name)), None)

    def require(self, test: unittest.TestCase) -> None:
        if self._name is not None:
            return
        if os.environ.get(REQUIRED_VARIABLE):
            test.fail(f"{MISSING_RUNTIME}, and {REQUIRED_VARIABLE} requires one")
        test.skipTest(MISSING_RUNTIME)

    def printed(self, program: str) -> str:
        command = [shutil.which(self._name), *RUNTIME_ARGUMENTS[self._name], program]
        return subprocess.run(command, capture_output=True, text=True, check=True).stdout.strip()

    def value_of(self, source: str, expression: str) -> object:
        return json.loads(self.printed(f"{source}\nconsole.log(JSON.stringify({expression}))"))
