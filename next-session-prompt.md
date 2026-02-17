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
- Watch module decomposition has started:
  - new package `src/crawl_github_starred/watch/`
  - signal/classifier/scoring helpers extracted to `watch/signals.py`
  - `watchlist_exports.py` keeps compatibility imports.
- Optional watch telemetry JSON artifact is available via `CRAWLGITHUB_WATCH_TELEMETRY_FILE`.

## Current priorities (architecture)

1. **Contract-first watch schema hardening**
   - Keep candidate + frontmatter contracts explicit and tested.
   - Guard field drift for `signal*`, `watch_signal_*`, lifecycle timestamps.

2. **Module decomposition of watchlist pipeline (in progress)**
   - Continue split of `watchlist_exports.py` into smaller units (next: sync/prune -> `watch/sync.py`).
   - Preserve behavior; no API expansion.

3. **Typed candidate models (next architecture step)**
   - Introduce typed watch candidate models and migrate dict plumbing incrementally.
   - Preserve JSONL/frontmatter field parity during migration.

4. **CLI subcommand shape (incremental)**
   - Move toward `crawl`, `watch sync`, `watch export` without breaking current flags.

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
# Local-only watch sync + prune
uv run crawl-github --export-seeds-only --sync-watch-candidates --prune-watch-candidates --max-npm-lookups 0

# Full test gate
uv run python -m pytest -q
```

## Definition of done for next session

- Working tree clean.
- Full test gate green.
- At least one architecture objective completed:
  - watch sync/prune extraction completed with behavior parity tests, OR
  - typed candidate model scaffolding introduced with parity tests.
