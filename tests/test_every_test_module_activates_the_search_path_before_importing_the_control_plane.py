import ast
import tempfile
import unittest
from pathlib import Path

from _support import PROJECT_ROOT, LiveTree

LiveTree.activate()

from _hooks.affected_tests import TEST_MODULE_PATTERN, ModuleIndex

ACTIVATING_CALL = ("LiveTree", "activate")
MODULE_SEPARATOR = "."
FIXTURE_SOURCES = {
    "lib/alpha.py": "ALPHA = 1\n",
    "tests/_support.py": "class LiveTree:\n    pass\n",
    "tests/_fixtures.py": "from _support import LiveTree\n\nLiveTree.activate()\n",
    "tests/test_activated.py": "from _support import LiveTree\n\nLiveTree.activate()\n\nimport alpha\n",
    "tests/test_through_a_fixture.py": "from _fixtures import LiveTree\nimport alpha\n",
    "tests/test_early.py": "import unittest\n\nimport alpha\nfrom _fixtures import LiveTree\n",
}


class ImportOrder:
    def __init__(self, index: ModuleIndex) -> None:
        self._index = index
        self._activating: dict[Path, bool] = {}

    def early_imports(self) -> list[str]:
        test_modules = sorted(self._index.tests_dir.glob(TEST_MODULE_PATTERN))
        return [early for path in test_modules for early in self._walked(path)[1]]

    def _activates(self, path: Path) -> bool:
        if path not in self._activating:
            self._activating[path] = self._walked(path)[0]
        return self._activating[path]

    def _walked(self, path: Path) -> tuple[bool, list[str]]:
        activated = False
        early: list[str] = []
        for statement in ast.parse(path.read_bytes()).body:
            activated = activated or self._is_activation(statement)
            for imported in self._imported_files(statement):
                if imported.parent == self._index.tests_dir:
                    activated = activated or self._activates(imported)
                elif not activated:
                    early.append(f"{path.name}:{statement.lineno}")
        return activated, early

    @staticmethod
    def _is_activation(statement: ast.stmt) -> bool:
        call = statement.value if isinstance(statement, ast.Expr) else None
        function = call.func if isinstance(call, ast.Call) else None
        return (isinstance(function, ast.Attribute) and isinstance(function.value, ast.Name)
                and (function.value.id, function.attr) == ACTIVATING_CALL)

    def _imported_files(self, statement: ast.stmt) -> list[Path]:
        files = (self._index.file_named(name.split(MODULE_SEPARATOR)[0]) for name in self._imported_names(statement))
        return [file for file in files if file is not None]

    @staticmethod
    def _imported_names(statement: ast.stmt) -> list[str]:
        if isinstance(statement, ast.Import):
            return [alias.name for alias in statement.names]
        if isinstance(statement, ast.ImportFrom) and statement.level == 0 and statement.module:
            return [statement.module]
        return []


class TestImportOrderOverAFixtureTree(unittest.TestCase):
    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        for relative, source in FIXTURE_SOURCES.items():
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            (root / relative).write_text(source)
        self.order = ImportOrder(ModuleIndex(root))

    def test_only_a_control_plane_import_before_the_activation_is_named(self):
        self.assertEqual(["test_early.py:3"], self.order.early_imports())


class TestEveryTestModuleRunsAlone(unittest.TestCase):
    def test_no_test_module_imports_the_control_plane_before_it_activates_the_search_path(self):
        self.assertEqual([], ImportOrder(ModuleIndex(PROJECT_ROOT)).early_imports())


if __name__ == "__main__":
    unittest.main()
