from __future__ import annotations

import subprocess
import unittest

from _domain_settings import LEDGER_MANIFEST, LOCAL_SETTINGS, CommittedSettings, GeneratedGuards
from _support import PROJECT_ROOT

GUARDED_FOLDER = "~/Documents/taxes"
OWN_SENSITIVE_FOLDER = "~/Documents/library"


class TheGuardsCoverEachSensitiveFolderOfAnotherDomain(unittest.TestCase):
    def test_a_folder_the_domain_does_not_list_gets_a_sandbox_read_denial(self) -> None:
        self.assertEqual([GUARDED_FOLDER], GeneratedGuards(LEDGER_MANIFEST).denied_reads())

    def test_the_folder_gets_a_read_and_an_edit_rule(self) -> None:
        expected = [f"Read({GUARDED_FOLDER}/**)", f"Edit({GUARDED_FOLDER}/**)"]
        self.assertEqual(expected, GeneratedGuards(LEDGER_MANIFEST).denied_rules())

    def test_a_sensitive_folder_the_domain_lists_itself_stays_unguarded(self) -> None:
        self.assertNotIn(OWN_SENSITIVE_FOLDER, GeneratedGuards(LEDGER_MANIFEST).denied_reads())


class TheGuardsNeverEnterGit(unittest.TestCase):
    def test_the_committed_settings_hold_no_permission_denial(self) -> None:
        self.assertNotIn("deny", CommittedSettings.blocks()["permissions"])

    def test_the_committed_settings_hold_no_sandbox_read_denial(self) -> None:
        self.assertNotIn("denyRead", CommittedSettings.blocks()["sandbox"]["filesystem"])

    def test_git_ignores_the_local_settings_file_the_guards_go_into(self) -> None:
        ignored = subprocess.run(["git", "check-ignore", "--no-index", "--quiet", LOCAL_SETTINGS],
                                 cwd=PROJECT_ROOT, capture_output=True, check=False)
        self.assertEqual(0, ignored.returncode)


if __name__ == "__main__":
    unittest.main()
