---
name: edit-drafts
description: "Edit drafts — on the user's instruction, edit a draft of the user's writing: check its structure, its sentences, and its terminology, citations, quotations, and language, grade each claim about a source against the passage cited, and report or mark each finding; check a later version against an earlier check; check a draft against the standards the user gives; apply the fixes the user approves to a new version; break the draft into its claims and match each to an atomic note; name the atomic notes the draft leaves unused; export a draft as a .docx or a PDF with its citations and bibliography in a named style; cut, import, and publish drafts."
allowed-tools: Read, Glob, Grep, Edit, Write, Agent, SendUserFile, WebFetch, Bash(~/.research-vault/venv/bin/python .claude/skills/edit-drafts/scripts/drafts.py:*), Bash(~/.research-vault/venv/bin/python .claude/skills/take-notes/scripts/notes.py:*), Bash(~/.research-vault/venv/bin/python .claude/skills/manage-projects/scripts/projects.py:*), Bash(~/.research-vault/venv/bin/python .claude/skills/answer-questions/scripts/verify.py verify:*), Bash(~/.research-vault/venv/bin/python .claude/skills/answer-questions/scripts/verify.py locate:*), mcp__vault-rag__search_hybrid, mcp__vault-rag__get_frontmatter, mcp__vault-rag__list_works, mcp__vault-rag__outline
---

# edit-drafts (Research Retrieval, run by the orchestrator; no worker)

**A draft's prose is the user's.** NEVER change a word of a draft or a
published piece except by "Applying approved fixes", and NEVER change what a
sentence argues. A finding is reported or marked; the user decides.

**NEVER add a fact, a name, a date, a source, or a claim to a draft.** If a
fix needs one, the finding asks the user for it.

**Read `.claude/skills/answer-questions/reference/retrieval.md` before checking a
citation or a quotation.** Its "Rigor" binds every finding about a source.

**If a command exits non-zero and no row below names its failure, stop and
ask the user**, naming the command and its error.

## Vocabulary

| Term | Is |
| --- | --- |
| draft | a file of `research vault/writing/3 drafts/` holding one version of a project's text, or of one section of it |
| whole draft | a draft of the whole project, `<Project> - v<NN>.md` |
| section draft | a draft of one section, `<Project> - <Section> - v<NN>.md`, versioned apart from the whole draft and from every other section |
| version | the two-digit number that closes a draft's name; the latest version is the highest |
| published piece | `research vault/writing/4 published/<Title>.md`, a finished whole draft the user is no longer working on, under a title no project file carries |
| Word file | a `.docx` in the inbox, a draft the user wrote outside the vault, awaiting import |
| citation | a pandoc citation of a draft, `[@<citekey>, <locator>]` or `@<citekey> [<locator>]`, the citekey being the Zotero record's |
| level | one of `structure`, `line`, `copy`, `proof`: the kind of editing a check does, per `reference/checks.md` |
| finding | one thing a check found in a draft: its line, the words it concerns, what is wrong, and the fix proposed or the question asked |
| verdict | the grade of one claim about a source against the passage it cites: `supported`, `partial`, `distorted`, `unsupported`, `inaccessible`, or `not checked` |
| editor's comment | the Obsidian comment `%% editor: <finding> %%`, written on the line after the paragraph the finding concerns |
| export style | the formatting an exported file takes, `submission` or `reading` |
| citation style | a `.csl` file of `~/Zotero/styles/`, named without its suffix, that sets how an export writes its citations and its bibliography |
| coverage | for each claim a draft makes, the atomic note that holds the claim, or none |

## Commands

Every command is
`~/.research-vault/venv/bin/python .claude/skills/edit-drafts/scripts/drafts.py <subcommand>`.
Run each writing form only after reading its read-only form's plan.

| Command | Does |
| --- | --- |
| `citations "<basename>"` | read-only: each citation of the draft with its line, its citekey, its locator, and the corpus file that carries the citekey, and the citekeys held and not held |
| `count "<basename>"` | read-only: the draft's words in its body, its notes, its reference list, and its abstract, and their total, without its frontmatter and its Obsidian comments |
| `cut "<Project>" [--section "<Section>"] [--apply]` | writes the next version into `writing/3 drafts/`, copied from the latest version of the same whole draft or section, or empty if there is none, and links it first under the project file's `## Drafts`; refuses an existing file |
| `publish "<Project>" --title "<Title>" [--apply]` | copies the latest whole draft into `writing/4 published/<Title>.md` and links it first under `## Drafts`; refuses a project with no whole draft, a title a project file carries, and an existing file |
| `import "<Word file>" "<Project>" [--section "<Section>"] [--apply]` | converts the Word file into the next version of the whole draft or section, its footnotes as Markdown footnotes, and links it first under `## Drafts`; the plan counts the words, the footnotes, and the images not carried; leaves the Word file in the inbox; refuses a name the inbox lacks, a file that is not a `.docx`, and an existing file |
| `discard "<Word file>" [--apply]` | moves the Word file from the inbox to the Trash |
| `export "<basename>" --to <directory> [--as pdf] [--style reading] [--csl <citation style>] [--apply]` | writes `<basename>.docx`, or `<basename>.pdf` with `--as pdf`, into the directory from a draft, a published piece, or an atomic note, in the export style; if the note cites, resolves each citation and adds the bibliography from the Zotero records, in the citation style or, absent `--csl`, in pandoc's default, Chicago author-date; leaves the note as it is; refuses an unknown basename, an existing file, a citation style `~/Zotero/styles/` lacks, a citekey Zotero holds no record under, and a citing note while Zotero is not running |

`import` and `export` run `pandoc`, and `export --as pdf` runs `typst`. If a
command reports that either is not installed, stop and ask the user to run
`brew install pandoc` or `brew install typst`.

## Operations

**Cut a version only when the user says so, or under "Applying approved
fixes".** An edit the user asks for by name goes into the version the user
names, or the latest if the user names none.

### Checking a draft

Precondition: the user names a draft and asks for it to be checked, edited,
or polished.

**Read `.claude/skills/edit-drafts/reference/checks.md` before step 1.** It
states the levels, each level's checks, the verdicts, and how a finding is
worded.

1. Settle the levels to run. If the user names levels, run those. If the user
   asks for a polish or a proofread, run `copy`. Otherwise, run `structure`,
   `line`, and `copy`, and say so in the report.
2. Read the draft whole. Run `citations` with its basename.
3. A choice of style or of a term is the draft's own: report a choice the
   draft makes two ways as a finding that asks which stands, and NEVER
   record a choice or a habit of the user's anywhere.
4. Make each check of the levels settled, and record each finding with its
   line.
5. For the `copy` level, grade each claim about a held source against the
   passage it cites, per "Sources" of `checks.md`, reading the passage per
   `retrieval.md`. Verify each quotation of a held work with `verify.py
   verify "<basename>" "<the quotation>"`. NEVER correct a quotation in the
   draft: the finding carries the page's words.
6. Deliver the findings in the form the user asked for:

   | The user asked for | Do |
   | --- | --- |
   | a report, or named no form | report in chat, by level and by check, each finding with its line, the words, and the fix proposed or the question asked |
   | comments in the draft | write each finding as an editor's comment, and report in chat the count by level and by check |
   | the errors fixed | report as the first row says; the request approves each finding that is a misspelling, a grammatical slip, a doubled word, or a slip of punctuation, and no other: follow "Applying approved fixes" for those |

7. Close the report with what was left and what was not checked, per
   `checks.md`.

### Checking a later version

Precondition: the user asks whether a new version answers an earlier check,
or asks for a proofread of a version cut after one.

1. Read the findings of the earlier check: the editor's comments of the
   earlier version, or the report in the conversation. If neither is at
   hand, stop and ask the user for them.
2. Read the earlier version and the new one whole, and grade each earlier
   finding per "Proof" of `checks.md`. A finding the user said stands is
   `declined`.
3. Make each check of "Proof": read each change that answers no finding as
   new text.
4. Report once, in chat: the count of each grade; each finding graded `partly
   addressed`, `not addressed`, or `new problem`, with its line; each finding
   of step 3; and what was checked.

### Checking a draft against given standards

Precondition: the user names a draft and gives the standards to check it
against: a journal's or a press's instructions, a style guide's rules, or a
call's requirements, as text, as a file, or as a link.

**The standards are what the user gives, and nothing else.** NEVER supply a
journal's or a style guide's rules from memory. If the user names a journal
and gives no instructions, ask for them or for their link.

1. Read the standards whole; a link is read with `WebFetch`. If the link
   cannot be read, stop and ask the user for the text.
2. List each requirement the standards state, in their words.
3. Run `count` and `citations` with the draft's basename, and read the draft
   whole.
4. Check the draft against each requirement. A requirement is checked if the
   draft's text shows whether it is met; otherwise it is left to the user.
5. Report once, in chat: each requirement, what the draft shows against it,
   and each finding with its line; then each requirement left to the user.

### Applying approved fixes

Precondition: the user approves findings of a check, all or by name, or asks
with the check for the errors of spelling and grammar to be fixed.

1. Run `cut` for the draft's project, and section if it is a section draft;
   read the plan; run it with `--apply`.
2. In the new version, make each approved fix, and no other change. Delete
   each editor's comment whose finding is fixed or that the user dismissed.
   NEVER fix a slip inside a quotation: report it.
3. Report once, in chat: the new version, the fixes made by check, and the
   findings left open.

### Breaking a draft into atomic notes

Precondition: the user names a draft and asks for its claims, its atomic
notes, or its coverage.

1. Read the draft whole. Run `notes.py list` for every atomic note with its
   claims and its projects.
2. List each claim the draft argues for or rests on, by section, in the
   draft's words. A claim the draft only reports of a source is no claim of
   the draft's.
3. Match each claim to the atomic note whose claims hold it. A note holds a
   claim if one of its claims states the same thing; a note on the same
   subject does not hold it.
4. For each claim no note holds, create the atomic note per "Creating a note"
   of the `take-notes` skill, its claims in the draft's words, and place it
   on the project's board with `projects.py place`.
5. If the draft argues one claim from another, write the relation with
   `notes.py relate`, marked for review.
6. If the user asked for the notes to be researched, follow "Researching a
   batch of notes" of the `take-notes` skill on the notes created.
7. Run `projects.py sync` with the project per "Syncing a board" of the
   `manage-projects` skill.
8. Report once, in chat, the coverage: per section, each claim with the note
   that holds it; each note created; and each claim whose note carries a
   review mark, an open task, or no reference. A draft is covered when every
   claim has a note with a reference and without a review mark.

### Matching unused notes to a draft

Precondition: the user names a draft and asks which atomic notes bear on it.

1. Read the draft whole. Run `notes.py list`.
2. For each atomic note no claim of the draft matches, per step 3 of
   "Breaking a draft into atomic notes", judge whether its claim would
   support, extend, or contradict a claim the draft makes.
3. Report once, in chat: each such note, the claim of the draft it bears on,
   and how; first the notes of the draft's project, then the others. NEVER
   write a note into the draft.

### Formatting a manuscript

Precondition: the user names a draft, a published piece, or an atomic note
and asks for it as a `.docx` or a PDF.

**The export style is `submission` unless the user asks for `reading`.**

| Export style | Sets |
| --- | --- |
| `submission` | Times New Roman 12 pt, double-spaced, 1-inch margins, footnotes 10 pt single-spaced |
| `reading` | Palatino 11 pt, spaced at 1.15, 1.25-inch margins, block quotations 10 pt, footnotes 9 pt |

**The file carries the note's body alone.** `export` leaves out the
frontmatter, every Obsidian comment, and every embed, and writes a wikilink
as the words it shows.

1. If the user names a citation style, pass it with `--csl`. If
   `~/Zotero/styles/` lacks the style, ask the user to install it in Zotero.
2. Run `export` with `--to` naming a new directory of the session scratchpad;
   read the plan; run it with `--apply`.
3. Send the file to the user through SendUserFile. If SendUserFile is
   unavailable, give the scratchpad path in chat.

### Publishing

1. Ask the user for the published piece's title, unless the user named it.
2. Run `publish` with the title; read the plan; run it with `--apply`.
3. Run `projects.py status "<Project>" published --apply`.

### Importing a Word file

Precondition: the user names a Word file and asks for it as a draft.

1. Ask the user for the project's name and whether the Word file is a whole
   draft or a section, unless the user said. If `projects.py tree` lacks the
   project, create it per "Creating a project" of the `manage-projects` skill.
2. Run `import`; read the plan. If the plan counts no words, stop and ask the
   user. Otherwise, run it with `--apply`.
3. NEVER correct the draft `import` wrote: its prose is the user's.
4. If the user asked for the Word file to be discarded, run `discard`, read
   the plan, and run it with `--apply`. If `discard --apply` reports that the
   Trash denies access, run the same command outside the sandbox. If the
   user did not ask, leave the Word file in the inbox.
5. Report once, in chat: the draft written, its words and footnotes, the
   images not carried if the plan counts any, and whether the Word file went
   to the Trash.
