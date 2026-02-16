# Next Session Prompt — CrawlGitHub

Continue improving `C:\Users\mjpa\ProgrammierProjekte\CrawlGitHub` for Obsidian searchability and low-maintenance curation.

## Context (already implemented)

- Added local README snapshot architecture in crawler (`repo_info.py`) with stable hashed filenames under `23.03_READMEs/`.
- Added structured frontmatter updates for repo notes (`source`, `repo`, `owner`, `review_status`, `why_starred`, `next_action`, metrics, README fields).
- Added `.base` generation (`bases_files.py`):
  - `23.03.00_RepoIndex.base`
  - `23.03.00_ReviewQueue.base`
- Improved `23.03.01_CrawlGitHubURLs.md` writer to dedupe duplicate no-longer-maintained entries (`starred_repos_file.py`).
- Added no-API migration script with batching:
  - `tools/migrate_repo_notes.py`
- Batch 01 migration already applied (`start=1`, `limit=150`):
  - report: `docs/migration/batch-01.json`
  - 150 README placeholder notes created in `23.03_READMEs/`
- Added crawler CLI options:
  - `--readme-sync-mode`
  - `--max-readme-updates`
  - `--skip-bases`

## Important constraints

- Do **not** hammer GitHub API.
- Keep README sync conservative (default `new`, bounded by `--max-readme-updates`).
- For mass note cleanup, use `tools/migrate_repo_notes.py` only (no API).
- Process legacy notes in batches (`--start-number`, `--limit`).

## First checks

1. `git status`
2. `uv run python -m compileall src tools`
3. Run migration dry-run for one batch:
   - `uv run python tools/migrate_repo_notes.py --start-number 1 --limit 150 --dry-run --report docs/migration/batch-01-dry.json`
4. Spot-check 5 files in Obsidian for:
   - readable frontmatter
   - deduped overview rows
   - README local link presence
   - Bases file visibility

## Next improvements to implement

### 0) Post-refactor workstream: watchlist feeds for pi extension scouting (NEW)

> Start this only **after** current refactor stabilizes (green tests + merged baseline).

Goal: turn CrawlGitHub output into machine-readable candidate feeds that can be ingested into the pi extension watchlist system.

Target watchlist system (outside this repo):
- `~/programming/pi-extensions/docs/extensions-watchlist.json`
- `~/programming/pi-extensions/docs/extensions-watch-events.jsonl`
- importer script: `~/programming/pi-extensions/scripts/import-crawlgithub-watchlist.mjs`

Deliverables in this repo:

1. **GitHub candidate export (JSONL)**
   - Add export file(s), e.g. under `docs/exports/`:
     - `extensions-watch-seeds.github.jsonl`
   - Emit one normalized JSON object per candidate repo.

2. **NPM candidate export (JSONL)**
   - Add export file, e.g.:
     - `extensions-watch-seeds.npm.jsonl`
   - Seed from repo/package signals (and optional npm metadata lookup with conservative rate limits).

3. **Tagging/classification heuristic for candidates**
   - Add tags such as:
     - `pi/extension`, `pi/skill`, `pi/prompt`, `pi/theme`
     - `source/github-starred`, `source/npm`
   - Suggested signals:
     - repo topics (e.g. `pi-package`, `pi-coding-agent`)
     - `package.json` keywords (`pi-package`, `pi-extension`)
     - resource paths (`extensions/*.ts`, `skills/**/SKILL.md`, `prompts/*.md`, `themes/*.json`)

4. **Normalized candidate schema (for github + npm)**
   - Minimum fields:
     - `id`
     - `type` (`repo`/`npm`)
     - `source`
     - `title`
     - `starred` (for repo candidates)
     - `tags` (array)
     - `whyWatch`
     - `status` (default `new`)
     - `owner` (default `you`)
     - `discoveredAt`

5. **Safety and scope constraints**
   - Do not hammer APIs.
   - Prefer cached/local data first.
   - Keep npm lookups optional and bounded.

### Existing backlog (still valid)

1. **README sync quality**
   - Store per-repo README ETag/Last-Modified metadata if useful.
   - Add smarter sync policy (`if-pushed` + stale fallback days).
2. **Frontmatter safety**
   - Prevent overwriting user-written fields if conflicts occur.
   - Add schema version field for migration tracking.
3. **Bases refinement**
   - Tune filters/columns to match real workflow.
   - Add one view for maintained + high-star + missing rationale.
4. **Migration ergonomics**
   - Add `--summary-only` output.
   - Add resume checkpoint file support.
5. **Testing**
   - Add unit tests for:
     - table row dedupe
     - frontmatter render order
     - starred file dedupe behavior

## Suggested batch execution plan

- Batch size: 150 files.
- Sequence:
  - `1..150`, `151..300`, ..., `1501..1650`.
- For each batch:
  1. dry-run + report
  2. real run
  3. spot-check
  4. commit

## Commands (examples)

```sh
uv run crawl-github --skip-existing --max-repos 50 --readme-sync-mode new --max-readme-updates 10
uv run python tools/migrate_repo_notes.py --start-number 1 --limit 150 --dry-run --report docs/migration/batch-01-dry.json
uv run python tools/migrate_repo_notes.py --start-number 1 --limit 150 --report docs/migration/batch-01.json --dedupe-starred-file

# post-refactor target (new workstream):
# uv run crawl-github --export-watch-seeds docs/exports/extensions-watch-seeds.github.jsonl
# uv run crawl-github --export-npm-seeds docs/exports/extensions-watch-seeds.npm.jsonl
```

## Definition of done for next session

### Core DoD (always)

- One full migration batch completed and committed.
- Bases files verified in Obsidian.
- No duplicate rows reintroduced.
- API-safe crawl run validated.

### Additional DoD (only if refactor is finished)

- Added JSONL export(s) for watchlist seeds under `docs/exports/`.
- Export schema documented (fields + tags + examples).
- At least one dry-run candidate export generated from starred repos.
- npm candidate path defined (implemented or explicitly stubbed with TODO + interface contract).
