Great idea—here’s a practical **proposal** for a `ReviewQueue.base` focused on items that are starred but missing a meaningful `why_starred`.

---

### Proposed file: `ReviewQueue.base`

```yaml
name: ReviewQueue

source:
  folders:
    - Inbox
    - Notes
    - Resources
  includeSubfolders: true

computed:
  rationale_status:
    formula: >
      if(empty(why_starred), "Missing",
      if(length(trim(why_starred)) < 25, "Too short", "OK"))
  age_days:
    formula: dateBetween(today(), starred_at, "days")

views:
  - name: Missing Why (Action Queue)
    type: table
    filters:
      and:
        - starred == true
        - rationale_status in ["Missing", "Too short"]
        - review_status != "Done"
    sort:
      - priority desc
      - age_days desc
    columns:
      - file
      - starred_at
      - age_days
      - why_starred
      - rationale_status
      - priority
      - tags
      - source_url
      - review_status
      - last_reviewed

  - name: Overdue (14+ days)
    type: table
    filters:
      and:
        - starred == true
        - rationale_status in ["Missing", "Too short"]
        - age_days >= 14
    sort:
      - age_days desc
    columns:
      - file
      - age_days
      - why_starred
      - priority
      - review_status

  - name: Completed This Week
    type: table
    filters:
      and:
        - review_status == "Done"
        - last_reviewed >= startOfWeek(today())
    sort:
      - last_reviewed desc
    columns:
      - file
      - why_starred
      - last_reviewed
      - outcome
```

---

### Expected note properties (frontmatter)

Use these consistently in starred notes:

- `starred: true/false`
- `why_starred: ""`
- `starred_at: YYYY-MM-DD`
- `priority: High|Medium|Low`
- `review_status: New|In Progress|Done|Dropped`
- `last_reviewed: YYYY-MM-DD`
- `source_url:`
- `outcome:` (optional summary after review)

---

### Weekly workflow (30–45 min total)

1. **Monday (10 min) – Triage**
   - Open **Missing Why (Action Queue)**.
   - Fill `priority` for new items.
   - Set top 5 for this week.

2. **Midweek (15–20 min) – Fill rationale**
   - For each top item, write 1–2 sentence `why_starred`:
     - Why it mattered
     - What action/value it supports

3. **Thursday (10 min) – Prune**
   - Review **Overdue (14+ days)**.
   - If no rationale emerges, set `review_status: Dropped` and unstar.

4. **Friday (5 min) – Close out**
   - Mark completed items `Done`.
   - Update `last_reviewed` and `outcome`.

---

If you want, I can also provide a **stricter version** where `why_starred` must contain at least one action verb (e.g., “use”, “apply”, “reference”) before it counts as complete.
