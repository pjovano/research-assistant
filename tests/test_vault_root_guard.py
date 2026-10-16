from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _support import PROJECT_ROOT, LiveTree

LiveTree.activate()

import vault
from _vault.machine import MachineConfig
from _vault.paths import OBSIDIAN_VAULT_NAME, VAULT_DIR_KEY, ConfiguredVault, VaultRootNotFound

LIB_SOURCE = PROJECT_ROOT / "lib"
PRINT_ROOT = "import vault; print(vault.VAULT_ROOT)"


class TransplantedLibrary:
    def __init__(self, base: Path) -> None:
        self._lib = base / "lib"
        self._home = base / "home"
        self.vault = base / "vault"

    def build(self) -> "TransplantedLibrary":
        self._lib.mkdir(parents=True)
        shutil.copytree(LIB_SOURCE / "_vault", self._lib / "_vault")
        shutil.copy(LIB_SOURCE / "vault.py", self._lib / "vault.py")
        self._home.mkdir(parents=True)
        return self

    def with_obsidian_vault(self, root: Path | None = None) -> "TransplantedLibrary":
        ((root or self.vault) / OBSIDIAN_VAULT_NAME).mkdir(parents=True)
        return self

    def naming_the_vault(self) -> "TransplantedLibrary":
        self.write_machine_config(f'{{"{VAULT_DIR_KEY}": "{self.vault}"}}')
        return self

    @property
    def documents(self) -> Path:
        return self._home / "Documents"

    def import_vault(self) -> subprocess.CompletedProcess:
        return self._run("import vault")

    def printed_root(self) -> str:
        return self._run(PRINT_ROOT).stdout.strip()

    def run_diagnostic(self) -> subprocess.CompletedProcess:
        return self._run(f"import runpy; runpy.run_path(r'{self._lib / 'vault.py'}')")

    def vault_entries(self) -> list[str]:
        return sorted(entry.name for entry in self.vault.iterdir())

    def write_machine_config(self, text: str) -> Path:
        path = self._home / ".research-vault" / "machine.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def _run(self, statement: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-c", f"import sys; sys.path.insert(0, r'{self._lib}'); {statement}"],
            capture_output=True, text=True, env={**os.environ, "HOME": str(self._home)},
        )


class TransplantTestCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.transplanted = TransplantedLibrary(Path(tmp.name)).build()


class TestTheVaultIsTheDirectoryVaultDirNames(TransplantTestCase):
    def test_a_vault_dir_holding_the_obsidian_vault_imports_cleanly(self) -> None:
        self.transplanted.with_obsidian_vault().naming_the_vault()
        result = self.transplanted.import_vault()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_the_root_is_the_named_directory(self) -> None:
        self.transplanted.with_obsidian_vault().naming_the_vault()
        self.assertEqual(str(self.transplanted.vault), self.transplanted.printed_root())

    def test_a_vault_dir_without_the_obsidian_vault_is_rejected_on_import(self) -> None:
        self.transplanted.naming_the_vault()
        result = self.transplanted.import_vault()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("VaultRootNotFound", result.stderr)

    def test_the_rejection_names_the_directory_and_the_key(self) -> None:
        self.transplanted.naming_the_vault()
        stderr = self.transplanted.import_vault().stderr
        self.assertIn(str(self.transplanted.vault), stderr)
        self.assertIn(VAULT_DIR_KEY, stderr)


class TestAnAbsentVaultDirResolvesToDocumentsUnderHome(TransplantTestCase):
    def test_documents_holding_the_obsidian_vault_is_the_root(self) -> None:
        self.transplanted.with_obsidian_vault(self.transplanted.documents)
        self.assertEqual(str(self.transplanted.documents), self.transplanted.printed_root())

    def test_documents_without_the_obsidian_vault_is_rejected_on_import(self) -> None:
        self.assertIn("VaultRootNotFound", self.transplanted.import_vault().stderr)


class TestUnreadableMachineConfigStopsTheScript(TransplantTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.transplanted.with_obsidian_vault()
        self.config = self.transplanted.write_machine_config("{not json")
        self.result = self.transplanted.import_vault()

    def test_the_import_exits_non_zero(self) -> None:
        self.assertNotEqual(0, self.result.returncode)

    def test_the_message_names_the_path_and_the_json_error_without_a_traceback(self) -> None:
        self.assertIn(str(self.config), self.result.stderr)
        self.assertIn("Expecting", self.result.stderr)
        self.assertNotIn("Traceback", self.result.stderr)

    def test_a_valid_config_imports_cleanly(self) -> None:
        self.transplanted.naming_the_vault()
        self.assertEqual(0, self.transplanted.import_vault().returncode)


class TestMachineConfigInProcess(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "machine.json"

    def test_an_absent_file_is_an_empty_config(self) -> None:
        self.assertEqual({}, MachineConfig(self.path).loaded())

    def test_invalid_json_stops_the_script_naming_the_path(self) -> None:
        self.path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(SystemExit) as raised:
            MachineConfig(self.path).loaded()
        self.assertIn(str(self.path), str(raised.exception))

    def test_a_valid_file_is_read_as_a_dict(self) -> None:
        self.path.write_text('{"rag_dir": "~/rag"}', encoding="utf-8")
        self.assertEqual({"rag_dir": "~/rag"}, MachineConfig(self.path).loaded())


class TestConfiguredVaultInProcess(unittest.TestCase):
    def test_the_configured_vault_is_the_live_root(self) -> None:
        self.assertEqual(vault.VAULT_ROOT, ConfiguredVault(vault.MACHINE).resolved())

    def test_the_live_root_holds_the_obsidian_vault(self) -> None:
        self.assertTrue((vault.VAULT_ROOT / OBSIDIAN_VAULT_NAME).is_dir())

    def test_a_configured_directory_without_the_obsidian_vault_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(VaultRootNotFound):
                ConfiguredVault({VAULT_DIR_KEY: tmp}).resolved()


class TestDiagnosticHasNoSideEffects(TransplantTestCase):
    def test_printing_resolved_paths_creates_no_directories(self) -> None:
        self.transplanted.with_obsidian_vault().naming_the_vault()
        before = self.transplanted.vault_entries()
        result = self.transplanted.run_diagnostic()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, self.transplanted.vault_entries())
