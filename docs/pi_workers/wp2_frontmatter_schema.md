Here’s a **concise, Bases-friendly, LLM-friendly** frontmatter schema.

### Recommended frontmatter (`v1`)
```yaml
---
schema: gh-starred-repo/v1
gh_id: 123456789
gh_full_name: owner/repo
gh_url: https://github.com/owner/repo
gh_starred_at: 2026-02-01T12:34:56Z
sync_last_at: 2026-02-16T14:28:00Z
status: inbox                      # inbox|shortlist|adopted|archived
summary_auto: "What the repo does in one sentence."

# optional auto (sync-managed)
gh_description: ""
gh_topics: []
gh_language: ""
gh_stars: 0
gh_forks: 0
gh_license: ""
gh_archived: false
gh_pushed_at: 2026-02-15T08:00:00Z
sync_etag: ""

# optional manual (human-managed)
summary_manual: ""
note_why_starred: ""
note_use_cases: []
note_decision: watch               # watch|try|adopt|drop
note_priority: 3                   # 1..5
note_tags: []
note_related: []
note_last_reviewed_at: null
sync_lock: false
---
```

## Required fields
- `schema` (string, versioned)
- `gh_id` (number, stable GitHub repo ID)
- `gh_full_name` (`owner/repo`)
- `gh_url` (URL)
- `gh_starred_at` (ISO datetime)
- `sync_last_at` (ISO datetime)
- `status` (enum)
- `summary_auto` (short factual sentence)

## Optional fields
### Auto/sync-managed
`gh_description`, `gh_topics`, `gh_language`, `gh_stars`, `gh_forks`, `gh_license`, `gh_archived`, `gh_pushed_at`, `sync_etag`

### Manual/human-managed
`summary_manual`, `note_why_starred`, `note_use_cases`, `note_decision`, `note_priority`, `note_tags`, `note_related`, `note_last_reviewed_at`, `sync_lock`

---

## Update rules (to protect manual notes)
1. **Field ownership by prefix**
   - Sync can write only: `gh_*`, `sync_*`, `summary_auto`, `status` (optional).
   - Sync must never write: `summary_manual`, `note_*`.

2. **Lock switch**
   - If `sync_lock: true`, skip all writes except maybe logging externally.

3. **Immutable fields**
   - Never change after creation: `schema` (except explicit migration), `gh_id`, `gh_starred_at`.

4. **Do not delete unknown/manual fields**
   - Preserve all non-managed keys exactly as-is.

5. **Manual override precedence (for retrieval/UI)**
   - Use `summary_manual` if non-empty; else `summary_auto`.
   - Keep both fields separate (no destructive merge).

6. **Use ISO timestamps + flat keys**
   - Better sorting/filtering in Bases and cleaner LLM ingestion.
