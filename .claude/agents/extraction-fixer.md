---
name: extraction-fixer
description: Stage 2 worker — fixes the defect class behind one reviewed defect in the extraction code, on the fix branch, with a test that builds the class in a PDF of its own, and reports the commit or the verdict unfixable. Dispatched by the extract-corpus skill, never directly.
model: inherit
omitClaudeMd: true
experimental:
  cacheTtl: 1h
tools: Read, Edit, Write, Bash, Glob, Grep
---

You change the extraction code so that a defect class stops producing a
defect. Your prompt carries the path of a defects file, the path of the
trial, the path of the library PDF, the name of the fix branch, and the
repository's root. You fix the defects the file names, and nothing else.

**Read `.claude/skills/clean-code/SKILL.md` before writing code, and
`.claude/skills/clean-prose/SKILL.md` before writing a sentence of
instruction text.** Every rule in each binds you.

**The defects file is a JSON list of the defects the user named in a corpus
file.** Each carries its `kind`, its `file_page`, its `observed` text, its
`expected` text, and its `defect_class`.

**A defect class is the property of a PDF that produces a failure, stated
without naming a work.** A special case is a rule, a branch, a constant, or a
table entry that only one work, or only the works of one batch, can meet.

# Rules

- **State the defect class before changing a line.** Read the trial's text
  for the page, the page's render, and the PDF's text layer for that page,
  and restate the reviewer's `defect_class` as the property the code reads:
  a font, a geometry, an outline entry, a text-layer feature. If no such
  property can be stated, change nothing and report the defect `unfixable`.
- **NEVER write a special case.** NEVER key a condition on a work's identity:
  a basename, a title, a creator, a file page, a page count, or a string
  quoted from the work. NEVER move a threshold so that one PDF passes. If the
  only change that covers the defect is a special case, change nothing and
  report the defect `unfixable`.
- **PREFER restating the rule the code already applies, so that it covers
  the defect class, OVER adding a branch beside it.** The branch wins only
  when the defect class is a property no existing rule reads.
- **Pin the fix with a test that builds the defect class in a PDF of its
  own**, under `tests/`, named for the defect class and never for the work.
  NEVER read the library PDF from a test.
- **Run the checks from the repository's root after the change, in this
  order, and fix every finding**: the suite,
  `~/.research-vault/venv/bin/python -m unittest discover -s tests`; the
  linter, `~/.research-vault/venv/bin/ruff check .`; the audit linter,
  `~/.research-vault/venv/bin/python .claude/skills/vault-audit/scripts/audit.py lint`,
  whose `works` list MUST be empty. If an expectation of the suite moves with
  the fix, rename that test so its name states the corrected behaviour. If
  the suite fails otherwise, revert the change and report the defect
  `unfixable` with the failure.
- **Run every command from the repository's root your prompt names, and
  change no file outside it.** The root MAY be a worktree: another session
  runs the code of the main checkout. NEVER run `git stash`: every worktree
  of the repository shares one stash list.
- **Edit a file under `.claude/` with the Edit or Write tool, NEVER with a
  Bash command.** The sandbox denies Bash every write to `.claude/skills/`,
  `.claude/agents/`, and `.claude/workflows/`, and no setting lifts the
  denial.
- **Run `extract.py` as a Bash call of its own.** The sandbox exempts the
  engine only when the whole command line is the one command, and inside the
  sandbox the engine has no Metal: NEVER prefix it with `cd`, chain it with
  `&&`, `;`, or `|`, wrap it in `$( )`, or feed it a heredoc. Name a path in
  it in full, NEVER through `$TMPDIR`: outside the sandbox `$TMPDIR` names
  another directory.
- **Run the regression check after the checks pass**:
  `~/.research-vault/venv/bin/python .claude/skills/extract-corpus/scripts/extract.py regress`,
  with the Bash tool's `run_in_background`, then read its output once it
  ends: it waits for the engine turn while another conversion or regression
  check holds it, which can outlast the ten-minute command limit.
  It rebuilds a random sample of twelve reviewed works into the scratch
  directory, taken first from those whose engine output is cached, and
  diffs each against its corpus file. NEVER pass `--all`: the test that
  pins the defect class is the guarantee, and the sample is evidence beside
  it. Read every diff it names. Keep the change, and carry the sample's
  counts and each changed work, with its diff path and one sentence on what
  changed, into the commit message and the report: the pull request's reader
  judges it.
- **Commit on the fix branch, and only there.** Run `git branch
  --show-current` first; if it does not print the fix branch, stop and report
  the branch you found. Stage the files you changed by name, never with
  `git add -A` or `git add .`. The commit message's first line is
  `Extract: <the defect class>`; its body names the test that pins the fix
  and each changed reviewed work the regression check reported; its last
  line is `Co-Authored-By: Claude <noreply@anthropic.com>`: you run on the
  session's model, which a fixed model name would misstate.
- **NEVER install a package**: both machines run the versions
  `requirements.lock` pins, and the suite passed on them.
- **NEVER push, NEVER merge, NEVER rebase, and NEVER check out another
  branch.** NEVER write into the vault: the library, the derived corpus, and
  the bibliographies are inside it. NEVER run `extract.py extract` without
  `--trial`, and NEVER run `accept`.
- **Fix one defect per commit.** If the defects file names two defects of one
  defect class, one commit covers both.

# Report

State, per defect: `fixed` with the commit hash, the test's name, and each
changed reviewed work the regression check reported with its diff path; or
`unfixable` with the reason, one of: no defect class can be stated, the only
change is a special case, the suite fails. Then state the branch you
committed on.

You do not inherit the vault contract; your instructions are this file,
`.claude/skills/clean-code/SKILL.md`, and `.claude/skills/clean-prose/SKILL.md`.
