# Next Session Prompt — CrawlGitHub (Updated Again)

Continue improving `C:\Users\mjpa\ProgrammierProjekte\CrawlGitHub` for Obsidian-native curation (Bases-first) with conservative API usage.

## Context (already implemented)

### Repo notes + README architecture

- Local README snapshot architecture is in place (`repo_info.py`) with stable hashed filenames under `23.03_READMEs/`.
- Repo frontmatter is structured and migration-aware:
  - includes `schema_version` (current target: `2`)
  - preserves user-authored triage fields (`review_status`, `why_starred`, `next_action`)
- `.base` file generation exists (`bases_files.py`):
  - `23.03.00_RepoIndex.base`
  - `23.03.00_ReviewQueue.base`
- `23.03.01_CrawlGitHubURLs.md` writer dedupes no-longer-maintained entries (`starred_repos_file.py`).

### README sync quality hardening (implemented)

- Modes: `off | new | if-pushed | always`
- Stale fallback support (for `if-pushed`):
  - env: `CRAWLGITHUB_README_SYNC_STALE_DAYS`
  - CLI: `--readme-stale-days`
- Deterministic stale jitter spreading:
  - env: `CRAWLGITHUB_README_STALE_JITTER_DAYS`
  - CLI: `--readme-stale-jitter-days`
- Conditional README validation via ETag / Last-Modified:
  - tracks `readme_etag`, `readme_last_modified`
  - handles `304` without rewriting snapshot content
- Retry-loop prevention for failed README states:
  - tracks `readme_last_attempt_at`, `readme_last_status`
  - cooldowns for `not_found`, `forbidden`, `error`
- End-of-run README sync summary logging:
  - due/attempted/skipped counters
  - status/reason counts
  - stale-window distribution summary

### Watchlist/Bases workflow (implemented)

- Export module exists: `src/crawl_github_starred/watchlist_exports.py`
- JSONL exports still supported:
  - `--export-watch-seeds`
  - `--export-npm-seeds`
  - `--max-npm-lookups`
  - `--export-seeds-only`
- **Obsidian-native sync now exists**:
  - `--sync-watch-candidates`
  - repo candidates are written into existing repo note frontmatter
  - npm candidates are written as notes under `CRAWLGITHUB_WATCH_CANDIDATES_SUBDIR` (default `23.03_WatchCandidates`)
- New watch candidates Base:
  - `23.03.00_WatchCandidates.base`
  - generator: `bases_files.write_watch_candidates_base()`
- Schema docs updated: `docs/exports/watch-seeds-schema.md`

### Migration + cleanup status

- No-API migration script exists (`tools/migrate_repo_notes.py`) and includes schema/frontmatter ordering updates.
- Previous migration/cleanup reports remain in `docs/migration/*`.

### Test status

- Pytest-style suite now includes:
  - `tests/test_repo_info_core.py`
  - `tests/test_starred_repos_file.py`
  - `tests/test_github_api_readme_fetch.py`
  - `tests/test_watchlist_sync.py`
  - plus existing logging/stamina tests
- Latest run: `16 passed`.

## Current working tree (likely uncommitted)

From `git status --short`:

- Modified:
  - `README.md`
  - `docs/exports/watch-seeds-schema.md`
  - `src/crawl_github_starred/bases_files.py`
  - `src/crawl_github_starred/config.py`
  - `src/crawl_github_starred/github_api.py`
  - `src/crawl_github_starred/main.py`
  - `src/crawl_github_starred/repo_info.py`
  - `src/crawl_github_starred/watchlist_exports.py`
  - `tools/migrate_repo_notes.py`
- Untracked:
  - `tests/conftest.py`
  - `tests/test_github_api_readme_fetch.py`
  - `tests/test_repo_info_core.py`
  - `tests/test_starred_repos_file.py`
  - `tests/test_watchlist_sync.py`

## Important constraints

- Do **not** hammer GitHub API.
- Keep README sync conservative and bounded (`--max-readme-updates`).
- Prefer local-first workflows:
  - `--export-seeds-only`
  - `--max-npm-lookups 0` unless explicitly needed
- Keep watch candidate flow **Obsidian-first** (Bases), JSONL export optional.
- For large note migration/cleanup, use `tools/migrate_repo_notes.py` (no API).

## First checks

1. `git status`
2. `uv run python -m compileall src tools tests`
3. `uv run python -m pytest -q`
4. Optional local-only watch sync verification:
   - `uv run crawl-github --export-seeds-only --sync-watch-candidates --max-npm-lookups 0`

## Next improvements to implement (priority)

1. **Commit hygiene / clean checkpoint**
   - Split and commit current work in coherent chunks.
   - Ensure working tree is clean before next feature wave.

2. **Watch candidate lifecycle management (important next feature)**
   - Add prune/archive behavior for candidates that are no longer detected.
   - Suggested flag: `--prune-watch-candidates`.
   - Keep history-friendly semantics (`watch_status: archived`) instead of destructive deletes.

3. **Watch heuristic quality refinement**
   - Reduce false positives while preserving recall.
   - Expand focused unit tests for classifier + normalization + merge behavior.

4. **Bases UX refinement for watch triage**
   - Tune `WatchCandidates.base` views/filters/orders for daily triage flow.

## Commands (examples)

```sh
# Safe crawl (API-aware + conservative README sync)
uv run crawl-github --skip-existing --max-repos 50 --readme-sync-mode if-pushed --readme-stale-days 30 --readme-stale-jitter-days 7 --max-readme-updates 10

# Local-only watch candidate sync into Obsidian notes + base workflow
uv run crawl-github --export-seeds-only --sync-watch-candidates --max-npm-lookups 0

# Optional JSONL export (still supported)
uv run crawl-github --export-seeds-only --export-watch-seeds docs/exports/extensions-watch-seeds.github.jsonl --export-npm-seeds docs/exports/extensions-watch-seeds.npm.jsonl --max-npm-lookups 0

# Tests
uv run python -m pytest -q
```

## Definition of done for next session

### Core DoD

- Working tree clean.
- `uv run python -m compileall src tools tests` passes.
- `uv run python -m pytest -q` passes.
- No duplicate repo notes reintroduced.
- README snapshot/link integrity remains intact.

### Feature DoD (pick at least one)

- Watch candidate prune/archive lifecycle implemented (`--prune-watch-candidates`) and documented.
- Watch heuristic quality improved with added targeted tests.
- WatchCandidates Base tuned for smoother triage workflow.
