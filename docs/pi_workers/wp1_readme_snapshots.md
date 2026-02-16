## API-safe design: GitHub README snapshots in Obsidian

### 1) Stable hashed filename
- Cache root: `/.obsidian/cache/github-readmes/`
- Build canonical key (stable, rename-safe):  
  `gh|github.com|repo_id:<repo_id>|readme_path:<resolved_path>`
- Filename:  
  `<base32(sha256(canonical_key)).slice(0,26)>.md`  
  Example: `A7K3...Q2.md`
- Keep `owner/repo` only as metadata (not in filename), so repo renames don’t churn files.

---

### 2) Content hash tracking
Use `/.obsidian/cache/github-readmes/index.json` (or sqlite) with one record per snapshot:

```json
{
  "id": "A7K3...Q2",
  "repo_id": 123456,
  "full_name": "owner/repo",
  "snapshot_file": ".obsidian/cache/github-readmes/A7K3...Q2.md",
  "etag": "\"abc123\"",
  "last_modified": "Wed, 14 Feb 2026 10:00:00 GMT",
  "content_sha256": "9f86d081...",
  "last_checked_at": "2026-02-16T14:20:00Z",
  "last_changed_at": "2026-02-10T09:00:00Z",
  "next_check_at": "2026-02-23T09:00:00Z",
  "status": "ok",
  "fail_count": 0
}
```

- Hash normalized bytes (`\n` line endings) for stable `content_sha256`.
- Update snapshot only when hash changes (atomic write: temp file + rename).

---

### 3) When to refresh
- Always use conditional GET (`If-None-Match`, `If-Modified-Since`) on `GET /repos/{owner}/{repo}/readme`.
- Refresh triggers:
  - no local snapshot
  - `now >= next_check_at`
  - manual force refresh
- Suggested cadence:
  - newly added / recently changed: every **24h**
  - unchanged for 3 checks: every **7d**
  - unchanged for 12 checks: every **30d**
- Run through a small queue (1–2 concurrent) to stay rate-limit friendly.

---

### 4) Failure handling
- **Never delete last good snapshot** on errors.
- `404` README missing: set `status=missing`, retry in **7d**.
- `403/429` rate limit: honor `Retry-After` / `X-RateLimit-Reset`, pause jobs.
- `5xx` / network: exponential backoff with jitter (15m → 1h → 6h → 24h, cap 7d).
- After N failures (e.g., 5), mark `status=error` and surface in a “Sync Issues” note/log.
