---
name: manage-projects
description: "Projects — on the user's instruction, manage the user's projects: scope a project from its questions and claims, with the state of the literature on them, a reading list, a proposed abstract, and next steps; keep each project up to date: a project file per project, its parents and children in its frontmatter; the bibliographies each atomic note's and project file's subject belongs to named in its `field:`; its board an argument map of the project's atomic notes, kept in step with the notes' relations and their `projects:`; its reading list refreshed against the library; build a project's board from a draft; carry agreed claims into atomic notes; record feedback."
allowed-tools: Read, Glob, Grep, Edit, Write, Agent, Skill, SendUserFile, Bash(~/.research-vault/venv/bin/python .claude/skills/manage-projects/scripts/projects.py:*), Bash(~/.research-vault/venv/bin/python .claude/skills/take-notes/scripts/notes.py:*), Bash(~/.research-vault/venv/bin/python .claude/skills/edit-drafts/scripts/drafts.py:*), Bash(~/.research-vault/venv/bin/python .claude/skills/answer-questions/scripts/verify.py verify:*), Bash(~/.research-vault/venv/bin/python .claude/skills/answer-questions/scripts/verify.py locate:*), Bash(~/.research-vault/venv/bin/python .claude/skills/search/scripts/search.py query:*), Bash(~/.research-vault/venv/bin/python .claude/skills/classify-and-place/scripts/bibliographies.py tree:*), mcp__vault-rag__search_hybrid, mcp__vault-rag__get_frontmatter, mcp__vault-rag__list_works, mcp__vault-rag__outline
---

# manage-projects (Research Retrieval, run by the orchestrator; no worker)

**The writing folders are a Zettelkasten.** An atomic note holds one to three
claims of the user's, their explications, its relations to other atomic notes,
the verified quotations behind the claims, and the tasks they leave. A project file maps the atomic notes of
one piece of writing on its board. Each fact lives in one place: the claims,
their relations, their references, and their tasks in the atomic note, the
arrangement in the project file, on its board, the prose in the drafts, and the
bibliographies of each one's subject in its own field.

**Write in `writing/` only on the user's instruction.** NEVER change the
prose of a draft or a published piece unless the user asks. The rules of
`AGENTS.md` §1 bind every line written: report each author's argument as the
text presents it, NEVER evaluate it, and NEVER write a quotation that was not
verified in the PDF.

**Read `.claude/skills/answer-questions/reference/retrieval.md` before searching,
reading, or quoting the library.** Its "Rigor" binds every reference and
every report of a source this skill writes.

**If a command exits non-zero and no row below names its failure, stop and
ask the user**, naming the command and its error.

## Vocabulary

| Term | Is |
| --- | --- |
| atomic note | `research vault/writing/1 notes/<Title>.md`: one to three claims of the user's under one idea's title, their explications, the references behind them, and the tasks they leave |
| field | the `field:` in an atomic note's or a project file's frontmatter: the bibliographies its subject belongs to, each `"[[<Topic>]]"`; no bibliography lists the note or the project file back |
| task | a `- [ ] #<tag> · <Verb> …` line naming a step the orchestrator or a worker carries out, its tag naming the step's kind: under an atomic note's `# Tasks`, `#<thread> · Take notes on “<Title>” …`, naming one further atomic note, per the `take-notes` skill; under a reading list's "Neighbouring subjects" or a project reading list's `# Neighbouring subjects`, a discover task, per the `discover` skill; NEVER a step only the user can take, and NEVER a line anywhere else |
| project | one piece of the user's writing in progress, named by its project file's basename |
| project file | `research vault/writing/2 projects/<Project>.md`, the user's map of one project: an Excalidraw board, with its parents and children in its frontmatter, its Markdown side, and its drawing |
| board | the drawing of a project file: the research question's section card, a card for each atomic note and each source of the project, an arrow for each relation, and the project card in its corner |
| card | one box of a board, holding a title and words; an atomic note's card and a source's card link what they stand for |
| section card | a card that shows what stands under `# Research question` or `# Project` as Markdown the user reads and edits on the board |
| project card | the section card of `# Project`: the abstract, the link to the project reading list, the drafts, the open questions, and the change log |
| change log | the lines under `## Change log` of a project file: one dated line per atomic note added to or removed from the project, and per draft listed |
| Markdown side | the headings of a project file above its drawing: `# Research question`; `# Project` with its `## Abstract`, `## Reading list`, `## Drafts`, `## Open questions`, and `## Change log`; `# Feedback` |
| project reading list | `research vault/bibliographies/4 reading lists/<Project> - Reading list.md`: under `# Questions` each question a reading list carried into it was searched for, then the works that bear on the project's questions, under `# Held`, then `# Wanted`, each sorted into the reading list's groups, then under `# Neighbouring subjects` the discover tasks carried into it; never a bibliography |
| group, of a project reading list | a `###` heading under `# Held` or `# Wanted` and the entries beneath it, named for one part of the project's questions |
| wanted entry | `- **<high\|medium\|low>** · <Author> <Year>, *<Title>* — <why the work bears on the question>. [<obtain link kind>](<link>)`, a work the library does not hold |
| board state | the comment `%% board-state … %%` that opens the Markdown side, naming the notes, the relations, and the section cards the last `sync` left on the board |
| child project | a project another project's `children:` lists, its own `parents:` listing that project; a project MAY have several parents |
| draft | a file of `research vault/writing/3 drafts/` holding one version of a project's text, or of one section of it |
| whole draft | a draft of the whole project, `<Project> - v<NN>.md` |
| section draft | a draft of one section, `<Project> - <Section> - v<NN>.md`, versioned apart from the whole draft and from every other section |
| version | the two-digit number that closes a draft's name; the latest version is the highest |
| published piece | `research vault/writing/4 published/<Title>.md`, a finished whole draft the user is no longer working on, under a title no project file carries |

## Layout

| Folder | Holds | Written by |
| --- | --- | --- |
| `writing/1 notes/` | every atomic note, flat | `notes.py`, per the `take-notes` skill; `projects.py classify`; the user; a fold of the reshaping, in `field:` alone |
| `writing/2 projects/` | every project file, flat | `projects.py new`, `link`, `status`, `add`, `sync`, `card`, `place`, `classify`; `drafts.py cut`, `publish`, and `import`, in `## Drafts` alone; the user, on the board in Obsidian; a fold of the reshaping, in `field:` alone |
| `writing/3 drafts/` | every draft of every project, flat | `drafts.py cut` and `import`, per the `edit-drafts` skill; the user |
| `writing/4 published/` | every published piece | `drafts.py publish`, per the `edit-drafts` skill |

**A name is unique across the vault.** NEVER give a project or an atomic note
the basename of a corpus file, a transcript, a bibliography, a reading list,
or another note of `writing/`: Obsidian resolves a wikilink by basename.

## The atomic note

**The `take-notes` skill states the atomic note, and its `notes.py` writes
every line of one.** Read `.claude/skills/take-notes/SKILL.md` before an
operation of this skill writes in an atomic note: its "The atomic note" and
its "Commands" bind that writing.

**An atomic note is placed only when the user asks.** The user places it, in
Obsidian or by asking for `place`.

## The project file

**The project file is an Excalidraw board: a frontmatter, a Markdown side,
and a drawing.** Obsidian opens it as the board; "Open as Markdown" shows the
Markdown side. It is the one note of the vault that is not plain Markdown.

**The frontmatter carries `status:`, `parents:`, `children:`, and, once the
user confirms its field, `field:`, beside the two keys the Excalidraw plugin
reads.** `status:` is one of `planning`, `drafting`, `revising`, `submitted`,
or `published`: set it with `status` when the user names the project's
state, and set `published` at publication.

**`parents:` and `children:` each list `"[[<Project>]]"` links, and every
link is listed on both projects.** `new --parent` and `link` write both
sides. If `tree` reports a one-sided link, ask the user whether to complete
it with `link`.

### The Markdown side

| Heading | Holds | Written |
| --- | --- | --- |
| `# Research question` | one `- <question>` line per question the project answers | by `card question`; by the user, on the section card |
| `# Project` | the five `##` headings below, and nothing of its own | by `new` and `sync` |
| `## Abstract` | the project's claim, in two or three sentences | by `card abstract`; by the user, on the section card |
| `## Reading list` | the link to the project reading list, and nothing else | by `new` and `sync`; NEVER by hand |
| `## Drafts` | one `- [[<draft basename>]]` link per draft and per published piece, latest first; NEVER an embed: an embed shows the whole draft | by `drafts.py cut`, `import`, and `publish` |
| `## Open questions` | one `- <question>` line per question the project has not settled; absent until its first line | by `card open-question`; by the user, on the section card |
| `## Change log` | one line per change to what the project holds, the oldest first: `- <YYYY-MM-DD> · <kind> <what>`, the last heading of the project card | by `sync`, `place`, and `drafts.py cut`, `import`, and `publish`, each as it makes the change; NEVER by hand, and NEVER reworded or deleted |
| `# Feedback` | one line per point of feedback the user received, under the name of who gave it; absent until its first line | by `add feedback` on the user's instruction |

**The change log is the project's trail: what joined it, what left it, and
when.** Each line carries one kind:

| Kind | The line reads | Written when |
| --- | --- | --- |
| `added` | `added [[<Title>]]` | an atomic note gains a card on the board, by `sync` or `place` |
| `removed` | `removed [[<Title>]]` | a note leaves the project: the user deleted its card |
| `drafted` | `drafted [[<draft basename>]]` | a draft or a published piece is listed under `## Drafts` |

A change to a note's title, its words, its references, its relations, or its
place on the board is no line of the change log: the note and the board show
it.

**`sync` writes the Markdown side anew from the bodies of `# Research
question`, `## Abstract`, `## Drafts`, `## Open questions`,
`## Change log`, and `# Feedback`.** NEVER write anything else on the Markdown side: `sync` drops
it. `sync` reads a heading an earlier layout wrote at the top level, and
writes it at its level of this table.

**A project file holds no task.** A task lives in its atomic note, or as a
discover task in the project reading list; a step only the user can take is
named in the report, and written nowhere.

**A line the orchestrator proposes under `# Research question`, `## Abstract`,
or `## Open questions` ends with the review mark, which the user alone
removes.** A line the user stated carries none.

### The board

**The board is the project's argument map, and nothing else: the research
question's section card as its root, a card for each atomic note and each
source, and an arrow for each relation between two atomic notes.**

**The board reads as a tree drawn by hand, rooted in the research question,
and whoever writes a card on it chooses where the card stands.**

| A card | Stands |
| --- | --- |
| the research question | at the middle of the board, the root |
| a note that takes the argument a step further: a main claim, or a claim that extends, supports, or presupposes the card beneath it | above the card it follows, so that reading upward is reading through the argument |
| a note that branches off: a view set against a card, a context, a detail, an example | beside the card it bears on, to its left or its right |
| the project card | below the research question and well to its left, the board's bottom left corner |

Judge each card by what its note does in the argument, and place it with
`place` or `move`. PREFER a tree whose trunk a reader finds at a glance OVER
an even grid: leave a branch short where the argument is short.

**Each time a card is added, read the whole board again and rearrange it
where the new card crowds it.** The board has no edge: PREFER distance
OVER a compact board, so that every arrow runs clear of every card and no
two arrows lie on one another. Move a card with `move`, which draws its
arrows again; a card the user placed MAY be moved for this, and is NEVER
resized or restyled. Read where each card stands in the `positions` of `board`, and
tell the user in the report which cards were moved.

**Everything else a project keeps stands in one section card, the project
card, in the board's corner.** The project card shows `# Project`: the
abstract, the link to the project reading list, the drafts, the open
questions, and the change log, each under its `##` heading. NEVER draw a further card
for a thing the project keeps, and NEVER show a list or a document kept
elsewhere on the board, at its length or as counts: the project card links
it. Which notes await review, the dashed border of their cards says.

**The project card stands below the research question's section card and
well to its left, clear of its level, and the argument map grows from the
research question upward and to both sides.** NEVER draw the project card
level with the research question or above it: the map needs that room.
`sync`, and `place` without a side, draw a card above the card it relates
to, or above the research question's section card if it relates to none.

**An atomic note's card shows the note's claims, each explication beneath
its claim, and no task.** Its last line counts the note's references and its
open tasks. A task is read in its note, and nowhere on the board.

**A card shows the whole of what it holds, with nothing to scroll.** `sync`
draws a section card as tall as the words under its heading need, and at
each `sync` makes taller a section card whose words have outgrown it, its
width kept: the research question's downward, its top kept, and the project
card upward, its foot kept, so that it never reaches the root's level. A
section card taller than its words need keeps its height. An atomic note's
card reaches beneath its last line.

**A card's title is set in black, heavy type, and every word of a board is
large enough to read with the cards around it in view.** A section card
carries its name above it, grouped with it: it shows what stands under its
heading and never the heading itself. The research question's section card
shows its words at one and a half times their size, and the project card at
one and a quarter.

**Every colour of a board follows the board's own light or dark mode, never
Obsidian's.** Excalidraw inverts each drawn colour in dark mode, so a drawn
card, title, or arrow carries its light-mode colour. A section card's fill
is drawn on the board like any card's, and its Markdown lies over the fill
with a see-through background: the Markdown's text takes the board's mode,
and a background of Obsidian's or of a fixed colour hides the text when the
two modes differ.

| Card | Shows | Drawn |
| --- | --- | --- |
| a section card | what stands under `# Research question` or under `# Project`, as Markdown, beneath the heading's name | by `new` and `sync`, once each; by `card`, if `sync` drew none before |
| an atomic note's | the note's title, its claims with their explications, and its counts of references and open tasks; it links the note | by `sync` for a note that names the project; by `place`; by the user, who drops the note on the board |
| a source's | a held work's basename, which it links | by `card source` |

**Everything a project file holds is reached from its board.** The user
reads and edits a section card on the board, and what the user writes there
is written under its heading. If the user deletes a section card, `sync`
leaves it deleted: the heading stays on the Markdown side.

| Line | Says |
| --- | --- |
| a solid border | the note has references and carries no review mark; or the user named the source |
| a dashed border | the note carries a review mark; or the orchestrator proposed the source |
| a grey border | the note has no reference yet |
| an arrow | a relation of a note that carries no review mark, or one the user drew |

**An arrow between two atomic notes' cards, labelled with a relation kind, is
that relation.** Each relation kind has its own colour. An arrow is drawn
heavy and bent, never ruled straight, and its heads say which way the
relation runs:

| Relation kind | The arrow runs |
| --- | --- |
| `contradicts` | both ways, a head at each end: neither note comes first |
| `extends`, `example of`, `presupposes`, `descends from` | from the note the relation names to the note that states it: from what is explained to what explains or continues it |
| `supports` | from the note that states the relation to the note it names: from the reason to what it is a reason for |

**An arrow labelled `answers` runs from a note's card to the card of the
question the note answers, with one head, at the question.** `answer` draws
it, to the research question's section card or to a card that states a
narrower question. It is no relation between two atomic notes: no note
carries a line for it, and `sync` leaves it as it stands. Draw one for each
note whose claims answer a question of the board: the user's own answer,
and each alternative answer the project sets against it, which carries its
`contradicts` relation to the user's answer besides. Draw none for a note
that only bears on an answer: its relation joins it to the answering note.

**An arrow is drawn once its note is reviewed.** `sync` draws no arrow for a
relation of a note that carries a review mark: the card stands on the board
with its dashed border, and its arrows follow when the user has accepted
the note. An arrow with any
other label, or to a card that is no atomic note's, is the user's drawing:
`sync` leaves it as it is.

**NEVER resize or restyle a card or an arrow the user placed, and NEVER
erase one.** `sync` draws a new card, rewrites the words and the border of
an atomic note's card, lowers the foot of a section card whose words have
outgrown it, and changes nothing else of what stands on the board. `move`
alone moves a card, per the rearranging rule above.

**NEVER write the drawing by hand, and NEVER write a project file while the
user has its board open in Obsidian:** the plugin saves the open board over
the file. Before a command of this skill or of `drafts.py` writes a project
file, read the `main` tabs of `research vault/.obsidian/workspace.json`: if
one names the project file, ask the user to close the board's tab, and
write nothing until the user says it is closed.

**Every write of a project file first copies the file as it stands into
`writing/2 projects/.board-backups/`, under the project's name and the
time, and the folder keeps the last thirty copies of a board.** If a command
that writes a project file exits non-zero, write nothing further to that
file: read it, and if it is empty or lacks what the board held, copy the
latest backup over it and tell the user what happened. NEVER run `sync` on
a project file a failed command left.

### What `sync` carries, in both directions

| The board and the notes differ by | `sync` does |
| --- | --- |
| `# Research question` or `# Project` has no section card, and `sync` drew none for it before | draws its section card |
| a note names the project in `projects:` and has no card | draws its card |
| one card of the last `sync` links a title no note carries, and one note that names the project has no card | the note was renamed: links the card to it, where the card stands; with more than one of either, relinks none and plans each note's card as new |
| a card stands for a note that does not name the project | writes the project into the note's `projects:` |
| a card `sync` drew, or saw, is gone from the board | takes the project out of the note's `projects:` |
| a relation between two notes of the board is in a note that carries no review mark, and has no arrow | draws the arrow |
| an arrow between two notes' cards has no relation in the source note | writes the relation into the note, as the user's, without a review mark |
| an arrow `sync` drew, or saw, is gone from the board | deletes the relation's explication from the note |
| a relation `sync` saw in a note is gone from the note | erases the arrow |

**If a relation to delete stands inside a sentence of the note, `sync` leaves
the note as it is and draws the arrow again.** Report the relation to the
user, who removes its words in the note.

## Commands

Every command is
`~/.research-vault/venv/bin/python .claude/skills/manage-projects/scripts/projects.py <subcommand>`.
Run each writing form only after reading its read-only form's plan.

| Command | Does |
| --- | --- |
| `tree` | read-only: every project with its `status`, its `field`, its parents, its children, each one-sided link, and its drafts |
| `new "<Project>" [--parent "<Project>"] [--apply]` | writes a project file into `writing/2 projects/`, every heading of its Markdown side empty but for the link to the project reading list, its two section cards drawn on the board, and a blank project reading list; with `--parent`, lists the parent in its `parents:` and it in the parent's `children:`; refuses a taken name or a name holding a character a filename or a wikilink cannot carry |
| `link "<Parent>" "<Child>" [--apply]` | lists the child in the parent's `children:` and the parent in the child's `parents:`; refuses a project as its own parent |
| `status "<Project>" <status> [--apply]` | sets the project file's `status:` |
| `add "<Project>" <heading> "<line>" [--apply]` | adds the line last under the heading, `drafts` or `feedback` |
| `board "<Project>"` | read-only: the atomic notes that have a card, the other links, each section card by its heading and the words under it, each card without a link by its title and its words, each arrow between two cards as source, label, target, and under `positions` where each note's card and each section card stands: its left edge, its top edge, its width, and its height, the top edge smaller the higher the card stands |
| `sync "<Project>" [--apply]` | brings the board and the atomic notes in step, per "What `sync` carries", writes the Markdown side anew, creates the project reading list if the folder lacks it, and turns a project file that has no drawing into a board; the plan lists each section card to add, each card to add, each card to relink to a renamed note, each note to join or leave the project, each arrow to draw or erase, and each relation to write or remove |
| `card "<Project>" <kind> "<words>" [--stated] [--apply]` | `abstract`, `question`, or `open-question`: writes the words last under the kind's heading, marked for review unless `--stated`, and draws the heading's section card if `sync` drew none before; `source`: draws a card at a free point of the board with a held work's basename, dashed, as the orchestrator's proposal, unless `--stated`; refuses a kind outside the four and a card without words |
| `readings "<Project>" [--refresh] [--apply]` | read-only: the project reading list's entries by status, and each wanted entry the library now holds with its basename; with `--refresh`, moves each such entry under `# Held` as the held work's wikilink with its reason |
| `reading "<Project>" <question\|held\|wanted\|subject> "<entry>" [--group "<Group>"] [--apply]` | adds the entry last under its section, `# Questions`, `# Held`, `# Wanted`, or `# Neighbouring subjects`, a held or wanted entry under its group, a discover task with its box to check and every other entry without one, creating the project reading list if absent; refuses a wanted entry or a discover task out of its shape, a group for a question or a discover task, and an entry the list holds |
| `place "<Title>" "<Project>" [--above "<Card>" \| --left-of "<Card>" \| --right-of "<Card>"] [--apply]` | draws the atomic note's card on the side named of the card named, a note's title or `Research question`, or above the research question if no side is named, and writes the project into the note's `projects:`; a card to the left or right stands on the named card's foot line, and a side already taken sends the card further the same way; the plan names the point; refuses a missing note, a note with a card on the board, and a card the board lacks |
| `answer "<Title>" "<Project>" [--question "<Card>"] [--apply]` | draws an arrow labelled `answers` from the note's card to the card of the question it answers: the research question's section card, or the card `--question` names; refuses a note without a card, a card the board lacks, and a second answer of the note to the same question |
| `move "<Title>" "<Project>" --above "<Card>" \| --left-of "<Card>" \| --right-of "<Card>" [--apply]` | moves the note's card to the side named of the card named, and draws every arrow bound to it again between the same cards; the plan names the point and each arrow to draw again; refuses a note without a card and a card the board lacks |
| `classify "<Title or Project>" "<Bibliography>"... [--apply]` | writes the field of the atomic note or project file the name gives into its frontmatter, replacing its `field:`, and writes in no bibliography; the plan names the `field:` it replaces; refuses a name that is neither or both, a name that is no bibliography, a bibliography named twice, and no bibliography |
**NEVER edit a project file by hand.** Every change goes through a command
or through the user in Obsidian.

## Operations

### Creating a project

1. Run `new` with the user's name for the project and, if the user names one,
   its parent; read the plan; run it with `--apply`.
2. If the user names further parents, run `link "<Parent>" "<Project>"` for
   each; read the plan; run it with `--apply`.
3. If the user states the project's abstract or its research questions, run
   `card` for each with `--stated`.

### Writing an atomic note

Follow "Creating a note" and "Researching a note" of the `take-notes` skill.
If the user asks for the note to be placed on a project's board, choose
where its card stands per "The board", and run `place` with the note, the
project, and the side; read the plan; run it with `--apply`. If
`place` refuses a note with a card on the board, leave the card where it
is.

### Setting a note's field

Precondition: the user asks for the field of an atomic note or a project
file, or the `take-notes` skill researches or reviews an atomic note.

**NEVER list an atomic note or a project file on a bibliography:** a
bibliography lists only works, and the field lives in the frontmatter alone.

1. Read the note's claims, or, with `board`, the project's abstract card and
   the atomic notes of its board, and their fields.
2. Read the `field:` of each held work the note's references name, with
   `get_frontmatter`, and the bibliography tree with
   `bibliographies.py tree`.
3. Choose the most specific bibliography the note's subject belongs to on
   each line of descent, under the rule of `AGENTS.md` §4 that places a work.
   A reading note takes the field of its work unless its claims treat a
   narrower subject.
4. If the `take-notes` skill researches or reviews the note, run `classify`
   with the bibliographies of step 3, read the plan, run it with `--apply`,
   and name each bibliography in the report: the user revises the field
   after the fact. Otherwise, propose the bibliographies to the user, each
   with the claim or source that gives the note that bibliography, and
   NEVER write a field the user has not confirmed.
5. If the user confirms bibliographies, run `classify` with them; read the
   plan; run it with `--apply`.
6. If no bibliography holds the note's subject, say so to the user and write
   no field: NEVER create a bibliography for a note, since a
   bibliography is created by the reshaping alone.

### Building a project's board from a draft

Precondition: the user names a draft and asks for its project file.

1. If the draft is a Word file, import it per "Importing a Word file" of the
   `edit-drafts` skill and go to step 2. If the draft is not in
   `writing/3 drafts/` under a draft name, ask the user for the project's
   name and whether the draft is whole or a section. Then create the project
   if `tree` lacks it, run `drafts.py cut` with `--apply`, and copy the
   draft's text into the empty version 01. Delete nothing: the user removes
   the original.
2. Read the draft whole.
3. If the draft states the project's question or its abstract, run `card`
   for each.
4. For each idea the draft argues for, create an atomic note of its one to
   three claims per "Creating a note" of the `take-notes` skill, and place it
   on the project's board with `place`.
5. Find every work the draft cites. Resolve each to a held work by
   `list_works`, `search_hybrid`, or `get_frontmatter`.
   1. If the work is held and the draft quotes it, write the quotation with
      `notes.py reference` in the atomic note the citation supports. If
      `reference` refuses the quotation, name the quotation, the work, and
      the folio the draft cites in the report, and NEVER correct the draft.
   2. If the work is held and the draft cites it without quoting, locate the
      passage at the folio the draft cites, or with `search_hybrid` or
      `verify.py locate` if the draft cites none, and write it with
      `notes.py reference`. If no passage is found, name the work in the
      report.
   3. If the work is not held, name it in the report.
6. Run `notes.py check` on each atomic note written. If the draft argues one
   idea from another, write the relation with `notes.py relate`.
7. Run `sync` with the project; read the plan; run it with `--apply`.
8. Report once, in chat: the cards and atomic notes written, the held works
   and unheld works found, each held work whose passage was not found, and
   each quotation `reference` refused.

### Carrying a discussion into the atomic notes

Precondition: the user and the orchestrator have agreed, in discussion, on
ideas to keep, or on passages and citations that bear on them.

1. Write each agreed idea per "Writing an atomic note".
2. Report once, in chat: each atomic note written or extended, and each
   project whose board it went onto on the user's request.

### Scoping a project

Precondition: the user gives the questions a project is to answer, and the
claims the user means to make.

**Report the literature; NEVER rule on it.** Say what each work argues, where
the works disagree, and where the user's claim stands among them: which works
state it, which state its contrary, and which leave it open. Whether the
claim is right is the user's.

1. Create the project per "Creating a project" if `tree` lacks it. Run `card`
   with `question` and `--stated` for each question, and create an atomic
   note per "Creating a note" of the `take-notes` skill for each claim, placed
   on the board with `place`.
2. For each question, search, choose the works, and read, per
   `.claude/skills/answer-questions/reference/retrieval.md`. Record each held work
   that bears on the question with `reading "<Project>" held "[[<basename>]]
   — <what it argues on the question, with its folio>" --group "<Group>"`,
   per "The groups of a project reading list".
3. Invoke the `discover` skill on the questions, then follow "Carrying a
   reading list into a project" on its reading list.
4. Research each claim's note per "Researching a batch of notes" of the
   `take-notes` skill.
5. Propose the abstract: run `card` with `abstract` and two or three sentences
   stating the question, the claim, and what the project sets aside. Propose
   each key source with `card source`, and each question the literature
   leaves open with `card open-question`.
6. Follow "Syncing a board".
7. Report once, in chat, per question: what the held works argue, cited by
   folio; where they disagree; where each of the user's claims stands among
   them; what the library lacks; then the reading list in counts, and the
   next steps: each wanted work of priority `high` to obtain, each claim
   without a reference to settle, and each open question to decide.

### The groups of a project reading list

**A project reading list sorts every entry into a group, and `# Held` and
`# Wanted` carry the same groups in the same order.** Name the groups from
the parts of the project's questions: one for the primary texts the
questions are about, one for the secondary literature on those texts, and
one for each debate a question names. Before the first entry is written,
state the groups to the user in chat. If an entry fits no group, ask the
user for its group. A wanted entry moves under `# Held` in the group it
stood in.

**A project reading list holds only the works that bear on the project's
questions, as the `discover` skill's "Scope" defines.** NEVER record a held
work, or carry a wanted one, on a neighbouring subject: a neighbouring
subject is a discover task under `# Neighbouring subjects`, which the user
chooses by checking it or naming it, and which the `discover` skill's
"Discover tasks" resolves.

### Carrying a reading list into a project

Precondition: a reading list the `discover` skill wrote, and a project `tree`
lists. If `tree` lacks the project, stop and ask the user.

1. Run `reading "<Project>" question` with the reading list's `question:`.
2. For each candidate item and each cited item of the reading list, run
   `reading "<Project>" wanted` with the item as a wanted entry and
   `--group` with its group: its author, year, and title from the item's
   reference, the item's comment as why the work bears on the question, and
   the item's obtain link. If the item has no obtain link, the wanted entry
   ends without one. Give `high` to a work wholly on the question, and
   `medium` to a work that discusses it in a passage, per the `discover`
   skill's "Scope". `low` is the user's to give.
3. For each discover task under the reading list's "Neighbouring subjects",
   run `reading "<Project>" subject` with the task.
4. If a cited item's entry text lacks an author, a year, or a title, do not
   carry the item: `reading` refuses a wanted entry out of its shape.
5. If `reading` refuses an entry the list holds, leave the entry as the list
   holds it.
6. NEVER carry an item of the reading list's "Already held" section: a held
   entry states what the work argues on the question, with its folio, which
   step 2 of "Scoping a project" reads.
7. Report once, in chat, in counts: the entries added by priority, the
   entries the list held, and by name each item not carried and each
   discover task carried.

A batch moves each wanted entry carried under `# Held` once its work is
placed, as the `ingest` skill's check-off states.

### Keeping a project up to date

Precondition: the user asks where a project stands, or for its upkeep. A
batch moves a wanted entry under `# Held` on its own once its work is placed, as the
`ingest` skill's check-off states; step 1 covers a work the library holds
that no batch has placed.

1. Run `readings` with the project. If it names wanted entries the library
   now holds, run `readings --refresh`, read the plan, and run it with
   `--apply`.
2. If the user discards a work, delete its entry's line from the project
   reading list by hand: the list keeps no discarded work. If the user
   checked a discover task of the project reading list, resolve it per the
   `discover` skill's "Discover tasks".
3. Run `tree`: each draft of `writing/3 drafts/` under the project's name is
   listed. If a draft is not linked under `## Drafts`, add its link with `add
   drafts`.
4. Follow "Syncing a board".
5. Report once, in chat, in counts and by name only what waits on the user:
   the notes to review, the open tasks of the board's notes, the wanted
   works by priority, the open discover tasks, the latest version of each
   draft, and the project's status.

### Recording feedback

Precondition: the user gives feedback received on a project or a draft.

1. Run `add` with `feedback` for each point, as `- <who>, on [[<draft
   basename>]]: <the point, in the words given>`.
2. If a point that calls for work concerns one atomic note's claim, add a
   task to the note with `notes.py task`. Name each other point that calls
   for work in the report.
3. NEVER answer or assess a point of feedback in the project file.

### Syncing a board

Precondition: the user asks for a project's board to be brought up to date,
or an operation wrote a relation, a `projects:`, or a claim of a note of the
project.

1. Ask the user to close the board's tab in Obsidian, unless the user said it
   is closed.
2. Run `sync` with the project; read the plan.
3. If the plan removes a relation or takes a note out of the project, name
   each to the user before step 4: the user's deletion on the board is what
   removes it.
4. Run `sync` with `--apply`.
5. Report once, in chat, in counts: the cards added, the notes joined and
   left, the arrows drawn and erased, the relations written and removed, and
   each relation `sync` left inside a sentence.
