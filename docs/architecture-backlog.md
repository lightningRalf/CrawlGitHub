# Architecture Backlog — CrawlGitHub

## Scoring rubric

- Importance (I): 1 low → 5 critical
- Urgency (U): 1 low → 5 immediate
- Difficulty (D): 1 easy → 5 hard
- Quadrant rules:
  - Q1 Do now: high I/high U
  - Q2 Plan: high I/low U
  - Q3 Delegate/Automate: low I/high U
  - Q4 Defer: low I/low U

## Scored backlog

| # | Task | I | U | D | Quadrant |
|---|---|---:|---:|---:|---|
| 1 | Add explicit watch candidate/frontmatter contract tests and field invariants | 5 | 5 | 2 | Q1 |
| 2 | Add local-only integration tests for classify→sync→prune workflow | 5 | 4 | 3 | Q1 |
| 3 | Split watch pipeline into focused modules (`watch/signals.py`, `watch/io.py`, `watch/npm.py`, `watch/candidates.py`, `watch/export.py`, `watch/sync.py`) | 5 | 4 | 4 | Q1 |
| 4 | Persist watch sync/export summary as JSON artifact (machine-readable telemetry) | 4 | 3 | 2 | Q2 |
| 5 | Introduce typed candidate models (dataclass/pydantic) with schema versioning | 5 | 3 | 4 | Q2 |
| 6 | Introduce incremental CLI subcommands (`watch sync`, `watch export`) | 4 | 3 | 4 | Q2 |
| 7 | Build labeled heuristic benchmark set (precision/recall tracking) | 4 | 2 | 3 | Q2 |
| 8 | Add migration helper for watch explainability fields in old notes | 3 | 2 | 3 | Q4 |
| 9 | Add performance profiling for candidate collection over large vaults | 3 | 2 | 2 | Q4 |
|10 | Automate local-only nightly watch sync job script | 2 | 4 | 2 | Q3 |

## HTN (Q1 + Q2)

### G0 — Stabilize and scale watchlist architecture with conservative API usage

#### T1 (Q1) — Enforce watch data contracts
- **Dependencies:** none
- **Leaf actions:**
  1. Add contract tests file: `tests/test_watchlist_contracts.py`.
  2. Assert required export fields: `signalReasons`, `signalSources`, `signalCount`, `confidence`.
  3. Assert confidence enum is one of `low|medium|high`.
- **Validation:**
  - `uv run python -m pytest -q tests/test_watchlist_contracts.py`

#### T2 (Q1) — Add integration tests for local-only workflow
- **Dependencies:** T1
- **Leaf actions:**
  1. Add file: `tests/test_watchlist_local_e2e.py`.
  2. Use temp vault fixture notes to test sync + prune idempotency.
  3. Verify generated frontmatter + watch base content expectations.
- **Validation:**
  - `uv run python -m pytest -q tests/test_watchlist_local_e2e.py tests/test_watchlist_sync.py`

#### T3 (Q1) — Decompose watchlist module safely
- **Dependencies:** T1, T2
- **Leaf actions:**
  1. Create package dir: `src/crawl_github_starred/watch/`.
  2. Extract classifier/scoring helpers to `watch/signals.py`.
  3. Extract frontmatter/file helpers to `watch/io.py`.
  4. Extract npm package parsing/enrichment to `watch/npm.py`.
  5. Extract typed candidate build/merge/collection to `watch/candidates.py`.
  6. Keep `watch/export.py` as thin export orchestration and `watch/sync.py` as sync/prune orchestration.
  7. Remove compatibility shim after migrations.
- **Validation:**
  - `uv run python -m compileall src tools tests`
  - `uv run python -m pytest -q`

#### T4 (Q2) — Persist telemetry artifacts
- **Dependencies:** T1
- **Leaf actions:**
  1. Add config/env for telemetry output path in `src/crawl_github_starred/config.py`.
  2. Write run summary JSON from watch sync/export.
  3. Document path/fields in `docs/exports/watch-seeds-schema.md`.
- **Validation:**
  - `uv run python -m pytest -q tests/test_watchlist_sync.py tests/test_watchlist_heuristics.py`

#### T5 (Q2) — Introduce typed candidate models
- **Dependencies:** T1, T3
- **Leaf actions:**
  1. Add models module: `src/crawl_github_starred/watch/models.py`.
  2. Replace untyped dict plumbing incrementally in sync/export boundaries.
  3. Keep serialization parity for existing JSONL/frontmatter fields.
- **Validation:**
  - `uv run python -m pytest -q`

#### T6 (Q2) — CLI subcommand evolution
- **Dependencies:** T3
- **Leaf actions:**
  1. Add argparse subparsers in `src/crawl_github_starred/main.py`.
  2. Require explicit subcommands (no flag-only compatibility path).
  3. Update README command examples.
- **Validation:**
  - `uv run python -m pytest -q`

#### T7 (Q2) — Heuristic benchmark corpus
- **Dependencies:** T1
- **Leaf actions:**
  1. Add fixtures under `tests/fixtures/watch_benchmark/`.
  2. Add evaluation test/report command for precision/recall trend.
  3. Document benchmark workflow in docs.
- **Validation:**
  - `uv run python -m pytest -q tests/test_watchlist_heuristics.py`

## Execution status update

- ✅ T1 contract checks implemented (`tests/test_watchlist_contracts.py`).
- ✅ T2 local-only integration baseline implemented (`tests/test_watchlist_local_e2e.py`).
- ✅ T3 module split completed:
  - created `src/crawl_github_starred/watch/`
  - extracted signal/classifier/scoring helpers to `src/crawl_github_starred/watch/signals.py`
  - extracted frontmatter/file helpers to `src/crawl_github_starred/watch/io.py`
  - extracted npm package parsing/enrichment to `src/crawl_github_starred/watch/npm.py`
  - extracted typed candidate build/merge/collection to `src/crawl_github_starred/watch/candidates.py`
  - reduced `src/crawl_github_starred/watch/export.py` to thin export orchestration
  - kept `src/crawl_github_starred/watch/sync.py` as sync/prune orchestration
  - removed legacy `watchlist_exports.py` compatibility shim
- ✅ T4 telemetry artifact output implemented:
  - config/env: `CRAWLGITHUB_WATCH_TELEMETRY_FILE`
  - writes JSON summaries for watch sync/export runs
  - covered by `tests/test_main_watch_telemetry.py`
- 🚧 T5 typed model migration progressed:
  - added `src/crawl_github_starred/watch/models.py` (`WatchCandidate` + coercion helpers)
  - shifted candidate creation + merge + collection internals to typed-first handling with dict compatibility at boundaries
  - moved signal/metadata normalization toward typed helpers (`candidate_reason_fragments`, `refresh_watch_candidate_signal_metadata`)
  - sync note-writing internals now consume typed signal/metadata helpers instead of dict-first helper calls
  - wired typed coercion into npm metadata enrichment mutation paths
  - sync now accepts typed `WatchCandidate` collections from boundaries
  - added parity-focused tests in `tests/test_watch_models.py` and typed sync/merge/enrichment/collection-path checks in `tests/test_watchlist_sync.py` + `tests/test_watchlist_heuristics.py` + `tests/test_watchlist_contracts.py`
- ✅ T6 explicit CLI subcommands finalized:
  - explicit argparse subparsers: `crawl`, `watch sync`, `watch export`
  - removed legacy flag-only invocation/default-to-crawl behavior
  - updated CLI tests/docs to enforce explicit command usage

## Current next actions

1. Continue T5 by migrating remaining dict-heavy helper callsites in watch pipelines to typed helper usage while preserving JSONL/frontmatter parity.
2. Keep schema/contract drift checks green (`signal*`, `watch_signal_*`, lifecycle timestamps).
