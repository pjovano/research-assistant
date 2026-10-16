# research-tools

The control plane of a personal research vault: a library of PDFs, the
Zotero records that identify them, a derived corpus of Markdown text built
from them, and a retrieval layer that answers research questions from that
corpus with every quotation verified against the page it was printed on.

The vault itself lives outside this repository, in `~/Documents`, and is
synced between two Macs through iCloud. This repository holds everything
that operates on it: the contract, the skills, the worker instructions, the
shared code, and the tests. It is run by Claude Code, which reads
`CLAUDE.md` as its standing instructions and each skill as the procedure for
one operation.

## What the vault holds

| Part | Path | Is |
| --- | --- | --- |
| library | `library/` | the cleaned PDFs, one per Zotero record; edited volumes in `library/volumes/`, with the chapters cut from them filed as works of their own |
| derived corpus | `research vault/corpus/` | one corpus file per PDF: frontmatter identifying the work, then the work's own text structured by its own headings, with a page marker where each printed page begins |
| talk transcripts | `research vault/corpus/talk transcripts/` | one transcript per recorded talk the user gave a URL for: frontmatter identifying the talk and linking its recording, then the talk and its discussion as the transcript reviewer made them readable, speakers named, with a time marker where each utterance begins; the audio is never kept |
| bibliographies | `research vault/bibliographies/` | one note per topic, and one per approved author, filed under `1 historical periods/`, `2 authors/`, or `3 topics/`; each lists the notes one level beneath it, so the notes form a tree |
| writing | `research vault/writing/` | the user's writing, kept as a Zettelkasten: `1 notes/`, one atomic note per idea, its one to three claims with their sources and tasks; `2 projects/`, one project file per project, an Excalidraw board: its parents and children in its frontmatter, a card for each atomic note and an arrow for each relation between two of them, and its research question, abstract, drafts, tasks, and reading list shown on the board; `3 drafts/`, every version of every draft; `4 published/`, the finished pieces; the research assistant writes there when the user asks, and changes the user's prose only on request |
| reading lists | `research vault/bibliographies/4 reading lists/` | one reading list per project, the works that bear on its questions as wanted or held, each wanted entry checked off by a batch once its work is placed on a bibliography; and the reading lists Discover produces, saved here when the user asks to keep one; none is a bibliography |
| inbox | `~/Desktop/inbox/` | new PDFs awaiting ingest |
| search stores | per machine, outside the vault | an embedding store and a full-text store built over the corpus, rebuilt rather than synced |

`research vault/` is an Obsidian vault. Every note is Obsidian Markdown, and
every link between notes is a wikilink, so Obsidian's graph shows which
works cite which and which topics hold which works.

## What happens to a PDF

A PDF dropped in the inbox passes through six stages in order. Each stage is
one skill in `.claude/skills/`, with its own scripts and, where judgment is
needed over many pages, a worker in `.claude/agents/` that reads the pages so
the main session does not have to.

| # | Stage | Skill | Does | Tools |
| --- | --- | --- | --- | --- |
| 0 | Clean | `clean-pdfs` | judges whether the PDF is an article, a book, or an edited volume; strips old annotations; repairs broken fonts so the text layer emits the characters the page shows; judges the cover; writes the outline (bookmarks) from the printed table of contents | PyMuPDF and pikepdf for the PDF; macOS Vision OCR (through `ocrmac`) as the pixel check that reads a rendered line and compares it with what the font emits; a worker that names glyphs no rule resolves |
| 1 | File | `file-pdfs` | finds the work's identifiers (DOI, ISBN, arXiv) and resolves them to a record; creates the Zotero record; lets Zotero place and name the PDF in the library; writes the corpus file's frontmatter | Crossref and the other identifier services; the Zotero connector; ZotMoov, the Zotero plugin that names and places the file |
| 2 | Extract | `extract-corpus` | converts the PDF to Markdown, either from the text layer or, for scans and pages with mathematical notation, from pixels; puts every page through the page checks, a language-independent quality gate, before anything is written; leaves out front matter, index, and publisher's pages | marker (with the surya models) as the conversion engine; a worker that judges the scope of what to leave out, and one that reads doubtful pages by eye |
| 3 | Link citations | `cite-links` | parses every entry of the work's reference list and every footnote, and every entry of the other corpus files that names the work's author; where one names a work the library holds, adds a wikilink to it; brings the citation graph up to date | a citation parser, `SIRIS-Lab/citation-parser-ENTITY`, run through Hugging Face transformers; fuzzy matching through rapidfuzz; the graph store in SQLite, with Louvain clustering through networkx |
| 4 | Classify and place | `classify-and-place` | reads the corpus file's opening and its neighbours in the citation graph, and records the work's type and role, a one-sentence description, and the topics it belongs to; adds it to each topic's bibliography | a worker on Sonnet that judges from the opening, informed by the graph; a script that writes the fields and places the work |
| 5 | Gloss | `gloss-bibliographies` | copies each work's description onto its listing on every bibliography as the listing's gloss, then writes each touched bibliography's introduction, a note on each of its groups, and the group of each unsorted work | a script that copies, lists, checks, and writes; one worker on Sonnet, the bibliography introducer, per bibliography |
| 6 | Index | `search` | syncs the search stores over the corpus, incrementally | Ollama with `qwen3-embedding:4b` for the embeddings, stored in ChromaDB; SQLite full-text search; optionally a reranker through llama-server |

The `ingest` workflow, `.claude/workflows/ingest.js`, runs a batch: it
carries each PDF through Stages 0 to 4 on its own, then runs the
bibliographies check beside the citation sweep, the reshaping (a worker
that creates bibliographies and moves works on the citation graph's
evidence), the check-off (each wanted entry of a project reading list whose
work is now placed on a bibliography moves under held), Stage 5 on each
bibliography the batch touched, and Stage 6, once. Stage 0 runs per PDF,
at most four at once; Stage 1 files one PDF at a time,
because there is one Zotero connector; Stage 2 converts one PDF at a time on
the engine; Stage 3 links each work as Stage 2 accepts it, and sweeps every
corpus file once per batch; Stage 6 runs once per batch, last.
Every script has a read-only form that reports what it would do and a
writing form that does it, and the writing form runs only after the
read-only output has been read.

Edited volumes take one extra step: `extract-chapters` cuts the chapters the
user names out of a volume into the inbox as standalone PDFs, each carrying
the volume's collected bibliography and endnotes, and each then passes
through the stages as a work of its own.

## What happens to a recorded talk

A YouTube URL the user gives, or the new videos of a playlist the user keeps
and names in `machine.json`, pass through `transcribe-talks`: `yt-dlp`
fetches the audio and the recording's record;
whisper.cpp transcribes it and pyannote labels the speakers by voice; a
worker, the transcript reviewer, reads the raw transcript part by part and
writes the version a reader can follow, with the speakers named, garbled
passages reconstructed from context, the chair's chatter dropped, and the
talk and the discussion under headings; a check passes or fails the review;
and `file` creates the Zotero record, a presentation by its presenters, and
writes the transcript into `research vault/corpus/talk transcripts/`, deleting the
audio.
Stage 4 then places the transcript under `## Talk transcripts` on its
bibliographies, and Stage 6 indexes it, so a research question searches
talks beside works. A transcript is paraphrased in an answer and cited by
its time marker, never quoted: it is a model's reading of a recording, not a
page.

## What the vault answers

Four operations run on a research question or request rather than on a
PDF.

| Operation | Skill | Does |
| --- | --- | --- |
| Answer questions | `answer-questions` | searches the corpus (embeddings and full text fused, optionally reranked), grades the hits, builds the answer from the corpus files, and verifies every direct quotation against the PDF before delivering it; cites by the printed page number, never the file page |
| Discover | `discover` | builds a reading list from what the held works cite and from a literature search outside the vault (Google Scholar, publishers, PhilPapers), grades it against a rubric, and delivers it as a document, which the user keeps under `bibliographies/4 reading lists/` |
| Annotate | `annotate-pdfs` | writes highlights with notes into a library PDF, on a question or across a whole work; the highlights are real PDF annotations, editable in any reader |
| Manage projects | `projects` | keeps an atomic note for each idea the user keeps, its claims with their sources and tasks, and a project file for each writing project, cuts a draft's next version when asked, builds a project file from a draft, carries the claims and passages agreed in discussion into atomic notes, and publishes a finished draft |

Two rules govern all four. The tools report what each author argues and
never evaluate it. And nothing is written into the library or the retrieval
layer as an answer: an answer lives in chat, or in a document the user keeps
under `writing/` or `bibliographies/4 reading lists/`, and the library and the retrieval layer
hold only the works and what is derived from them.

The `search` skill also runs an MCP server, `vault-rag`, registered in
`.mcp.json`, through which the session searches the corpus, reads a work's
heading tree and frontmatter, and walks the citation graph.

## Repository layout

| Path | Holds |
| --- | --- |
| `CLAUDE.md` | the contract: the mandate, the architecture, the conventions, the operations, and the standards |
| `.claude/settings.json` | permissions and hooks; one hook runs the checks after every edit to a Python or Markdown file, the affected test modules among them, another turns every destructive command into a permission prompt |
| `.githooks/` | the pre-push hook, which runs the test suite, the linter, and the audit linter before every push |
| `.claude/skills/<skill>/` | one skill per operation: `SKILL.md`, its `scripts/`, and any `reference/` files it loads |
| `.claude/agents/` | the worker instructions, one file per worker |
| `.claude/workflows/` | the saved workflows: `ingest.js`, which runs a batch |
| `lib/` | the shared code: `vault.py` resolves the vault's paths; `pagetext.py` reads pages; `references.py` parses citations; `rag.py` builds and queries the search stores; `annotate.py` writes annotations; `zotero.py` talks to Zotero |
| `tests/` | the suite, run with `python -m unittest discover -s tests` under the vault's own Python environment |
| `requirements.txt`, `requirements.lock` | the dependencies and the exact versions both machines run |
| `pyproject.toml` | the ruff configuration |
| `.github/` | the CI workflow, a lint job, an audit job, a publish-guard job, and a test job, all on Ubuntu, on every pull request and push to `main`; and the composite action that points the vault at an empty directory |
| `.gitleaks.toml` | the publish guard's secret scan: gitleaks's default rules, less the citation keys and the audit baseline's digests |
| `.mcp.json` | registers the `vault-rag` server |

Two standards bind every change. `clean-code` holds the code to Robert
Martin's Clean Code, and `clean-prose` holds every instruction file to a
fixed vocabulary and sentence form, so that a worker reading nothing but its
own instructions can tell what binds it. Both are skills in this repository
and are invoked before any edit.

Per-machine values, such as where the search stores live, sit outside the
repository in `~/.research-vault/machine.json`, and the models the engines
run on live in each machine's own caches. Nothing in the repository names a
machine or an absolute path.

## Running it

The tools run on a Mac with Claude Code, and `~/Developer/research-tools`
opened as the project folder.

1. Clone the repository to `~/Developer/research-tools`.
2. Write `~/.research-vault/machine.json`. Every key is optional: `vault_dir`
   (default `~/Documents`), `rag_dir` for the search stores,
   `crossref_mailto` for the identifier lookups, `batch_update_minutes` for
   the interval of the batch update (default 30), and the reranker's
   `reranker_model`, `reranker_pooling`, and `llama_server`.
3. Build the Python environment from the lock, so both machines run the
   versions the suite passed on:

       uv venv --python 3.12 ~/.research-vault/venv
       uv pip sync --python ~/.research-vault/venv/bin/python requirements.lock

   If the machine does not run macOS, set `UV_TORCH_BACKEND=cpu` for every
   `uv pip sync`: there the lock resolves torch to its CPU build, which only
   the PyTorch CPU index serves.

4. Install the models: pull `qwen3-embedding:4b` into Ollama, and download
   the citation parser once with the command the `cite-links` skill names,
   and fetch the tokenizer encoding once with the command the `search` skill
   names.
   The engine's models download on the first `fonts scan` and the first
   `extract`: run each once from a terminal with `HF_HUB_OFFLINE` unset. The
   harness sets `HF_HUB_OFFLINE=1`, and a download fails under it.
5. Install Zotero with ZotMoov and the Zotero connector.
6. For recorded talks: `brew install yt-dlp ffmpeg whisper-cpp`, download a
   whisper.cpp model and name its path in `machine.json` under
   `whisper_model`, and download the diarization model once with the command
   the `transcribe-talks` skill names, after accepting its terms on Hugging
   Face. The skill's setup table states each step.
7. Run the suite:

       ~/.research-vault/venv/bin/python -m unittest discover -s tests

8. Open the repository as the project folder in Claude Code and drop a PDF
   in `~/Desktop/inbox/`.
