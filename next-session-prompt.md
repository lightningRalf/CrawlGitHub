# Next Session Prompt — CrawlGitHub (Updated)

Continue improving `C:\Users\mjpa\ProgrammierProjekte\CrawlGitHub` for Obsidian searchability and low-maintenance curation.

## Context (already implemented)

### Repo note + README architecture

- Local README snapshot architecture is in place (`repo_info.py`) with stable hashed filenames under `23.03_READMEs/`.
- Structured frontmatter updates exist for repo notes (`source`, `repo`, `owner`, `review_status`, `why_starred`, `next_action`, metrics, README fields).
- `.base` file generation exists (`bases_files.py`):
  - `23.03.00_RepoIndex.base`
  - `23.03.00_ReviewQueue.base`
- `23.03.01_CrawlGitHubURLs.md` writer dedupes no-longer-maintained entries (`starred_repos_file.py`).

### Migration + cleanup status

- No-API migration script exists (`tools/migrate_repo_notes.py`) and was run in full batches.
- Reports exist for:
  - `docs/migration/batch-01.json` (already done before)
  - `docs/migration/batch-02.json` … `docs/migration/batch-11.json`
  - `docs/migration/catchup.json`
  - `docs/migration/starred-file-dedupe-02.json`
  - `docs/migration/duplicate-note-cleanup.json`
- Duplicate repo-note cleanup completed (5 duplicate files removed after merging overview history into canonical notes).

Current vault integrity (post-cleanup):
- repo notes: `1563`
- README snapshot files: `1563`
- notes with `readme_note`: `1563`
- notes with local README link: `1563`
- missing README targets: `0`
- duplicate `repo_url` groups: `0`

### Watchlist seed workstream (implemented)

- New export module: `src/crawl_github_starred/watchlist_exports.py`
- New crawler CLI options:
  - `--export-watch-seeds`
  - `--export-npm-seeds`
  - `--max-npm-lookups`
  - `--export-seeds-only` (local-only export, no GitHub API crawl)
- Schema docs added: `docs/exports/watch-seeds-schema.md`
- Seed snapshots generated:
  - `docs/exports/extensions-watch-seeds.github.jsonl`
  - `docs/exports/extensions-watch-seeds.npm.jsonl`

### Testing direction

- Test strategy is being shifted to `pytest`-style assertions.
- Current working tree may contain uncommitted updates for:
  - `tests/test_logging.py`
  - `tests/test_stamina_logging.py`
  - `pyproject.toml`
  - `uv.lock`
  - `README.md` (testing command update)

## Important constraints

- Do **not** hammer GitHub API.
- Keep README sync conservative (default `new`, bounded by `--max-readme-updates`).
- Prefer local-first workflows where possible:
  - use `--export-seeds-only` for watchlist exports when crawl refresh is unnecessary.
- For large note cleanup, continue to use `tools/migrate_repo_notes.py` (no API).

## First checks

1. `git status`
2. `uv run python -m compileall src tools`
3. `uv run python -m pytest -q`
4. Optional local-only watch export refresh:
   - `uv run crawl-github --export-seeds-only --export-watch-seeds docs/exports/extensions-watch-seeds.github.jsonl --export-npm-seeds docs/exports/extensions-watch-seeds.npm.jsonl --max-npm-lookups 0`

## Next improvements to implement (priority)

1. **Finalize pytest migration and commit hygiene**
   - Ensure tests are deterministic and assertion-based.
   - Remove script-style testing remnants from docs/tooling.

2. **Frontmatter safety hardening**
   - Prevent accidental overwrite of user-authored fields.
   - Add `schema_version` for migration tracking.

3. **README sync quality improvements**
   - Track and use README cache validators (ETag/Last-Modified) where useful.
   - Add smarter sync policy:
     - `if-pushed`
     - stale fallback days.

4. **Watchlist export quality refinement**
   - Expand candidate recall while keeping false positives low.
   - Add unit tests for tag classification and candidate normalization.
   - Keep npm lookup optional + bounded.

5. **Core unit test backlog (still relevant)**
   - table row dedupe
   - frontmatter render order
   - starred file dedupe behavior

## Commands (examples)

```sh
# Safe crawl (API-aware)
uv run crawl-github --skip-existing --max-repos 50 --readme-sync-mode new --max-readme-updates 10

# Local-only watchlist seed export (no GitHub crawl)
uv run crawl-github --export-seeds-only --export-watch-seeds docs/exports/extensions-watch-seeds.github.jsonl --export-npm-seeds docs/exports/extensions-watch-seeds.npm.jsonl --max-npm-lookups 0

# Optional bounded npm enrichment
uv run crawl-github --export-seeds-only --export-watch-seeds docs/exports/extensions-watch-seeds.github.jsonl --export-npm-seeds docs/exports/extensions-watch-seeds.npm.jsonl --max-npm-lookups 10

# Tests
uv run python -m pytest -q
```

## Definition of done for next session

### Core DoD

- Working tree clean (including test migration files).
- `uv run python -m compileall src tools` passes.
- `uv run python -m pytest -q` passes.
- No duplicate repo notes reintroduced.
- README link integrity remains intact.

### Feature DoD (pick at least one)

- Frontmatter safety enhancement implemented and documented.
- README sync policy improved (`if-pushed` + stale fallback concept).
- Watch export heuristic/test quality improved with added unit tests.
