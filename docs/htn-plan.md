# HTN Plan — CrawlGitHub Searchability Overhaul

Goal: make the generated vault notes searchable for Obsidian + LLM retrieval, while minimizing GitHub API load.

## Status (current)

- ✅ WP1 implemented in crawler (`repo_info.py`) + conservative README sync controls.
- ✅ WP2 implemented frontmatter schema + defaults (`repo_info.py`).
- ✅ WP3 implemented `.base` repo index generation (`bases_files.py`).
- ✅ WP4 implemented `.base` review queue generation (`bases_files.py`).
- ✅ WP5 implemented migration + dedupe tooling (`tools/migrate_repo_notes.py`), batch 01 already applied.
- ✅ WP6 created `next-session-prompt.md`.

## Decomposition

### WP1 — README local snapshots (hashed + linked)
- Add local README snapshot files under `23.03_READMEs/`.
- Stable filename with repo hash (repo identity hash, not content hash).
- Store `readme_sha256` in frontmatter.
- Add wiki-link in repo note body and backlink in README note.
- Refresh policy: default conservative to avoid API spikes.

### WP2 — Structured frontmatter schema
- Add consistent properties for Bases + search:
  - `source`, `repo`, `repo_url`, `owner`, `repo_name`, `description`
  - `stars`, `watchers`, `forks`, `contributors`, `last_release`
  - `last_pushed_at`, `maintained`
  - `review_status`, `why_starred`, `next_action`
  - `readme_note`, `readme_sha256`
- Preserve existing manual properties.

### WP3 — Obsidian Bases index (instead of markdown index table)
- Generate `23.03.00_RepoIndex.base`.
- Table-first layout for browsing/sorting/filtering.

### WP4 — Obsidian Bases review queue
- Generate `23.03.00_ReviewQueue.base`.
- Focus filter: items with missing `why_starred` or `review_status: inbox`.

### WP5 — Dedup + migration + batching (no API)
- Dedupe duplicate overview rows in repo notes.
- Dedupe duplicate entries/headings in `23.03.01_CrawlGitHubURLs.md`.
- Add migration script with work-package flags:
  - `--start-number`
  - `--limit`
  - `--dry-run`
- No API calls in migration.

### WP6 — Next session prompt
- Create `next-session-prompt.md` with:
  - implemented changes
  - remaining migration batches
  - API-safe run strategy
  - next improvements

## Batching strategy for frontmatter migration

Estimated repo note files: ~1560.

Use batches of 150 files to reduce risk:
- Batch 01: `--start-number 1 --limit 150`
- Batch 02: `--start-number 151 --limit 150`
- ...
- Batch 11: `--start-number 1501 --limit 150`

Validation after each batch:
- count changed files
- spot-check 3 files
- verify no markdown table corruption
- keep API calls at zero for migration run
