---
name: take-notes
description: "Take notes — on the user's instruction, research an atomic note: word its claims, find the passages of the library that state or support them, verify each quotation in the PDF, and write its claims, explications, relations, references, and tasks, each line marked for review; write a highlight into the PDF for each reference of a note, and atomic notes from the highlights of a PDF; one note by the orchestrator, or a batch of notes through one note researcher each; resolve the tasks the user chooses into further atomic notes, and have the note reviewer relate and revise the note they came from."
allowed-tools: Read, Glob, Grep, Agent, Workflow, Bash(~/.research-vault/venv/bin/python .claude/skills/take-notes/scripts/notes.py:*), Bash(~/.research-vault/venv/bin/python .claude/skills/answer-questions/scripts/verify.py verify:*), Bash(~/.research-vault/venv/bin/python .claude/skills/answer-questions/scripts/verify.py quality:*), Bash(~/.research-vault/venv/bin/python .claude/skills/answer-questions/scripts/verify.py locate:*), Bash(~/.research-vault/venv/bin/python .claude/skills/extract-corpus/scripts/extract.py record:*), Bash(~/.research-vault/venv/bin/python .claude/skills/search/scripts/search.py query:*), Bash(~/.research-vault/venv/bin/python .claude/skills/search/scripts/search.py outline:*), Bash(~/.research-vault/venv/bin/python lib/vault.py:*), mcp__vault-rag__search_hybrid, mcp__vault-rag__outline, mcp__vault-rag__get_frontmatter, mcp__vault-rag__list_works, mcp__vault-rag__cites, mcp__vault-rag__cited_by, mcp__vault-rag__neighbours, mcp__vault-rag__contexts
---

# take-notes (Research Retrieval, run by the orchestrator; a note researcher for each note of a batch or chosen task; a note reviewer for each reviewed note)

**Read `.claude/skills/answer-questions/reference/retrieval.md` before step 1 of
every operation.** Its "Rigor" binds every line this skill writes.

**Write in an atomic note through `notes.py`.** Its commands close each line
with the review mark and refuse a quotation that is not verified. If the user
asks for a change no command makes, edit the line by hand and close it with
the review mark.

**If a command exits non-zero and no row below names its failure, stop and
ask the user**, naming the command and its error.

## Vocabulary

| Term | Is |
| --- | --- |
| atomic note | `research vault/writing/1 notes/<Title>.md`: one to three claims of the user's under one idea's title, their explications, the references behind them, and the tasks they leave |
| explication | a tab-indented `- <explication>` line beneath a claim: a precision, a clarification, or a relation of the claim |
| reference | one verified quotation under an atomic note's `# References`: a block of `>` lines, its quotation line, its source line, and its optional comment line |
| quotation relation | one of `states`, `supports`, `explicates`, `discusses`, the bold word a quotation line opens with |
| relation | the words `<relation kind> [[<Title>]]` in an explication or in a reference's comment line, naming another atomic note and how the note relates to it |
| relation kind | one of `extends`, `supports`, `contradicts`, `example of`, `presupposes`, `descends from` |
| review mark | ` #review` closing a line of an atomic note the orchestrator, a note researcher, or the note reviewer wrote or changed, which the user alone removes, by hand or by checking the note's accept task; a reference carries one, on its quotation line |
| accepted mark | ` #accepted` closing a line of an atomic note the user has reviewed and keeps, a reference on its quotation line, written in place of the review mark by the user or by `accept` on a note whose accept task the user checked; a line that carries it is never changed or deleted |
| accept task | `- [ ] #accept · Accept every line of this note marked for review`, the first line under every atomic note's `# Tasks`, which the user checks to accept every line of the note marked for review; it is no task |
| task | a `- [ ] #<thread> · …` line under an atomic note's `# Tasks`, its thread's tag first: `Take notes on “<Title>” …`, naming one further atomic note that a thread of the note leads to, or, for an `enrich` task, `Read <the source> for this note …` |
| thread | what a task is to the note it stands in, written as the task's tag: one of `focus`, `enrich`, `conceptual`, `genealogical`, `contrary`; an `enrich` task names further reading for the same note, the others a further atomic note |
| retagged task | a chosen task whose tag the user changed to a note thread while its words name no further note, `Take notes on “<Title>”` absent |
| chosen task | a task the user has checked, `- [x]`, or names in chat: the task to resolve |
| further note | the atomic note a task names, which resolving the task creates and researches |
| stub note | an atomic note the user wrote with a title and a claim and no reference, which no chosen task names; the `resolve-tasks` workflow researches it |
| `resolve-tasks` workflow | `.claude/workflows/resolve-tasks.js`, which resolves the chosen tasks: a note researcher per further note, then a note reviewer per reviewed note |
| reviewed note | the atomic note the note reviewer revises: the note whose chosen tasks are resolved, or a note the user asks to be reviewed |
| note researcher | the `note-researcher` worker, one dispatch per atomic note of a batch or per chosen task, that researches the note and writes into it |
| note reviewer | the `note-reviewer` worker, one dispatch per reviewed note, that relates the note to each further note, rewords its claims to state what its references support, and fits its tasks to them |

## The atomic note

**An atomic note holds three parts, in this order:**

| Part | Holds |
| --- | --- |
| claims | one to three `- <claim>` lines opening the body, each with at most one explication beneath it, besides its relations; claims and explications together come to at most three lines |
| `# References` | one reference per passage behind the claims, each under a group, per "References" |
| `# Tasks` | the accept task, then one task per further atomic note a thread of the note leads to, per "Tasks" |

**`note` writes the blank note from
`.claude/skills/take-notes/reference/atomic-note.md`.**

**A claim is the user's own position, and the title names its idea.** The
title is the filename. If the title holds a character `note` refuses, or runs
past its length, ask the user for a title `note` takes.

**One idea, one atomic note.** A note's claims are one position: one
thinker's view of one matter, or one thesis of the user's. NEVER write in
one note the views two thinkers hold of a matter, or a view a held note
already states: write each view in its own note, and join the two notes
with a relation. If what was found bears on a held note's claims, name the
passages to the user in the report, and write them in that note only when
the user asks.

**A title is short and follows a pattern a reader knows:** `<Author> on <X>`,
`<Author>'s view on <X>`, `<Author>'s <doctrine>`, or `<X> in <work>`. A
title is written in sentence case: a capital opens it and each proper name,
and every other word is lowercase, so that an atomic note is told at sight
from a work, a bibliography, and a project, which are titled in Title Case.
If the user asks for a note and states no title, propose one in chat before
`note` runs. NEVER create a note under a placeholder title.

**NEVER rename an atomic note.** Retitling an idea is the user's, done in
Obsidian, which carries every link of a note to the new name. A board's card
keeps the old name until the board's next `sync`, which relinks it: after
the user retitles a note, follow "Syncing a board" of the `manage-projects`
skill for each project the note names.

**An atomic note's frontmatter carries its `projects:` and its `field:`, and
nothing else.** The `manage-projects` skill writes both.

### What is written, and how it is marked

**Create or fill an atomic note when the user asks, or when an operation of
this skill or of the `manage-projects` skill calls for one.**

**Every line written or changed in an atomic note ends with the review
mark.** A reference carries one review mark, on its quotation line, which
stands for the whole reference: its source line and its comment line carry
none, so that Obsidian lists each thing to review once under the tag. A task
takes no review mark, and a relation the user stated takes none. NEVER
remove a review mark: the user removes it from a line the user accepts.

**The marks say which lines may change, whoever wrote them.** A line that
carries the accepted mark is the user's word: NEVER change or delete it. Any
other line of an atomic note MAY be changed or deleted where an operation of
this skill calls for it, and a line written or changed closes with the
review mark.

**The user accepts a line by writing the accepted mark in place of its
review mark, and rejects one by deleting it.** A reference is accepted on its
quotation line, a claim or an explication at its end.

**The user accepts every line of a note marked for review by checking its
accept task.** `accept` then writes the accepted mark in place of each review
mark of the note and unchecks the accept task. Write the accepted mark only
through `accept`: NEVER write it by hand, and NEVER check an accept task,
because the mark is the user's word that the line was read and is kept.

**A claim's first wording is where research starts: the research rewords
it to state what the note's references support, and the note reviewer
rewords it again after each revision.** Word a claim with `claim`, unless it
carries the accepted mark. Name in the report each claim reworded, with what
the new wording drops or adds, and each part of the first wording no passage
read states or supports.

**The claims and their explications state the whole idea, so that a reader
recalls the note from them alone; the references below give the passages.**

| Rule | Binds |
| --- | --- |
| a note's claims and explications, its relations aside, come to at most three lines | every note |
| each claim or explication is one or two short sentences | every line |
| fill the three lines: name the idea's terms, its steps, and what it is set against, as the passages read state them | every note, unless the passages read give no more to say |
| a claim states one point of the idea; an explication beneath it gives a precision, a step, or a term of that point | each claim carries at most one explication besides its relations |
| NEVER quote a reference or restate a comment line in a claim or an explication | every line |

If the passages read give less than three lines, write fewer, and name in
the report what no passage read gave.

**NEVER attribute a claim or an explication to a source whose text does not
state it, and NEVER evaluate a source in one.**

### References

**A reference is one verified quotation, written by `reference` as a block of
`>` lines with a blank line before it and after it:**

    > **<quotation relation>** · “<the quotation as passed, or the page's words, per the rule below>”
    > 	[[<basename>]], [p. <folio>](<the deep link `verify` reports>)
    > 	<comment>

| Line | Holds |
| --- | --- |
| quotation line | the quotation relation in bold, ` · `, then the quotation between `“` and `”` |
| source line | `> `, a tab, the held work's wikilink, a comma, then the printed folio; if `verify` reports a link, the folio is the link's text, `[p. <folio>](<deep link>)`, and NEVER a separate word beside it |
| comment line | optional, and one or more: `> `, a tab, then one line of the comment, written for a reader of the PDF page, per "Comments", or a relation the passage gives the note |

| Quotation relation | The passage |
| --- | --- |
| `states` | makes the claim |
| `supports` | gives a reason for the claim |
| `explicates` | explains a term or a step of the claim |
| `discusses` | is secondary literature on a primary passage the note references |

**Every reference stands under a group, a `###` heading under
`# References`.** Name the groups from the kinds of source the claims rest
on, judged from the claims: where a claim reports what a thinker holds, one
group for the thinker's primary texts and one for the secondary literature on
them; where a claim sets a position against a debate, one group for that
debate. A note whose claims rest on one kind of source takes one group. Use
the groups of the project reading list of the note's project where the same
division fits.

**The primary texts' group stands first.** `reference` writes a group the
note lacks last. If the note holds a group and lacks the primary texts'
group, write the first primary passage with `--group` naming the primary
texts' group and `--before` naming the note's first group, and each later
primary passage with `--group` alone. `reference` NEVER moves a group the
note holds: if the primary texts' group stands after another group, report
the note to the user.

**Within a group, the references to one work stand together, in the order of
its pages, and then those to the next work.** `reference` places each
reference so; NEVER part the references to one work with another work's.

### Comments

**A comment line is read on the page of the PDF, where it becomes the
highlight's annotation note: write it for a reader who has the page and has
not the atomic note.** A comment gives what the page does not.

**A comment is of one of three kinds, and its kind is its highlight's
colour.** Judge which kind the passage needs, for a reader of the page, and
write that kind:

| Kind | The comment | Its lines | Colour |
| --- | --- | --- | --- |
| claim | explicates, summarizes, or rewords the claim the passage makes, or gives a held work's reading of it that no held work contests | search terms, a summary phrase, `Cf.` lines stating a claim, and `Parallels:` or `Discussed in:` after them | `yellow` in a work the note passes as `--generic`, else the note's group, `blue` or `green` |
| dispute | flags that held works read the passage, or the concept it states, in contrary ways, and points to the contrary reading | one or more `Contra:` lines, beside the `Cf.` line of the reading they contest where the passage is not itself that reading | `orange` |
| pointer | only points to parallel passages, or to works that discuss the passage | `Parallels:`, `Discussed in:`, and `Cf.` lines naming a passage with no claim, alone | `gray` |

A reference with no comment takes the claim kind's colour.

**A dispute comment is rare: orange marks a key passage on which an
interpretive debate turns.** Write one only where every condition holds:

| Condition | Fails when |
| --- | --- |
| both readings are commentators' readings of one primary author's passage or concept | a primary author is set against a commentator, or one primary author's doctrine against another's |
| the two readings are mutually incompatible, plainly to anyone who reads both | the readings differ in emphasis, in detail, or in how much they say |
| at least one of the two works names the other, setting its reading against the other's, on a page read | neither work names the other |

Determinate negation and contradiction in Hegel are concepts so read. A
reading that fails a condition is a `Cf.` line of a claim comment. A primary
author's doctrine that differs from another's is a task, per "Tasks", and
NEVER a comment line.

**A note's comments and its secondary references lead to each other.** The
comment of a primary passage names, in a `Cf.` or `Contra:` line, each
secondary reference of the note that discusses the passage; the comment of
a secondary reference points to the primary passage it discusses. A reading
that a primary passage's comment names and the note does not reference
stays only where it adds to the readings the note references; if it bears
on the note's claims, write an `enrich` task for it. NEVER leave a secondary
reference of the note unnamed on the primary passage it discusses.

| A comment gives | Written as |
| --- | --- |
| the terms a reader would search the PDF by that neither the passage nor the note's title uses | `<Author> on <the subject's name in today's literature>`, the comment's first line |
| a summary of the passage, where its own words are long or oblique | one phrase, on a line of its own |
| where another held work makes a claim about this passage itself: a reading of it, a use it puts it to in its own argument, an objection to it, or a context it sets it in | one line to a work: `Cf. <Author> <Year>, p. <folio>: <one short sentence stating that claim, as the work's text presents it>` |
| where a held work reads the passage, or the concept it states, contrary to the reading the passage states or a `Cf.` line gives | one line to a work: `Contra: <Author> <Year>, p. <folio>: <one short sentence stating the contrary reading, as the work's text presents it>` |
| where another held work quotes or restates this passage and claims nothing about it the passage does not say | one line, after the `Cf.` lines: `Discussed in: <Author> <Year>, p. <folio>`, the works joined with `; ` |
| in a passage of secondary literature on a thinker, the primary passages it discusses | one line: `Cf. <work> (<Author> <Year>, p. <folio>)`, the passages joined with `; ` |
| where the same author treats the same matter in other passages, to be read beside this one | one line, last: `Parallels: <work> (<Author> <Year>, p. <folio>)`, the passages joined with `; ` |

**A comment is one or more comment lines, one to each row of the table that
applies and one to each work a `Cf.` names.** Pass each line to `reference`
as a `--comment` of its own. The highlight's annotation note carries the
lines one beneath another.

**NEVER say in a comment what the note's title says.** The annotation note
opens with the note's link, and a first line that names the same author and
subject says it twice.

**A `Cf.` to another work carries a sentence, NEVER a word or two in
parentheses:** a reader of the page MUST learn from the line what the other
work claims about the passage that the passage does not say. Write the
sentence from the passage of that work that was read, per `AGENTS.md` §1.
NEVER write a `Cf.` sentence that restates the passage: if the other work
only quotes or restates it, name the work under `Discussed in:`.

**A reference takes a comment only where a row of the table applies.** If
none applies, write no comment line. NEVER write a comment that says again
what the passage plainly says.

**A comment names another work only for what that work says of this passage,
for the primary passage this passage discusses, or for a parallel passage of
the same author.** NEVER carry into a comment a
connection the atomic note makes: that a passage supports, opposes, or bears
on what another work holds is the note's own, and it stands in the note, as
a relation, an explication, or the group its reference stands under. A
library PDF is read apart from every note, and its annotations say what
readers of the passage have said of it, never what one note sets it
beside.

**A comment is as short as its content allows: it is read in a small
annotation on the page.** Outside the sentence of a `Cf.` line, write
phrases, and NEVER a sentence where a phrase says it. Name the subject in the fewest words that a search would find, and
add no gloss of the name: its history, its other names, or what the passage
calls it.

**NEVER write in a comment what the page itself tells its reader, or what
only the atomic note makes plain:** the work, the edition, or the lectures
the passage stands in; the translation the passage's own author cites; which
claim of the note the passage bears on; or how the passage's wording stands
to the note's. A point about the note's wording is a task or an
explication. Every folio a comment cites is of a passage read, per "Rigor"
of `retrieval.md`.

**`reference` verifies the quotation before it writes.** Pass the quotation
as the corpus file writes it. If the quotation agrees with the page's words
case for case, apart from ligatures, quotation marks, dashes, and notation,
the reference carries the quotation as passed; otherwise it carries the
page's words, with the notation where the quotation sets it. NEVER write a
reference by hand.

**A transcript is quoted word for word as the transcript carries it.**
`reference` finds the passage in the transcript and cites the time marker
before it, with the recording's link.

**If a corpus file carries `uncitable:`, read the quotation on the PDF page
and pass `--locator` with the chapter and section.** `reference` writes the
locator in place of the folio and closes it with `(folio unverified)`.

**Choose the passage that makes the note's claim.** NEVER write a reference
to a passage that only shares the claim's subject.

**A quotation becomes a highlight, read on the page by a reader who has not
the atomic note: choose a passage that says, by itself, what it is quoted
for.** NEVER quote a passage whose point stands in a sentence the quotation
leaves out, and NEVER leave a sentence out because it carries notation: pass
the notation as the corpus file writes it.

**Quote the whole passage, not the one sentence that matched.** A quotation
runs from where the author takes up the point to where the author leaves it:
the sentence that states the claim together with the sentences that give its
reason, its terms, or its example. A quotation of one sentence is right only
where the sentences around it add nothing to the claim. The fuller quotation
makes the note stand without its source, and makes the highlight in the PDF
cover what bears on the claim.

**The passages of one work that stand on one page, or in one paragraph that
runs on to the next page, are one reference.** Join them in the page's order
with ` […] ` wherever words of the page are left out between them: a note
mark, a marginal number, notation, or sentences that do not bear on the
claim. `reference` verifies each passage and writes one quotation, cited by
the folio of the first passage, or by both folios where the passages run on
to the next page; `highlight` writes a highlight over each passage. NEVER
write two references to one page of one work under one group. If `reference`
refuses a passage of another page, write that passage as a reference of its
own.

**A group holds at most three references when a note is first researched.**
Where more passages bear on the claims, choose the three the claims rest on
most: PREFER the passage that states a claim OVER one that repeats it, and
the passage the secondary literature itself discusses OVER one beside it.
Write one reference if one passage states the claim. Write a fourth
reference to a group only when the user asks for more, or when an `enrich`
task's revision cannot make the point with three.

**An `enrich` task is resolved as a `focus` revision is: in the note
itself.** The note reviewer reads the source the task names, keeps the best
of several references to one source that say much the same thing, and
writes the new source's better passages in place of weaker ones.

**If a claim reports what a thinker holds, write the primary passages under
the group of the primary texts, and the secondary literature that discusses
each under its own group, as `discusses` references.** The comment line of
the primary passage names each `discusses` reference, as `Cf.`, per
"Comments".

**A note that references secondary literature references the primary
passages that literature discusses.** A work roled `secondary` in its corpus
file's `source_role` NEVER stands in a note without a reference to a
primary text, the thinker's own work the secondary literature discusses,
whether or not its corpus file carries a role: write the passages the secondary references discuss, or
that their `Cf.` lines name, under the group of the primary texts, up to
the three a group holds. If the claims set the thinker's idea beside
another primary author's, write that author's passage the secondary
literature discusses under the same group as `supports` or `explicates`:
"One idea, one atomic note" binds the claims, and a primary passage quoted
to bear them out is no second idea. If the library holds no primary passage
the secondary literature discusses, write an `enrich` task naming the
primary work and the folio, and name it in the report. `check` finds a note
whose every reference is to a work roled `secondary`.

**If a claim reports how a work of secondary literature reads a thinker, write
the primary passages that work discusses as well, under the group of the
primary texts.** Read each in the edition the library holds, and write it
though another atomic note quotes the same passage. If the work quotes
another translation than the held one, say so at the close of the `Cf.` or
`Contra:` line that names the work, on the primary passage's comment, and
NEVER on a line of its own.

**A passage arguing a claim's contrary belongs to another atomic note.**
Write no reference to it in the note; if an atomic note holds the contrary
claim, relate the two notes with `contradicts`.

**An unheld work takes no reference.** Name the work as `<Author> <Year>` in
the task whose thread the work bears on, per "Tasks".

### Relations

**A relation is the words `<relation kind> [[<Title>]]`, in an explication or
in a reference's comment line.** `relate` writes a relation as an explication
of its own beneath the last claim.

| Relation kind | The note says of the other note |
| --- | --- |
| `extends` | it carries the other note's claim further |
| `supports` | it gives a reason for the other note's claim |
| `contradicts` | its claim is the contrary of the other note's |
| `example of` | its claim is a case of the other note's |
| `presupposes` | its claim holds only if the other note's holds |
| `descends from` | its idea descends historically from the other note's: takes it up, transforms it, or answers it |

**Relate a note to every note that stands to it genealogically, conceptually,
or as its contrary.** A genealogical relation is `descends from`; a
conceptual relation is `extends`, `supports`, `example of`, or
`presupposes`; a contrary is `contradicts`. Whenever a note is researched or
reviewed, read the claims of every other note of `1 notes/` with `list`, and
judge each note not related to it in either direction: if the two ideas
share a thinker's doctrine, a concept, a lineage, or a debate, write the
relation in the kind that fits. PREFER writing a relation OVER leaving two
kindred notes apart; leave a note unrelated only where its idea shares none
of the four with the note's.

**A relation is written in one atomic note, and NEVER mirrored in the other.**
Obsidian's backlinks show it from the other note. An atomic note relates to
another at most once: if `relate` refuses a second relation, ask the user
whether to change the existing line.

### Tasks

**A task names one further atomic note to take, or, as an `enrich` task,
further reading for this note.** Each task of the four note threads names a
note that follows one thread of the note further, so that the notes together
form a tree in which each note holds one idea and the passages that support
it.

**A task is one line of four parts, in this order:**

| Part | Written as |
| --- | --- |
| its thread | the thread's tag, then ` · `: `#focus · ` |
| the further note | `Take notes on “<Title>”`, the title per "The atomic note"; for an `enrich` task, `Read <the source> for this note` |
| its claim | `: ` then one clause wording the claim the further note would make; for an `enrich` task, what the source adds to this note's idea |
| its passages | `; from ` then each passage read that bears on that claim: a held work as its wikilink `[[<basename>]]` with its folios, an unheld work as `<Author> <Year>` |

| Thread | The task | Once the task is resolved, the note |
| --- | --- | --- |
| `focus` | takes over a matter this note's claims join to their one idea, so that this note holds that idea alone | gains a relation to the further note, and is revised |
| `enrich` | names a source that adds support, detail, or precision to this note's own idea, or a better passage than one the note holds: the same idea, never another | gains or exchanges references, and is revised; no further note |
| `conceptual` | names a different idea, conceptually related, that is needed to understand this note's idea | gains a relation to the further note |
| `genealogical` | names a different idea, historically related, that is needed to trace the lineage of this note's idea: what it descends from, answers, or is received as | gains a relation to the further note |
| `contrary` | names a view or a reading mutually incompatible with this note's claims, which a passage read holds | gains a relation to the further note |

**A task's tag decides its outcome, and the user's change of a tag changes
it.** Resolve a chosen task by the tag it carries, whatever its words:

| Tag | Resolving the task |
| --- | --- |
| `#accept` | accepts every line of the note marked for review, per "Accepting notes" |
| `#enrich` | revises this note with the source the line names; no further note |
| `#focus` | creates a further note that takes over the second matter, then revises this note to its one idea |
| `#conceptual`, `#genealogical`, `#contrary` | creates a further note, and relates this note to it |
| `#discover` | runs Discover on the neighbouring subject, a task of a reading list, per the `discover` skill |

**If the user retags a task to a note thread whose words name no further
note, reword the line before resolving it.** With the Edit tool, rewrite a
retagged task in its thread's form, `#<thread> · Take notes on “<Title>”:
<claim>; from <passages>`: the title per "The atomic note", the claim worded
from the line's words, and its passages kept. Keep the box checked, and name
each title written in the report.

**A task that would only add a source to this note's idea is an `enrich`
task, NEVER a note thread.** Where an author's doctrine differs from the
one the note reports, without disputing how that note's source reads, the
difference is a `genealogical` or `conceptual` task, NEVER a dispute
comment.

**Write the handful of tasks that promise most for further research, the
`focus` threads first.** Judge which threads the passages read open are
worth following, and write those; NEVER pad the list with every thread a
passage touches. NEVER write a task for a thread no passage read opens, and
NEVER name in a task a folio of a held work that was not read.

**A task MAY take notes on a work the library does not hold.** If a passage
read rests on a work the library lacks, the work a load-bearing argument
cites or answers, write a task whose further note takes notes on that work,
titled per "The atomic note" and naming the work as `<Author> <Year>`, with
the folios the citing passage gives, and the citing passage among its
passages. Such a task is a lead to a source the library has yet to obtain.
When it is resolved, the further note's references are the held passages
that report or discuss the work, and the report names the work as unheld,
so that the user can obtain it.

**Write a `focus` task only where the note's claims join a second matter to
their one idea.** A note whose claims hold one idea, each part of it stated
or supported by a passage read, takes no `focus` task. A note MAY take no
task at all.

**If `1 notes/` holds a note for a thread's idea, write no task for the
thread.** Write the relation to that note with `relate`.

**The user chooses a task by checking it, `- [x]`, or by naming it in
chat.** The check is the user's word that the task is to be resolved: NEVER
check a task unless the user names it in chat, and then check that task
alone. NEVER take notes on a task's note before the user chooses the task.
"Resolving chosen tasks" resolves each chosen task and deletes its line.

**The accept task stands first under `# Tasks` and is NEVER deleted, moved,
or rewritten.** `note` writes it, `task` writes every task after it, and
`accept --apply` writes it in a note that lacks it.

**A task bears on the note's claims as they stand.** When the note reviewer
revises a note, it deletes each open task whose thread no longer bears on the
claims, moves to a further note each open task whose thread bears only on the
matter that note took over, and rewrites each open task whose claim the
revision changes. A chosen task stays until it is resolved.

**Resolving `focus` tasks is a loop.** The revision of the reviewed note MAY
open further `focus` tasks, which the user chooses in turn; the loop ends
when the revision opens none.

## Commands

Every command is
`~/.research-vault/venv/bin/python .claude/skills/take-notes/scripts/notes.py <subcommand>`.
Run each writing form only after reading its read-only form's plan.

| Command | Does |
| --- | --- |
| `note "<Title>" [--apply]` | writes a blank atomic note: an empty claim bullet, then an empty `# References`, then `# Tasks` holding the accept task; refuses an existing note, a forbidden character, and a title past 200 bytes |
| `check "<Title>"` | read-only: the note's claims, references, review marks, and open tasks besides the accept task counted, and each finding: a claim count outside one to three, a blank claim, a claim with more than one explication besides its relations, claims and explications past three lines, a heading other than `# References` then `# Tasks`, a reference under no group, a work's references parted by another work's in a group, a reference whose quotation line or source line breaks its shape, a source no corpus file or transcript carries, a relation to a note `1 notes/` lacks, references only to works roled `secondary`, a `# Tasks` that does not open with the accept task; exits 1 if it prints a finding |
| `list` | read-only: every atomic note with its claims, its `projects:`, its `field:`, its counts of references and open tasks, and whether it carries a review mark |
| `claim "<Title>" <N> "<wording>" [--apply]` | words claim N with the review mark: an existing claim, or the next one; refuses a blank wording, a claim past the next one, and a fourth claim |
| `explicate "<Title>" <N> "<explication>" [--apply]` | writes the explication last beneath claim N, with the review mark; refuses a claim the note lacks |
| `reference "<Title>" "<basename>" <quotation relation> "<quotation>" [--comment "<comment line>"]... [--group "<Group>" [--before "<Held group>"]] [--after <M>] [--locator "<chapter and section>"] [--apply]` | verifies the quotation, in the PDF for a corpus file and in its text for a transcript, each passage of a quotation joined with ` […] ` on its own, and writes the reference with the review mark, under its group, or under the group of reference M, beside the group's other references to the same work in the order of its pages; a group the note lacks is written last, or, with `--before`, before the held group `--before` names; refuses a reference given neither `--group` nor `--after`, a `--before` naming a group the note lacks, a `--before` beside a `--group` the note holds, and a `--before` beside `--after`; the plan names each notation span, and each character the PDF sets in a math font, to read on the page, and the reference carries each where the quotation sets it; refuses a quotation `verify` does not confirm, one found on more than one page, an unheld work, and a `--locator` for a corpus file without `uncitable:` |
| `relate "<Title>" <relation kind> "<Other title>" ["<gloss>"] [--stated] [--apply]` | writes the relation as the last explication beneath the note's last claim, with the review mark unless `--stated`; leaves the other note as it is; refuses a note related to itself, a missing note, and a second relation between the same two notes |
| `task "<Title>" "<task>" [--apply]` | writes the task last under `# Tasks`; refuses a task that does not open with its thread's tag, then ` · ` |
| `highlight "<Title>" [--generic "<basename>"]... [--group blue\|green] [--colour <name>] [--apply]` | for each reference of the note that carries the accepted mark and cites a PDF page, writes a highlight over the quotation into the library PDF in the colour "Colour" gives it, and gives each highlight the note already has there the note's present tags and that colour; the plan counts the references not accepted, which take no highlight, and names, per PDF, the colours, each highlight added or merged, the highlights retagged, and each quotation not located; refuses a `--generic` work the note's accepted references do not cite, and a claim comment's passage outside the `--generic` works on a run naming no `--group` |
| `highlights "<basename>" [--tag "<tag>"]` | read-only: every annotation of the library PDF as JSON, each with its file page, the words it covers, its annotation note, its tags, and its colour |
| `chosen [--limit <N>] [--apply]` | one JSON line: under `tasks`, each checked task of every note in the task form, with its reviewed note, thread, title, line, and state, `research` if its further note holds no reference and `review` if it holds one; under `deferred`, the tasks whose further notes fall past the first `N` titles, 8 if absent; under `to_create`, the further notes no note carries yet; under `refused`, each title no note can carry, with the reason; under `retagged`, each retagged task, with its reviewed note and its thread; under `unparsed`, each checked line in no task form, the accept task aside; under `stubs`, each stub note, within what the limit leaves after the tasks, and under `deferred_stubs`, the rest; a done date Obsidian stamps on a checked task is no part of its claim; `--apply` creates each note `to_create` names, its first claim the task's claim |
| `accept [--apply]` | one JSON line: under `accepted`, each note whose accept task is checked, with the count of its lines marked for review; under `accept_task_written`, each note whose `# Tasks` does not open with the accept task; `--apply` writes the accepted mark in place of each review mark of each note under `accepted` and unchecks its accept task, then writes the accept task first under `# Tasks` of each note under `accept_task_written` |

| `reference` refuses with | Do |
| --- | --- |
| `verify does not confirm … reads '<page text>'` | quote the page's words the message shows, and run `reference` again |
| `the passages of one reference stand in the page's order on one page … or run on to the next` | give the passages in the page's order; write a passage of another page as a reference of its own |
| `the quotation appears on more than one page` | quote a longer span that one page alone carries, and run `reference` again |
| `verify finds the quotation on no page` | read the page in the PDF. If the page carries the passage in other words than the corpus file writes, quote the page's words and run `reference` again. Otherwise, write a task naming the work and the folio |
| `the transcript … carries the quotation <N> times, not once` | quote the transcript's words exactly, in a span long enough to be the only one |
| `an unheld work takes a task` | name the work in the task whose thread the work bears on, per "Tasks" |
| `the note holds no group '<Held group>' to write a new group before` | name with `--before` one of the groups the message lists, and run `reference` again |
| `the note holds the group '<Group>' already, and a held group is never moved` | run `reference` again without `--before` |
| `--before places a new group named with --group` | run `reference` again with `--group` and `--before`, without `--after` |

**If the plan of `reference` names a notation span or a math-font character,
read it on the PDF page before `--apply`.** The reference carries the
notation as the quotation passes it: pass the notation in the page's own
characters. If the page sets the notation otherwise than the plan's
reference writes it, write a task that names the work and the folio.

## Highlights

**A reference of an atomic note and a highlight in the library PDF mark one
passage, and the quotation joins them.** `highlight` finds the quotation's
words on the file page the reference's link names; it NEVER deletes an
annotation.

**A passage several atomic notes quote carries one highlight, NEVER one to
a note.** When a note's passage overlaps a highlight the PDF already holds,
`highlight` adds the note's entry to that highlight: the note's link, its
comment lines, and its tags, beneath the entries the highlight has, a blank
line between two entries. The plan reads `MERGED` for such a reference.

| The note's passage | The highlight |
| --- | --- |
| lies within the highlight | keeps its extent |
| runs past the highlight | grows to cover the passage as well; the plan says `highlight extended over the passage` |

A shared highlight NEVER shrinks, keeps the colour it has, and keeps every
other note's entry as that note wrote it. Each note rewrites its own entry
alone.

**A reference that joins several passages of one file page takes one joint
highlight over them all.** If its passages stand on two file pages, each
page takes its own highlight.

**A highlight is written only for a reference that carries the accepted
mark.** NEVER write a highlight for a reference under the review mark, or
for one that carries neither mark: a highlight in a library PDF says the
user read the passage and keeps it.

| A highlight `highlight` writes carries | Taken from |
| --- | --- |
| its annotation note | `[[<Title>]] — ` and the reference's comment line; if the reference has several comment lines, the note's link on a line of its own and each comment line on a line beneath it; the note's link alone if the reference has none, and NEVER a claim of the note; a highlight the note already has takes the comment lines as the note now writes them |
| its tags | the note's `projects:`, then its `field:`, each a `#[[<name>]]` token on the line after the annotation note; a `field:` bibliography whose name the comment carries, in any letter case, stands as its token in the comment, in place of those words, and NEVER again on that line |
| its colour | per "Colour" |

**Colour.** The colour says what a passage is to the work it stands in, so
that a book read with many notes shows a few colours, each with one
meaning. **The comment's kind, per "Comments", gives the colour;**
`highlight` reads the kind from the comment's lines, and the orchestrator
decides two things alone:

| The orchestrator decides | Pass |
| --- | --- |
| which works treat the note's subject as part of their own topic, a primary or a secondary work, so that a claim comment there takes `yellow`: every work, unless the note's passages in it digress from its core topic into a subtopic it treats in passing | `--generic "<basename>"` for each |
| the note's group, which a claim comment in a digressing work takes: `blue` for theoretical philosophy (logic, language, mathematics, science, metaphysics, causality), `green` for practical philosophy (ethics, politics, aesthetics, religion) | `--group blue` or `--group green`, on every run; `highlight` refuses a claim comment's passage on a run naming none |

**Most highlights in the vault are yellow or gray.** Orange, blue, and green
are rare, so that on the page each says something is going on: an
interpretive debate turns on the passage, or the author digresses from the
work's core topic.

A dispute comment takes `orange` and a pointer comment `gray` in every work,
a `--generic` work among them: a secondary work's passage that needs no more
than a pointer to the primary passage it discusses is gray, so that yellow
marks only the claims the work itself makes. If the user names a colour for a case, pass
`--colour`, which overrides the kind in every work not named `--generic`.
If a highlight's colour is wrong, the comment's kind is wrong: correct the
comment, NEVER the colour alone.

**`red`, `purple`, and `magenta` are reserved.** NEVER pass one unless the
user names it for the case: each reads poorly through the page.

**Every run recolours the note's own highlights to this table.** A highlight
another note's entry shares keeps the colour it has. Pass the same
`--generic` and `--group` on every later run for the note.

| `highlight` reports or refuses | Do |
| --- | --- |
| a quotation under `quotations_not_located` | the page's word order breaks the quotation, at a column, a footnote, or a figure: report the quotation to the user as not highlighted, and NEVER place the highlight by another means |
| `no such PDF` | report the reference's source to the user: the library holds no PDF under that basename |

**A reference that cites a transcript, or a corpus file by chapter and
section, takes no highlight.**

## Unattended runs

**An unattended run of this skill is a run the user does not watch.** It is
a delegation whose `Run:` reads `unattended (write)`, or a `resolve-tasks`
run with `unattended: true`. Its rules override each step of an operation
that conflicts with them.

- **Write only in `writing/1 notes/`.** NEVER write a highlight into a PDF,
  a project file, a bibliography, or any other file.
- **Change or delete only a line that carries the review mark.** NEVER
  change or delete a line with no mark or with the accepted mark. The review
  mark shows what a run added or reworded, never what it removed. A
  reference's source line and comment line take the mark of its quotation
  line.
- **Close every line the run writes with the review mark,** per "What is
  written, and how it is marked". `note` and `chosen --apply` MAY write the
  blank note of a new atomic note.
- **Write no task, and NEVER check or uncheck one.** A task takes no review
  mark. Name in the report each task the passages read open.
- **Write no field.** The frontmatter carries no review mark. Name in the
  report the bibliographies the note's field would hold.
- **NEVER run `accept`, and NEVER delete a resolved task's line.** A chosen
  task stays checked for an attended run.
- **Reword a claim only if it carries the review mark.** Name in the report
  each claim left as it stands.

**Tell each worker of an unattended run that the run is unattended.** Close
its prompt with the line `This run is unattended: follow "# Unattended runs"
of your instructions wherever it overrides a step.`

## Operations

### Creating a note

Precondition: the user asks for an atomic note, or an operation calls for
one.

1. If `writing/1 notes/` holds a note for the idea, name it to the user and
   use it.
2. Otherwise, run `note` with the idea's title; read the plan; run it with
   `--apply`.
3. Write each claim the user states with `claim`.

### Researching a note

Precondition: the user names an atomic note, or states a rough claim for a
new one.

1. If the note does not exist, create it per "Creating a note".
2. Read the note. A line without the review mark is the user's.
3. Search, choose the works, and read, per
   `.claude/skills/answer-questions/reference/retrieval.md`, taking each claim as the
   question.
4. For each claim, choose the passages per "References". PREFER a passage
   that `states` the claim OVER one that `supports` it, and either OVER one
   that `explicates` it; the lower relation is written when it adds what the
   higher ones lack.
5. If a claim reports what a thinker holds, find the secondary literature on
   each primary passage with `cited_by` and `contexts`.
6. Settle the note's groups per "References", then write each passage with
   `reference` and its `--group`, and `--before` where "References" calls
   for it: read the plan, then run it with `--apply`.
   Follow the refusal table.
7. Reword each claim with `claim` so that it states what the note's
   references state or support, unless the claim carries the accepted mark,
   and fill the three lines per "What is written, and how it is marked",
   adding explications with `explicate`.
8. Relate the note per "Relations": run `list`, judge every note not related
   to this one in either direction, and write each relation with `relate`.
9. Write the note's tasks per "Tasks", each with `task`. If the note carries
   no `field:`, write its field per "Setting a note's field" of the
   `manage-projects` skill, with
   `~/.research-vault/venv/bin/python .claude/skills/manage-projects/scripts/projects.py classify`.
10. Run `check`. Correct each finding in a line this operation wrote.
11. Report once, in chat: each claim reworded, with its first wording and
    what the new wording drops or adds; each part of the first wording no
    passage read states or supports; the field written;
    the references written, by quotation relation; the relations; the
    tasks, each by its thread; each quotation `reference` refused; and each
    finding of `check` in a line the user wrote.

### Accepting notes

Precondition: the user asks for the checked notes to be accepted, or the
`resolve-tasks` workflow returns notes under `accepted`.

1. Unless the workflow ran it, run `accept`; read the plan; run it with
   `--apply`.
2. For each note under `accepted` that holds a reference, run "Highlighting
   a note's references".
3. Report once, in chat: each note accepted, with its count of lines; each
   note the accept task was written in; and what "Highlighting a note's
   references" reports per note.

### Highlighting a note's references

Precondition: the user says a note is reviewed, asks for a note's
highlights, or asks for a note's tags to be carried into its highlights.

1. Run `highlight` with the note's title; read the plan; run it with
   `--apply`.
2. Follow the table of "Highlights" for each report and refusal.
3. Report once, in chat, per PDF: the highlights added, merged, and
   retagged, the colour, and each quotation not highlighted; then the count
   of references not accepted, which took no highlight.

### Writing notes from a PDF's highlights

Precondition: the user names a held work and asks for atomic notes from its
highlights.

1. Run `highlights` with the work's basename, and with `--tag` if the user
   names a tag.
2. Group the highlights by the claim each bears on: highlights whose
   annotation notes state one idea form one group. A highlight whose
   annotation note already opens with `[[<Title>]] — ` belongs to that atomic
   note.
3. For each group, create the atomic note per "Creating a note", unless one
   exists for the idea. Word its claims from the annotation notes of the
   group, with `claim`.
4. Write each highlight of the group with `reference`, passing the words the
   highlight covers as the quotation and its annotation note as `--comment`.
5. Run `check` on each note. A highlight gains its note's link and tags once
   the user accepts its reference and "Highlighting a note's references"
   runs.
6. Report once, in chat: each note written or extended, its references, each
   highlight no group took, and each quotation `reference` refused.

### Researching a batch of notes

Precondition: the user names several atomic notes, or a set of rough claims.

1. Create each note that does not exist, per "Creating a note".
2. Dispatch one note researcher per note, at most four in one message: invoke
   the Agent tool with `subagent_type: note-researcher` and no `model`. The
   prompt carries the note's title, and the unattended line if the run is
   unattended, per "Unattended runs".
3. If a note researcher returns `{"error": …}` or no JSON object, dispatch it
   once more. If it fails again, name the note in the report and go on.
4. Run `check` on each note.
5. Report once, in chat, per note: what the note researcher reports, and each
   finding of `check`.

### Resolving chosen tasks

Precondition: the user asks for the chosen tasks to be resolved, or the
stub notes to be researched, of every atomic note or of the notes the user
names.

**The `resolve-tasks` workflow, `.claude/workflows/resolve-tasks.js`, runs
the operation unattended.** It takes two kinds of work, the chosen tasks
first and the stub notes within what the limit leaves. Its steps:

| # | Step | Run by |
| --- | --- | --- |
| 0 | `notes.py accept --apply`: each note whose accept task is checked accepted, so that no worker changes its lines; an unattended run skips it | relay |
| 1 | `notes.py chosen --limit <N> --apply`: every checked task of every note in the task form, each further note created with the task's claim as its first claim, the stub notes, and the tasks and stubs past the limit deferred | relay |
| 2 | one note researcher per further note that holds no reference and per stub note, all at once; a further note two notes chose is researched once, and a stub note takes no note reviewer | note researcher |
| 3 | one note reviewer per reviewed note, once each of its further notes is researched, its prompt carrying each task whose further note was researched and each chosen `enrich` task, which the reviewer resolves in the note itself and which takes no researcher | note reviewer |
| 4 | `notes.py chosen` again: each task of the run still standing | relay |

A worker that returns `{"error": …}` or no JSON object is dispatched once
more; a task whose note researcher fails twice stays checked for the next
run, and its reviewed note is reviewed for its other tasks alone.

1. If the user names tasks in chat, check each one. If the user names
   notes, resolve only the checked tasks of those notes: pass no other note's
   task to the workflow, by asking the user to uncheck the others first.
2. Run `notes.py accept` and `notes.py chosen`, and read their plans. Reword
   each task under `retagged` per "Tasks", then run `notes.py chosen` again.
   If `accept` lists no note under `accepted` and `chosen` lists no task and
   no stub, tell the user that no checked accept task, checked task, or stub
   note stands, and name each line under `unparsed`.
3. Invoke the Workflow tool with `name: "resolve-tasks"` and
   `args: {"limit": <N>}`, `N` the user's cap, or 8 if the user names none.
   If the run is unattended, add `"unattended": true` to `args`.
4. Run `check` on each note the run wrote.
5. For each note the workflow returns under `accepted`, run steps 2 and 3 of
   "Accepting notes", and report them with the rest of the run.

**An unattended run skips step 1, `accept` and the rewording of step 2, and
step 5.** It reports each retagged task as it stands.
6. Report once, in chat, per reviewed note: each further note, with what its
   note researcher reports; then what the note reviewer reports, per
   "Reviewing a note"; then each stub note, with what its note researcher
   reports, per "Researching a note"; then each task still standing,
   deferred, refused, or unparsed, and each stub deferred, with its reason;
   and each finding of `check`.

### Reviewing a note

Precondition: the user asks for an atomic note to be reviewed. The
`resolve-tasks` workflow dispatches the note reviewer itself, per "Resolving
chosen tasks", and reports what it returns.

1. Dispatch one note reviewer on the note: invoke the Agent tool with
   `subagent_type: note-reviewer` and no `model`. The prompt carries the
   note's title and, for each task resolved in the same operation, the
   task's line and its thread; if none was resolved, the prompt says so.
2. If the note reviewer returns `{"error": …}` or no JSON object, dispatch
   it once more. If it fails again, stop and ask the user.
3. Run `check` on the note, and on each note the note reviewer moved a task
   to.
4. Report once, in chat: the relations written, those to the further notes
   and those the sweep of "Relations" found; the parts of the claims the
   further notes took over; each claim reworded, with its new wording and what
   it drops or adds; the field written; the references taken out and
   written; the tasks
   deleted, moved, and written, each by its thread, or that the revision
   opened no `focus` task; each line left because it carries the accepted
   mark; and each finding of `check`.
