---
name: search
description: "Stage 6 — sync the search stores over the derived corpus once per batch, after Stage 5, and serve hybrid search over MCP to Answer questions: local embeddings through Ollama, full text through SQLite, an optional reranker through llama-server."
allowed-tools: Bash(~/.research-vault/venv/bin/python .claude/skills/search/scripts/search.py:*)
---

# search (Stage 6, run inline)

**Stage 6 is a deterministic script.** Outside a batch, the orchestrator
runs it inline. In a batch, the `relay` worker runs it through
`ingest.py drive-index`, detached through `ingest.py drive-detach`. NEVER dispatch it to any other worker.

## Parts

| Part | Is | Run by |
| --- | --- | --- |
| `scripts/search.py` | the CLI, whose commands are tabled below | the orchestrator |
| `server.py` | the `vault-rag` MCP server exposing `search_hybrid`, `get_frontmatter`, `list_works`, `index_status`, `outline`, and the citation graph tools `cites`, `cited_by`, `neighbours`, and `contexts`, which read the corpus files and the graph store, never the search stores | `.mcp.json`, long-lived |

Both call `lib/rag.py`, so hybrid search behaves identically in both.
`cites` and `cited_by` call `lib/references.py`, as `cite.py cites` and
`cite.py cited-by` do; `neighbours` and `contexts` call
`lib/citation_graph.py`, as `graph.py neighbours` and `graph.py contexts` do,
and the `cite-links` skill states what each returns. Each returns
`{"error": …}` for a basename the vault does not hold.

**`server.py` releases its models after five minutes with no tool call:** it
stops the reranker's `llama-server` and lets go of the embedding store, and
the next tool call loads both again. NEVER keep them loaded for the life of
the session: a session that searched once would hold more than 2 GB while it
sat idle.

**`outline` is a work's heading tree, read from its corpus file, never from
the search stores:** the parents table lacks a heading's level, drops a
heading with no prose of its own, and lags the corpus file until the next
sync. Each entry carries the heading path, the level, the first and the last
folio the section spans, the first file page, and the section's own word
count; the report carries the work's word count. A section's last folio is
the last folio printed before the next heading at its level or above, so a
section reaches the page its successor begins on. An unknown basename
returns `{"error": …}`.

## What the search stores hold

**The search stores are the embedding store and the full-text store, built
over the body of every corpus file and every transcript.** The indexed text
is the body with the first-line link to the PDF or the recording, the
wikilink brackets, and the work's own bibliography section removed; the
page markers in the body supply each chunk's folio range, and the time
markers of a transcript its time range.

**Every child is embedded and indexed under its chunk context.** The chunk
context is two lines: the work label, then the child's heading path; a child
with no heading path carries the work label alone. The work label is the
work's authors joined with `and`, its year, and its main title, as
`<A and B>, <Year>, <Title>`; if the frontmatter lacks any of the three, the
work label is the basename. The embedded text of a child is its chunk
context, then its text with every notation span, `$…$`, `$$…$$`, or the legacy `❲…❳`, removed.
The full-text store indexes the chunk text as written in its `text` column,
so a search for a symbol or a macro still hits, and the chunk context in its
`context` column at a quarter of the weight of the text: a query naming an
author or a title reaches that work's chunks, and a body match outranks a
match in the context alone. The chunk context NEVER enters a chunk's text:
what search returns is the work's own words.

| Store | Holds | Where |
| --- | --- | --- |
| embedding store | one vector per child chunk, from `qwen3-embedding:4b` through Ollama, with the model's name recorded in the collection; a query is embedded with an instruction prefix, a chunk without | `<rag_dir>/chroma/` |
| full-text store | every parent and child chunk with its metadata, each child's chunk context, the full-text index over the children's text and chunk context, and the manifest of what is indexed | `<rag_dir>/fulltext.sqlite` |

**A chunk is a child or a parent.** A parent is one section of a work, split
at paragraph boundaries into pieces of at most 1,024 tokens; a child is a
piece of a parent of at most 256 tokens, never cut inside a notation span, a table,
or a footnote definition. Search matches children and returns their parents.
Every chunk carries the work's basename, its heading path, the first and
last folio and file page it spans, and, in a transcript, the first and last
time marker it spans. A chunk's id is a hash of its embedded
text, so a sync re-embeds only the chunks whose text or chunk context
changed. The manifest records each work's content hash under the chunking
version; a change to how chunks are cut or contextualized bumps the version,
and the next `sync` re-chunks every work and prunes the old chunks.

**The search stores are per machine and rebuildable.** They live at
`~/.research-vault/rag/`, or at the path `~/.research-vault/machine.json` names
in `rag_dir`; `sync --rebuild` regenerates them from the corpus.

## Models

| Role | Model | Runner | `machine.json` key | Default |
| --- | --- | --- | --- | --- |
| embedding | `qwen3-embedding:4b` | Ollama, at `ollama_url`, held in memory for `ollama_keep_alive` after each call | `embedding_model`, `ollama_url`, `ollama_keep_alive` | `qwen3-embedding:4b`, `http://localhost:11434`, `5m` |
| reranking | `bge-reranker-v2-m3` as a GGUF file | `llama-server --reranking --pooling <reranker_pooling>`, on `127.0.0.1:8790`: `search.py query` starts it per query and stops it after; `server.py` holds it for its lifetime | `reranker_model` (the file's path), `reranker_pooling` (the pooling llama-server runs the model under), `llama_server` (the binary) | none; `rank`; `llama-server` on the PATH |

The models live outside the vault, in the primary's own caches. Installing
them is the user's step, once, on the primary: pull `qwen3-embedding:4b` into Ollama, and
place the reranker GGUF at the path `reranker_model` names. If
`reranker_model` is absent or names no file, search runs without the
reranker and says so in every result.

**The chunker counts tokens with tiktoken's `cl100k_base` encoding**, cached
under `~/.research-vault/tiktoken`. Fetching it is the user's step, once, on
the primary, from a terminal: the sandbox denies its host.

    TIKTOKEN_CACHE_DIR=~/.research-vault/tiktoken ~/.research-vault/venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

If `sync` fails naming the encoding, stop and ask the user to run that step.

**The reranker is probed before its first real query in a session.** The
probe scores one fixed query against one matching and one unrelated passage.
If the unrelated passage scores at or above the matching one, or both scores
are below 1e-6 in magnitude or equal, the reranker is unavailable for the
rest of the session, every result carries a `warning` naming the probe's
scores, and the results are the fused ordering: llama-server returns
degenerate scores for some rerankers under some pooling settings.

**If the probe fails, change the pooling once.** If the probe fails under `rank`, set
`reranker_pooling` in `machine.json` to the pooling the model's own
documentation names and query again; if it fails under every pooling, leave
`reranker_model` unset. A result list the reranker ordered carries a
`reranker: used` entry.

## Procedure

**Precondition: in a batch, Stages 3 and 4 have run on every corpus file in it.** In
a backfill, Stage 6 MAY run before Stages 3 and 4, as `AGENTS.md` §4 states:
a later classification or wikilink costs one re-chunk and no embedding call.

**Precondition: Ollama is running with `qwen3-embedding:4b` pulled.** If it is not,
`sync` exits 1 with an `error` naming the cause: start Ollama, or pull the
model, and run `sync` again. NEVER run `sync --rebuild` to recover from a
missing model: the rebuild fails the same way after emptying the stores.

1. Sync:

       ~/.research-vault/venv/bin/python .claude/skills/search/scripts/search.py sync

   `sync` hashes each corpus file and each transcript, re-chunks the changed ones and, after a
   chunking version bump, every one, embeds only the chunks not yet in the
   embedding store, and prunes the chunks and the works that no longer
   exist. If `sync` exits non-zero with an `unreadable` list, each note it
   names carries frontmatter that does not parse: the rest is synced, and
   the named notes keep their old chunks; stop and ask the user to repair
   them. If `sync` exits non-zero otherwise, run `status`.
2. Verify:

       ~/.research-vault/venv/bin/python .claude/skills/search/scripts/search.py status

   `status` cross-checks the manifest, the full-text store, and the
   embedding store, and exits non-zero when they disagree. If `status` exits
   non-zero, run `sync` again, then `status`: an interrupted sync leaves
   vectors the manifest does not record, and a second `sync` reconciles
   them. If `status` still exits non-zero, run:

       ~/.research-vault/venv/bin/python .claude/skills/search/scripts/search.py sync --rebuild

   If `sync --rebuild` exits non-zero, stop and ask the user.

**An embedding store carries the name of the model that filled it.** If the
configured `embedding_model` differs from the recorded one, `sync` refuses
and names `sync --rebuild`, and `status` reports the disagreement: vectors
from two models in one collection are not comparable. The first sync on a
machine, and every change of `embedding_model`, MUST be `sync --rebuild`.

**A full-text store built before the `context` column is upgraded when
opened:** the column is added, empty, and the index rebuilt over it. The
manifest survives the upgrade, so the next `sync` re-chunks every work and
prunes the old vectors; no rebuild is needed.

**Postcondition:** every corpus file with a body, and every transcript, is
reachable through `search_hybrid`.

**After a sync that adds or changes vectors, ask the user to reconnect the
`vault-rag` server.** The full-text store is read fresh per query, but a
chromadb process caches the embedding store's index in memory and keeps
serving the index it first loaded, and the orchestrator cannot restart the
server. Until the user reconnects it, say in each answer that a work synced
since is reachable by full text alone.

## Verifying the models

Before the first sync on a machine, run:

    ~/.research-vault/venv/bin/python .claude/skills/search/scripts/search.py check-embeddings

It embeds paired passages in German, French, Latin, and Greek with their
English counterparts and one unrelated passage, and reports for each passage
whether it sits closer to its pair than to anything else in the set.

| Group | Languages | Force |
| --- | --- | --- |
| blocking | German, French, Latin | a failure exits non-zero |
| advisory | Greek | a failure is listed under `advisory_failures` and the check still passes |

If the check exits non-zero, stop and tell the user which pair failed: the
embedding model is not serving the languages retrieval depends on. Greek is
advisory: if the Greek pair fails, a Greek passage is still
reached through the full-text store, so `answer-questions` still queries Greek terms.

## Conflict copies

**`rag_dir` NEVER names a path inside the vault:** iCloud syncs such a path and
resolves a torn sync by leaving a conflict copy beside the store, which
`status` does not detect. List `RAG_DIR`; a sibling of `chroma/` whose name
begins with `chroma`, or of `fulltext.sqlite` whose name begins with
`fulltext`, is a conflict copy. Report every conflict copy to the user and
ask before deleting it; once they are gone, run `sync --rebuild`.

## Commands

| Command | Does | Writes |
| --- | --- | --- |
| `search.py status` | reports counts, the stale or unindexed works, whether the stores agree, `embedding_model` beside the `recorded_embedding_model` the collection carries, and under `reranker` whether the reranker is configured or why it is unavailable; `chroma_chunk_count` is `null` before the first sync; exits non-zero on disagreement | nothing, except the one-time schema upgrade above when it opens an older store |
| `search.py sync` | syncs new, changed, and deleted corpus files into the stores; after a chunking version bump, re-chunks every work; prints one line per work to stderr as it goes; lists under `unreadable` every note whose frontmatter does not parse, and exits non-zero | the stores |
| `search.py sync --rebuild` | empties the stores and syncs every corpus file | the stores |
| `search.py query "<text>"… --k 8 [--no-rerank]` | hybrid search from the CLI over one query or several: every query's full-text and vector candidates are fused by reciprocal rank in one fusion, reranked once when the reranker is available, and each parent is returned once. A result carries the parent's text, the offsets of the matched child within it, the heading path, the folio range, and the file pages | nothing |
| `search.py chunks <basename>` | prints the stored parents and children of one work | nothing |
| `search.py outline "<basename>"` | prints the work's heading tree as `outline` returns it; exits non-zero on an unknown basename | nothing |
| `search.py check-embeddings` | the multilingual check above | nothing |

## Failure branches in a result

| Entry in the results | Meaning | Do |
| --- | --- | --- |
| `{"warning": "reranker unavailable: …"}` | the results are the fused hybrid ordering; a cause beginning `reranker probe failed` names the probe's scores | say so in the answer |
| `{"reranker": "used: …"}` | the reranker ordered the results | nothing |
| `{"warning": "… keyword-only …"}` | the embedding model was unreachable; the results are full-text only | say so in the answer; start Ollama before the next query |
| `{"warning": "stale: …"}` | a named work changed since it was indexed, or was never indexed | run `sync`, then ask the user to reconnect the `vault-rag` server |

## Invariants

- `sync` runs only when invoked: no watcher exists.
- Nothing in the stores is quoted. A hit names a work and a passage to open
  in the PDF (`answer-questions` skill).

## The ingest workflow

**The `ingest` workflow runs Stage 6 once per batch through `ingest.py
drive-index`, which carries no judgment.** It runs steps 1 and 2 of the sync
procedure with the one further sync, and prints one JSON line.

| `state` | Means | Do |
| --- | --- | --- |
| `indexed` | the stores agree; `questions` names each unreadable note, and asks the user to reconnect `vault-rag` if the sync added or changed vectors | carry `questions` into the batch's one report |
| `rebuild` | the configured `embedding_model` differs from the recorded one | run `sync --rebuild` as its own step, then `drive-index` once more; a second `rebuild` stops the batch |
| `halt` | the embedding model or the tokenizer is unavailable, or the stores still disagree after the further sync | stop the batch with the line's `question` |
