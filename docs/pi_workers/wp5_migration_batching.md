Here’s a **safe, local-only migration workflow** for ~1500 Markdown files.

## 1) Pre-migration safety (no content changes yet)

**Create a dedicated branch and backups**
1. Create branch: `migration/md-frontmatter-dedupe`
2. Create immutable baseline tag: `migration/C0-baseline`
3. Create offline backup artifact (extra safety):  
   - git bundle or zip of repo at baseline
4. Build file inventory:
   - `/migration/manifests/all-md.txt` (all `*.md`)
   - `/migration/reports/checksums-baseline.json` (sha256 per file)

**Checkpoint C0**
- Clean working tree
- Baseline tag + backup artifact exists
- File count matches expected (~1500)

**Rollback from C0**
- Full rollback: reset branch to `migration/C0-baseline`
- Disaster rollback: restore from bundle/zip backup

---

## 2) Build an idempotent migration script

Use one local script, e.g. `/scripts/migrate_markdown.py` (or `.js`), with flags:

- `--dry-run` (no writes)
- `--apply`
- `--batch-file /migration/manifests/batch-001.txt`
- `--report /migration/reports/batch-001.json`
- `--state /migration/checkpoints/state.json`

### Script behavior (safe rules)

### A) Table row dedupe
- Parse Markdown with a local parser (avoid regex-only parsing).
- Only dedupe valid table body rows (never header/separator).
- Normalize dedupe key per row (trim cells, collapse whitespace, lowercase if desired).
- Keep first occurrence, preserve original row formatting for kept rows.
- Skip ambiguous blocks (log as `skipped`).

### B) Frontmatter
- If frontmatter missing, insert YAML at top.
- If frontmatter exists, only add missing keys (don’t overwrite existing values unless explicitly configured).
- Suggested defaults: `title`, `slug`, `migrated_at`, `migrated_by`.
- Ensure valid YAML output.

### C) Idempotency
- Running twice should produce zero additional diffs.
- Add a quick idempotency test against sample files.

**Checkpoint C1**
- Dry-run report generated
- Idempotency confirmed on sample set
- No parse crashes

**Rollback from C1**
- No repo rollback needed if no writes (`--dry-run` only)

---

## 3) Pilot batch before full run

Run on a small pilot (e.g. 30 files):
- `/migration/manifests/pilot.txt`
- run `--dry-run`, inspect report
- run `--apply`
- validate and spot-check manually

Validation checks:
- frontmatter parses successfully
- markdown linter passes (local)
- no unexpected large diffs

Commit pilot separately.

**Checkpoint C2**
- Pilot commit + tag `migration/C2-pilot-ok`
- Team sign-off before scaling

**Rollback from C2**
- `git revert <pilot-commit>` (safest), or reset to C1 if not shared

---

## 4) Batch execution plan (main migration)

Use **15 batches of 100 files** (or 30x50 if you want finer rollback units).

Store manifests:
- `/migration/manifests/batch-001.txt` ... `batch-015.txt`

For each batch:
1. `--dry-run` and inspect report
2. `--apply`
3. run validation scripts/lint
4. manual spot-check (5–10 files)
5. commit + tag `migration/C3-batch-001`, etc.

Also write:
- `/migration/reports/batch-001.json`
- `/migration/checkpoints/state.json` (completed batches, timestamps, stats)

**Stop conditions (fail-safe)**
- Any YAML parse error
- Any script crash
- Unexpectedly high change rate (define threshold)
- Validation failure

---

## 5) Rollback strategy (practical matrix)

- **Single batch bad**: `git revert <batch-commit>`
- **Multiple recent bad batches**: revert those commits in reverse order
- **Abort entire migration**: reset to `migration/C0-baseline`
- **File-level rollback**: restore specific files from baseline tag

Keep each batch in its own commit for clean reversibility.

---

## 6) Finalization

After all batches:
1. Run full-repo validation once more
2. Recompute checksums and diff stats
3. Produce final report:
   - files changed
   - rows removed
   - frontmatter added/updated
   - skipped/errored files
4. Merge migration branch only after sign-off

---

If you want, I can also draft:
- a concrete `/migration/config.yaml`,
- a batch runner shell/PowerShell script,
- and a minimal `migrate_markdown.py` skeleton with these safety guards.
