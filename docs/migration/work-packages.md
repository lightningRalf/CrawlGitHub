# Migration Work Packages (no API)

Use `tools/migrate_repo_notes.py` in batches to avoid risky mass rewrites.

## Progress

- ✅ Batch 01 applied (`--start-number 1 --limit 150`)
  - Report: `docs/migration/batch-01.json`
  - Changed files: `149`
  - Duplicate rows removed: `995`
  - README placeholder files created: `150`

- ✅ Batches 02–11 applied (`--start-number 151..1501`, `--limit 150`)
  - Reports: `docs/migration/batch-02.json` … `docs/migration/batch-11.json`
  - Selected files: `1414`
  - Changed files: `1412`
  - Duplicate rows removed: `5829`
  - README links added: `1411`
  - README placeholder files created: `1406`

- ✅ Catch-up pass applied (`--start-number 1 --limit 5000`)
  - Report: `docs/migration/catchup.json`
  - Remaining changed files: `6`
  - Additional README links added: `6`

- ✅ Starred file dedupe verification
  - Report: `docs/migration/starred-file-dedupe-02.json`
  - Changes needed: `false`

- ✅ Duplicate repo-note cleanup (post migration)
  - Report: `docs/migration/duplicate-note-cleanup.json`
  - Removed duplicate note files: `5`
  - Kept canonical note files: `5`
  - Merged historical overview rows into canonical files before deletion

## Package size

- Batch size: `150` files
- Pattern: `23.03.<number>_*.md`

## Batch plan

| Batch | Start number | Limit |
|------:|-------------:|------:|
| 01 | 1 | 150 |
| 02 | 151 | 150 |
| 03 | 301 | 150 |
| 04 | 451 | 150 |
| 05 | 601 | 150 |
| 06 | 751 | 150 |
| 07 | 901 | 150 |
| 08 | 1051 | 150 |
| 09 | 1201 | 150 |
| 10 | 1351 | 150 |
| 11 | 1501 | 150 |

## Command template

Dry run:

```sh
uv run python tools/migrate_repo_notes.py --start-number <START> --limit 150 --dry-run --report docs/migration/batch-<NN>-dry.json
```

Apply:

```sh
uv run python tools/migrate_repo_notes.py --start-number <START> --limit 150 --create-readme-placeholders --report docs/migration/batch-<NN>.json
```

Apply + dedupe `23.03.01_CrawlGitHubURLs.md`:

```sh
uv run python tools/migrate_repo_notes.py --start-number <START> --limit 150 --dedupe-starred-file --report docs/migration/batch-<NN>.json
```

## Validation after each batch

1. Check report counts (`changed_files`, `rows_removed`, `readme_links_added`).
2. Spot-check 3 files in Obsidian.
3. Ensure frontmatter keys are intact.
4. Ensure Overview table still renders.
5. Commit batch separately.
