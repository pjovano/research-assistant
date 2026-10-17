from __future__ import annotations

from pathlib import Path

from _support import FIXTURES_DIR

NAMED_WORK = "Roe - 2021 - A Split Sentence"
OLD_ENGINE_LINT = FIXTURES_DIR / "pre-a2-audit" / "lint-rows.json"
COMPARED_ROWS = ("code", "pointers", "works")
PLANE_FILES = {
    "AGENTS.md": (
        "# Contract\n\n"
        "Read `.claude/skills/one/SKILL.md` first, then `.claude/skills/gone/SKILL.md`.\n"
        "Code lives in `lib/engine.py` and `lib/missing.py`; `requirements.txt` pins it.\n"
        "The library holds `library/no-such.pdf` and `research vault/corpus/no such note.md`.\n"
        "Settings sit in `~/no-such-audit-fixture/machine.json`; a note is `<basename>.md`.\n"
        "Decided 2999-01-01 to keep it, and 2001-01-01 to drop it.\n"
        f"If the PDF is `{NAMED_WORK}.pdf`, skip its first page.\n"
    ),
    "CLAUDE.md": "@AGENTS.md\n",
    ".mcp.json": "{}\n",
    ".claude/settings.json": "{}\n",
    ".claude/glossary.md": "| term | `tests/README.md` |\n",
    ".claude/skills/one/SKILL.md": "Run `.claude/skills/one/scripts/run.py`, then `agents/none.md`.\n",
    ".claude/agents/worker.md": f"Never open {NAMED_WORK} first.\n",
    "lib/engine.py": (
        "# a note to the reader\n"
        f'SKIPPED = "{NAMED_WORK}"\n\n\n'
        "def joined(first, second, third, fourth):\n"
        '    """Join them."""\n'
        "    return first\n\n\n"
        "def counted():\n" + "".join(f"    step_{number} = {number}\n" for number in range(25))
    ),
    ".claude/skills/one/server.py": "# serves the stage\nvalue = 1\n",
    ".claude/skills/one/scripts/run.py": "class Run:\n    def go(self):\n        return 1\n",
    "tests/test_one.py": f"# the test of {NAMED_WORK}\nvalue = 1\n",
    "lib/profiles/mac-local.json": "{}\n",
    ".github/actions/empty-vault/action.yml": "name: x\n",
}


class AuditPlane:
    def __init__(self, root: Path) -> None:
        self._root = root

    def built(self) -> Path:
        for name, text in PLANE_FILES.items():
            path = self._root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return self._root
