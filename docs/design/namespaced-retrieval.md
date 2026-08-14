# Design: Namespaced retrieval (candidates only)

- **Status:** Accepted (planner freeze)
- **Date:** 2026-08-14
- **Design issue:** [#72](https://github.com/lbliii/orrery/issues/72)
- **Parent epic:** [#61](https://github.com/lbliii/orrery/issues/61)
- **Parent saga:** [#56](https://github.com/lbliii/orrery/issues/56) (closed),
  [#1](https://github.com/lbliii/orrery/issues/1)
- **Binds:** [ADR 0005](../adr/0005-discovery-and-dual-trust.md) §2

## Question frozen

How does optional retrieval attach to gaze so a large **namespace** can
recover missed blurbs, without Orrery becoming an embedding winner-picker
or a chat-with-docs product?

## Decision

Retrieval is **insurance for gaze recall inside one node**. It returns
candidate **names** only. The agent still picks. `resolve_name` stays exact.

This is not document RAG, not public-web search, and not a new MCP tool.

### Rejected options

1. **Global embedding router** — rejected. ADR 0005 Not now (DORI failure
   mode). No API may return a single forced skill.
2. **Hosted vector DB / embedding vendor in v1** — rejected. Public sky
   already scores every row in the node (`score_record`). A new engine
   would not earn its keep until a tenant corpus fails recall@k.
3. **Always-on second ranker** — rejected. Default path stays today's
   lexical `gaze_match` / `gaze_search`.

### Flag

`ORRERY_GAZE_RETRIEVAL` — unset or `0` is off (MVP / production default).
`1` enables the retriever merge on `gaze_match` only. `gaze_search`
stays substring. No `app.py` read; catalog reads the env.

Flag off must keep today's shortlist **name set** for the public intent
fixtures (bit-identical names in the capped window, order may follow
existing `score_record` ties).

### Scope

- Pool is `records_for_gaze_node(node)` only. No cross-namespace admit.
- Index text: summary, `use_when`, `example_intents`, coarse facets
  (`kind`, `price_band`, `reactive`, `oracle_ok`). Same disclosure
  surface as gaze hits.
- Never index tool schemas, live payloads, listing bytes, or wallet
  rows.

### Protocol

```python
class GazeRetriever(Protocol):
    def retrieve(
        self, intent: str, records: tuple[ResolveRecord, ...]
    ) -> tuple[str, ...]:
        """Candidate names only. Empty is fine. Never a winner API."""
```

`catalog.store.Catalog.match` when the flag is on:

1. Default lexical pool (today's `score_record` > 0).
2. `retrieve()` names intersected with the same node records.
3. Union, re-rank with `score_record`, apply `clamp_gaze_limit`.

No new gaze tool. No `winner` / `best` / `route` field on `GazeHit`.
A one-hit shortlist is allowed only when the union truly has one
in-scope name — the API shape stays a list.

### v1 adapter

In-process lexical retriever in `catalog/retrieval.py`. No new
dependency. It may re-admit in-node names the first pass dropped
(score 0) only when a `use_when` / `example_intents` line shares a
token with the intent after the same `_tokens` rules. That is the
whole v1 “insurance.” It will often be a no-op on the public sky.

Injected retrievers in tests prove: extra in-node name can appear;
cross-node name cannot; flag off ignores the retriever.

### Follow-on (not v1)

An embedding adapter may implement the same `GazeRetriever` later.
Do not pick a model, vendor, or dimension in this freeze. File that
leaf `blocked` until a real namespace corpus fails recall@k with v1
on.

### Eval

`tests/gaze-intents.v1.json` remains the public regression (shortlist
contains, never top-1 mandate).

Add `tests/gaze-retrieval.v1.json` plus a recall@k helper:

- Flag off: record baseline recall@3 on that file.
- Flag on + v1 adapter: recall@3 ≥ baseline.
- A short note in this doc or the issue: public-sky baseline and
  whether v1 moved anything (honest zero is acceptable).

### Eval numbers (2026-08-14, #467)

Public + `acme` suite in `tests/gaze-retrieval.v1.json` (17 queries,
macro recall@3, relevant-set overlap, no top-1 mandate):

| Mode | recall@3 |
| --- | --- |
| Flag off (lexical `score_record` only) | 1.00 |
| Flag on + v1 `LexicalGazeRetriever` | 1.00 |

v1 did not move public-sky recall. That is acceptable: the current
catalog already scores every in-node row. The harness is the product
of this leaf.

### What leaves may assume

- No new ADR. Cite ADR 0005 + this note.
- No `app.py`, `discovery.py`, or new MCP tool.
- `catalog/store.py` `match()` only for the merge; `search()` untouched.
- Workers do not add embeddings, a winner field, or a second catalog.

## Non-goals

- Chat / memory / “ask the sky”
- Cross-namespace or public crawl retrieval
- Changing `resolve_name`
- Paid rank from retrieval score
- Default-on in production
