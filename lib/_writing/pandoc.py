from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

EXECUTABLE = "pandoc"
INSTALL_COMMAND = "brew install pandoc"
DOCX = "docx"
DRAFT_MARKDOWN = "markdown_strict+footnotes+pipe_tables+tex_math_dollars"
OBSIDIAN_MARKDOWN = "commonmark_x+hard_line_breaks"
CITING_MARKDOWN = "markdown+hard_line_breaks+lists_without_preceding_blankline-yaml_metadata_block"
DEFAULT_REFERENCE = "reference.docx"


class Pandoc:
    def markdown_of(self, docx: Path) -> str:
        arguments = [str(docx), "--from", DOCX, "--to", DRAFT_MARKDOWN, "--wrap=none",
                     "--reference-location=document"]
        return self._run(arguments).decode("utf-8")

    def default_reference(self) -> bytes:
        return self._run(["--print-default-data-file", DEFAULT_REFERENCE])

    def write_docx(self, markdown: str, reference: Path, target: Path) -> None:
        arguments = ["--from", OBSIDIAN_MARKDOWN, "--to", DOCX, "--reference-doc", str(reference),
                     "--output", str(target)]
        self._run(arguments, markdown.encode("utf-8"))

    def write_manuscript(self, markdown: str, target: Path, options: list[str]) -> None:
        self._run(["--from", CITING_MARKDOWN, *options, "--output", str(target)], markdown.encode("utf-8"))

    def _run(self, arguments: list[str], standard_input: bytes | None = None) -> bytes:
        command = [self._executable(), *arguments]
        try:
            return subprocess.run(command, input=standard_input, capture_output=True, check=True).stdout
        except subprocess.CalledProcessError as failure:
            reason = failure.stderr.decode("utf-8", errors="replace").strip()
            raise ValueError(f"pandoc failed on {' '.join(arguments)}: {reason}") from failure

    @staticmethod
    def _executable() -> str:
        found = shutil.which(EXECUTABLE)
        if found is None:
            raise ValueError(f"pandoc is not installed on this machine: run `{INSTALL_COMMAND}`")
        return found
