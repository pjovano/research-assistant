from __future__ import annotations

import sys
from pathlib import Path


def _lib_dir() -> Path:
    here = Path(__file__).resolve()
    return next(parent / "lib" for parent in here.parents if (parent / "lib" / "vault.py").is_file())


sys.path.insert(0, str(_lib_dir()))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _audit.baseline import Baseline
from _audit.cli import AuditSet, CommandLine
from _audit.measures import CodeMeasures
from _audit.pointers import InstructionPointers
from _audit.residue import Residue
from _audit.scope import ControlPlaneFiles

__all__ = ["AuditSet", "Baseline", "CodeMeasures", "CommandLine", "ControlPlaneFiles", "InstructionPointers",
           "Residue"]


if __name__ == "__main__":
    CommandLine().run(sys.argv[1:])
