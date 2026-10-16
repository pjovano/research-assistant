---
name: extract-chapters
description: "Extract chapters — on the user's instruction, list a held volume's chapters, and cut the ones the user names into the inbox as standalone PDFs, each carrying the volume's collected bibliography and endnotes. Runs at Stage 0 when a volume is filed, and on demand at any later time."
allowed-tools: Read, Bash(~/.research-vault/venv/bin/python .claude/skills/extract-chapters/scripts/volumes.py:*)
---

# extract-chapters (run on the user's instruction; no worker)

**A volume is a PDF in `library/volumes/`.** It has no Zotero record and no
corpus file, and its outline is its contents.

**The user chooses every chapter extracted.** NEVER extract a chapter the user
has not named: the orchestrator lists what the volume holds, and the user
answers with the chapters to cut.

**This skill has two triggers, and one procedure.** Stage 0 runs it when it
files a volume; the user runs it on any held volume at any later time. Both
run the procedure below.

**In a batch, a volume waits on the user.** If Stage 0 files a volume during
a batch, `clean.py drive-route --kind volume` runs step 2 and sets the volume
aside with its chapter list as its question. Cut nothing until the user
names the chapters.

**If a command exits non-zero and no row below names its failure, stop and
ask the user**, naming the command and its error.

## Invariants

| Rule | Holds |
| --- | --- |
| Page geometry is never altered | a chapter is a page copy; no page is split, cropped, rotated, or resized |
| The volume is never written | every command reads the volume and writes only into the inbox |
| A chapter carries its references | a cut chapter carries the volume's collected bibliography and endnotes: cut without them it cites nothing, so the citation graph never records what it cites. A per-chapter reference list already lies in the chapter's range; `contents` reports under `apparatus` only what the volume collects at its own level, and `extract` appends only that |
| The inbox is never overwritten | `extract --apply` refuses a destination already there |
| Page numbers are 1-based | `--range`, `--also`, and every `file_pages` name file pages |

## Procedure

Every command is
`~/.research-vault/venv/bin/python .claude/skills/extract-chapters/scripts/volumes.py <subcommand>`.

| # | Step | Command | Does |
| --- | --- | --- | --- |
| 1 | List the volumes | `list` | read-only; every held volume with its page count, its chapter count, and its apparatus; a volume with no outline carries `"outline": "absent"`. Run it when the user names no volume |
| 2 | Read the contents | `contents "<volume>.pdf" [--level N]` | read-only; the volume's chapters, each with its file-page range, and its `apparatus`. `--level` sets the deepest outline level listed as a chapter, and defaults to 1. If `contents` exits 1 reporting no outline, bookmark the volume first: the `toc` commands of `clean-pdfs` locate a PDF in `library/volumes/`; then run `contents` again |
| 3 | Give the user the chapters | — | show the chapter list and ask which to extract. NEVER choose for the user |
| 4 | Plan each cut | `extract "<volume>.pdf" --range <first>-<last> --title "<chapter title>"` | read-only; prints the printed folios of the range's ends, the ranges it would append, the total page count, and the destination |
| 5 | Write each cut | the same command with `--apply` | copies the chapter and the appended ranges into the inbox as `<chapter title>.pdf`, verifies the page count and that the text layer survived, and refuses to overwrite |

**Read step 4's output before running step 5.** If `--apply` exits non-zero,
it has deleted the file it wrote: stop and ask the user.

| Step 4 result | Do |
| --- | --- |
| folios consecutive with the chapter's extent | run step 5 |
| `no printed folio` at either end | confirm the range against `contents`, then run step 5 |
| range past the end, or destination present | fix the range or the title and run step 4 again |
| folios printed but not consecutive with the chapter's extent | stop and ask the user for the range |

## Flags on `extract`

| Flag | Does |
| --- | --- |
| `--also <first>-<last>` | appends one further file-page range; repeatable. For a volume whose collected apparatus its outline does not name |
| `--no-apparatus` | appends nothing the outline named; the chapter is cut alone. Pass it only on the user's instruction |

**A range that already lies inside the chapter is never appended twice.**

## The extracted chapters

**The extracted chapters are the next batch.** Each passes every stage, and
Stage 0 judges it an article. The `pdf-filer` worker instructions state the fields a chapter
cut from a held volume carries.
