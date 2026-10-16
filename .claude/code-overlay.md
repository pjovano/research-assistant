# Code overlay — Research Vault

The code overlay is the vault's rules on code, which `clean-code` reads after its own text.

The control plane is the repository this code overlay lives in. Everything `clean-code` states is the standard for all code in the control plane, and it binds a one-line fix as much as a new module. There are no exemptions. The rules below add to the standard for control-plane code only. In the vault, **Fix what you find** overrides `clean-code`'s **Scope of a change**.

**Organize as objects.** In a language with classes, code is organized as classes with encapsulated state, composed rather than inherited. Free functions are permitted in exactly three places: the single entry point of a script, pure functions with no domain state (a formatter, a parser of one value), and the re-exports required by the frozen-name rule below.

**No comments, no docstrings, no defect narratives.** The general list of acceptable comments does not apply in the vault. A comment recounting a past bug is not an explanation of intent; it is a journal entry, and it is deleted. The corrected behaviour is recorded in the test that pins it (see below), not in a comment.

**Fix what you find.** A defect noticed while working on something else gets fixed, not filed. Fix it as its own change with its own suite run, so that a regression in the fix cannot be confused with a regression in the original task.

**Fix the defect class, never the PDF.** The contract's §5 defines the defect class and the special case, and prohibits the special case. In code:

- **Key a condition on a property the code reads from the PDF** (its fonts, its geometry, its outline, its text layer, its producer). NEVER key one on a work's identity: a basename, a title, a creator, a Zotero key, a file page, a page count, or a string quoted from the work.
- **NEVER move a threshold until one PDF passes:** the threshold moves for every PDF. If a threshold changes, the suite pins one built PDF on each side of the new value.
- **PREFER restating the rule the code already applies, so that it covers the defect class, OVER adding a branch beside it.** The branch wins only when the defect class is a property no existing rule reads. A function that gains a branch per batch is a list of special cases.
- **The test that pins the fix builds the defect class in a PDF of its own** and is named for the defect class, never for the work that exposed it.

**Run the test suite before and after every change.** The suite is a characterization suite: it pins current behaviour *including current defects*, so a genuine fix fails an expectation. Two conditions follow:

- **The expectation moves with the fix, in the same change.** The reason is recorded where the standard permits it: rename the test so its name states the corrected behaviour, and state the reason in the change summary (the commit message where version control exists; otherwise the report to the user). A failing expectation you did not intend to move is a regression; revert it.
- **Never regenerate expectations in bulk** to make a suite go green. That destroys the only record of prior behaviour.

**A name referenced from outside the code is frozen.** Entry-point filenames, subcommand names, and any identifier that appears in configuration or instruction text cannot be renamed by a code-only change, because those callers are not reachable by grepping the code. To restructure such a module, keep its name and have it re-export exactly what it exported before.
