# Crawl GitHub Starred Repositories

Fetches starred repositories for a configured GitHub user (defaults to `lightningralf`), collects metadata, and updates Obsidian notes in `23.03_Code`.

## Features

- Repository discovery for starred repos
- Metadata collection (stars, watchers, forks, contributors, latest release)
- Per-repo Markdown notes with historical overview table
- **Local README snapshot notes** in `23.03_READMEs/` (stable hashed filenames)
- README sync supports conditional checks via ETag/Last-Modified and cooldown-aware retries for missing/forbidden/error states
- End-of-run README sync metric summary (due/attempted/skipped/status/reason counts + stale-window distribution)
- Structured frontmatter (`schema_version: 2`) for search/Bases/LLM retrieval
- Manual triage fields (`review_status`, `why_starred`, `next_action`) are preserved across sync runs
- Auto-generated Obsidian Bases files:
  - `23.03.00_RepoIndex.base`
  - `23.03.00_ReviewQueue.base`
  - `23.03.00_WatchCandidates.base` (when syncing watch candidates)
- Watchlist seed exports for pi extension scouting:
  - GitHub candidates JSONL
  - npm candidates JSONL (optional bounded npm enrichment)
- Watch candidate lifecycle sync can archive stale candidates (`watch_status: archived`) with `--prune-watch-candidates` and tracks reactivation/archive timestamps
- Watch heuristics use boundary-aware marker matching, frontmatter-weighted phrase signals, and conservative repo anchors to reduce false positives
- Synced watch notes include explainability fields (`watch_signal_sources`, `watch_signal_count`, `watch_confidence`) for clearer Bases triage
- Deduplicated `23.03.01_CrawlGitHubURLs.md` maintenance section
- Cached API responses (ETag/Last-Modified) in `tools/cache`
- Retry logic with `stamina`
- Console + file logging (`github_fetch.log`)

## Prerequisites

- Python 3.11+
- uv (https://github.com/astral-sh/uv)
- GitHub Personal Access Token (`GITHUB_PAT`)

## Installation

```sh
uv sync
```

## Configuration

Set your token:

```powershell
$env:GITHUB_PAT = "your_github_personal_access_token"
```

Optional environment variables:

- `CRAWLGITHUB_WORKING_DIR` (default: Obsidian `23.03_Code` path)
- `CRAWLGITHUB_CACHE_DIR`
- `CRAWLGITHUB_REQUEST_DELAY_SECONDS` (default: `1.0`)
- `CRAWLGITHUB_README_SYNC_MODE` (`off|new|if-pushed|always`, default: `new`)
- `CRAWLGITHUB_README_SYNC_STALE_DAYS` (default: `30`, used as fallback with `if-pushed`; `0` disables stale fallback)
- `CRAWLGITHUB_README_STALE_JITTER_DAYS` (default: `7`, adds deterministic per-repo stale jitter via `hash(repo) % N`; `0` disables jitter)
- `CRAWLGITHUB_MAX_README_UPDATES_PER_RUN` (default: `25`)
- `CRAWLGITHUB_README_NOTES_SUBDIR` (default: `23.03_READMEs`)
- `CRAWLGITHUB_WATCH_CANDIDATES_SUBDIR` (default: `23.03_WatchCandidates`)
- `CRAWLGITHUB_WATCH_CANDIDATES_BASE_FILE` (default: `23.03.00_WatchCandidates.base`)

## Usage

Run crawler:

```sh
uv run crawl-github
```

PowerShell wrapper:

```powershell
.\run_crawl_github.ps1
```

### CLI flags

- `--skip-existing`
- `--resume-from 1450`
- `--max-repos 25`
- `--readme-sync-mode new`
- `--readme-stale-days 30`
- `--readme-stale-jitter-days 7`
- `--max-readme-updates 20`
- `--skip-bases`
- `--sync-watch-candidates`
- `--prune-watch-candidates`
- `--export-watch-seeds docs/exports/extensions-watch-seeds.github.jsonl`
- `--export-npm-seeds docs/exports/extensions-watch-seeds.npm.jsonl`
- `--max-npm-lookups 10`
- `--export-seeds-only`

Example (safe incremental run):

```sh
uv run crawl-github --skip-existing --max-repos 50 --readme-sync-mode if-pushed --readme-stale-days 30 --readme-stale-jitter-days 7 --max-readme-updates 10
```

Example (sync watch candidates directly into Obsidian notes + WatchCandidates base, local-only):

```sh
uv run crawl-github --export-seeds-only --sync-watch-candidates --max-npm-lookups 0
```

Example (sync + archive candidates no longer detected):

```sh
uv run crawl-github --export-seeds-only --sync-watch-candidates --prune-watch-candidates --max-npm-lookups 0
```

Example (export watchlist seeds from local notes, no npm API enrichment):

```sh
uv run crawl-github --export-seeds-only --export-watch-seeds docs/exports/extensions-watch-seeds.github.jsonl --export-npm-seeds docs/exports/extensions-watch-seeds.npm.jsonl --max-npm-lookups 0
```

Schema and tagging notes: `docs/exports/watch-seeds-schema.md`

## Batch migration (no API)

Use this to migrate existing note files in work packages (frontmatter + dedupe):

```sh
uv run python tools/migrate_repo_notes.py --start-number 1 --limit 150 --dry-run
uv run python tools/migrate_repo_notes.py --start-number 1 --limit 150 --create-readme-placeholders
```

Optional report output:

```sh
uv run python tools/migrate_repo_notes.py --start-number 151 --limit 150 --report docs/migration/batch-02.json
```

Also dedupe `23.03.01_CrawlGitHubURLs.md`:

```sh
uv run python tools/migrate_repo_notes.py --start-number 1 --limit 150 --dedupe-starred-file
```

PowerShell batch helper:

```powershell
.\tools\run_migration_batch.ps1 -Batch 1 -DryRun
.\tools\run_migration_batch.ps1 -Batch 1 -CreateReadmePlaceholders -DedupeStarredFile
```

## Testing

```sh
uv run python -m pytest -q
```

## Project Structure

```
CrawlGitHub/
src/
  crawl_github_starred/
    __init__.py
    bases_files.py
    cache.py
    config.py
    github_api.py
    main.py
    repo_info.py
    starred_repos_file.py
    watchlist_exports.py
tools/
  migrate_repo_notes.py
tests/
  conftest.py
  test_github_api_readme_fetch.py
  test_logging.py
  test_repo_info_core.py
  test_stamina_logging.py
  test_starred_repos_file.py
  test_watchlist_sync.py
README.md
```
