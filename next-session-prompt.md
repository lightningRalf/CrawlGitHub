# Next Session Prompt — CrawlGitHub (Architecture Wave)

Continue improving `C:\Users\mjpa\ProgrammierProjekte\CrawlGitHub` for Obsidian-native curation (Bases-first) with conservative API usage.

## Current baseline (implemented)

- README snapshot sync is conservative and bounded (`off|new|if-pushed|always`, stale fallback/jitter, ETag/Last-Modified, retry cooldowns, summary logging).
- Repo notes use structured frontmatter (`schema_version: 2`) and preserve manual triage fields.
- Bases are generated for repo index/review queue/watch candidates.
- Watch candidate workflow is Obsidian-first:
  - `--sync-watch-candidates`
  - lifecycle archiving via `--prune-watch-candidates` (`watch_status: archived`)
  - reactivation handling and lifecycle timestamps.
- Watch heuristics improved:
  - boundary-aware matching,
  - frontmatter-weighted phrase signals,
  - conservative repo anchors,
  - explainability metadata (`signalReasons`, `signalSources`, `signalCount`, `confidence`).
- Tests now include watch lifecycle, heuristics, contract checks, and local-only end-to-end sync/prune/base workflow.
- Watch module decomposition advanced to focused modules:
  - `src/crawl_github_starred/watch/signals.py` for classifier/scoring helpers
  - `src/crawl_github_starred/watch/io.py` for frontmatter/file helpers
  - `src/crawl_github_starred/watch/npm.py` for npm parsing + enrichment
  - `src/crawl_github_starred/watch/candidates.py` for typed candidate build/merge/collection
  - `src/crawl_github_starred/watch/export.py` as thin local seed export orchestration
  - `src/crawl_github_starred/watch/sync.py` for note sync/prune pipeline
  - legacy `watchlist_exports.py` compatibility shim removed.
- Typed candidate model migration advanced:
  - `src/crawl_github_starred/watch/models.py` now provides typed signal/confidence/count helpers
  - merge and stats callsites in sync/export flows now operate typed-first
  - JSONL/frontmatter parity preserved at boundaries via `to_dict` coercion
  - parity-focused tests extended in `tests/test_watch_models.py`, `tests/test_watchlist_heuristics.py`, `tests/test_watchlist_sync.py`, and `tests/test_watchlist_contracts.py`.
- Incremental CLI subcommand shape introduced (compatibility-safe):
  - explicit subparsers: `crawl`, `watch sync`, `watch export`
  - legacy flag-only invocation remains supported by defaulting to `crawl`.
- Optional watch telemetry JSON artifact is available via `CRAWLGITHUB_WATCH_TELEMETRY_FILE`.
- Current test gate: `66 passed`.

## Current priorities (architecture)

1. **Contract-first watch schema hardening**
   - Keep candidate + frontmatter contracts explicit and tested.
   - Guard field drift for `signal*`, `watch_signal_*`, lifecycle timestamps.

2. **Typed candidate models (migration phase)**
   - Continue migrating remaining dict-heavy watch pipeline helper callsites to typed helper usage.
   - Preserve JSONL/frontmatter field parity during migration.

3. **CLI subcommand shape (incremental)**
   - Refine subparser UX/help and keep command behavior explicit.
   - Preserve legacy flags and behavior compatibility.

4. **Post-shim cleanup + API clarity**
   - Keep `watch/io.py`, `watch/npm.py`, `watch/candidates.py`, `watch/export.py`, and `watch/sync.py` boundaries explicit.
   - Remove lingering transitional naming (`*_model`) where safe, without behavior expansion.

## Constraints

- Do **not** hammer GitHub API.
- Keep README sync conservative and bounded (`--max-readme-updates`).
- Prefer local-first workflows:
  - `--export-seeds-only`
  - `--max-npm-lookups 0` unless explicitly needed.

## First checks

1. `git status`
2. `uv run python -m compileall src tools tests`
3. `uv run python -m pytest -q`

## Suggested next commands

```sh
# Local-only watch sync + prune (subcommand form)
uv run crawl-github watch sync --prune-watch-candidates --max-npm-lookups 0

# Backward-compatible legacy form
uv run crawl-github --export-seeds-only --sync-watch-candidates --prune-watch-candidates --max-npm-lookups 0

# Full test gate
uv run python -m pytest -q
```

## Definition of done for next session

- Working tree clean.
- Full test gate green.
- At least one architecture objective completed:
  - typed model migration further expanded by converting at least one remaining watch pipeline callsite to typed helper usage + parity tests, OR
  - subparser UX/help refinements completed with legacy-flag compatibility preserved.
