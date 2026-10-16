from __future__ import annotations

import re
import unittest

from _support import PROJECT_ROOT
from _workflow_source import WORKFLOW

AGENTS_DIR = PROJECT_ROOT / ".claude" / "agents"
DISPATCHED_TYPE_RE = re.compile(r"agentType: '([\w-]+)'")
RELAYED_REQUEST_RULE = re.compile(r"If\s+the\s+harness\s+relays\s+a\s+user\s+request\s+before\s+"
                                  r"(?:your\s+prompt|the\s+computed\s+task)")


def dispatched_worker_types() -> set[str]:
    return set(DISPATCHED_TYPE_RE.findall(WORKFLOW.read_text(encoding="utf-8")))


class TestEveryWorkerTheIngestWorkflowDispatchesReadsARelayedRequestAsContext(unittest.TestCase):
    def test_the_workflow_dispatches_workers(self) -> None:
        self.assertIn("work-classifier", dispatched_worker_types())

    def test_each_dispatched_workers_instructions_state_the_rule(self) -> None:
        lacking = sorted(worker for worker in dispatched_worker_types()
                         if not RELAYED_REQUEST_RULE.search((AGENTS_DIR / f"{worker}.md").read_text(encoding="utf-8")))
        self.assertEqual([], lacking)


if __name__ == "__main__":
    unittest.main()
