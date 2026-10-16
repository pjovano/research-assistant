import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _support import PROJECT_ROOT

SETUP_SCRIPT = Path("bin/cloud-setup.sh")
HOOKS_PATH = ".githooks"
NETWORK_STEPS = ("install_pandoc", "build_python_environment", "require_node")
HOST_CHANGING_VARIABLES = ("CCR_AGENT_PROXY_CA_CERT_B64", "NO_PROXY", "no_proxy", "GIT_DIR", "GIT_WORK_TREE",
                           "GIT_COMMON_DIR", "GIT_INDEX_FILE")


class StagedSetup:
    def __init__(self, repository: Path, home: Path) -> None:
        self._repository = repository
        self._home = home
        subprocess.run(["git", "init", "--quiet", str(repository)], check=True, env=self._environment())
        (repository / SETUP_SCRIPT).parent.mkdir(parents=True)
        shutil.copy(PROJECT_ROOT / SETUP_SCRIPT, repository / SETUP_SCRIPT)

    def run_without_the_network_steps(self) -> subprocess.CompletedProcess:
        stubs = "".join(f"{step}() {{ :; }}; " for step in NETWORK_STEPS)
        program = f'source "$1"; {stubs}main'
        return subprocess.run(["bash", "-c", program, "setup", str(self._repository / SETUP_SCRIPT)],
                              capture_output=True, text=True, env=self._environment())

    def hooks_path(self) -> str:
        return subprocess.run(["git", "-C", str(self._repository), "config", "core.hooksPath"],
                              capture_output=True, text=True, env=self._environment()).stdout.strip()

    def _environment(self) -> dict:
        environment = {key: value for key, value in os.environ.items() if key not in HOST_CHANGING_VARIABLES}
        environment["HOME"] = str(self._home)
        return environment


class TestTheCloudSetupUsesTheRepositoryHooks(unittest.TestCase):
    def test_the_setup_points_git_at_the_repository_hooks(self):
        scratch = Path(self.enterContext(tempfile.TemporaryDirectory()))
        setup = StagedSetup(scratch / "repository", scratch / "home")
        result = setup.run_without_the_network_steps()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(HOOKS_PATH, setup.hooks_path())


if __name__ == "__main__":
    unittest.main()
