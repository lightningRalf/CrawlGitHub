# Watchlist seed export schema

CrawlGitHub can export pi-extension scouting candidates as JSONL files.

- GitHub candidates: `docs/exports/extensions-watch-seeds.github.jsonl`
- npm candidates: `docs/exports/extensions-watch-seeds.npm.jsonl`

It can also sync candidates directly into Obsidian notes/frontmatter with
`--sync-watch-candidates` and generate `23.03.00_WatchCandidates.base`.

Optional lifecycle pruning with `--prune-watch-candidates` archives notes that
are no longer detected (`watch_status: archived`) instead of deleting them.

Each line is one JSON object.

## Normalized fields

| Field | Type | Notes |
|---|---|---|
| `id` | string | Stable identifier (`github:<owner/repo>` or `npm:<package>`). |
| `type` | string | `repo` or `npm`. |
| `source` | string | `github-starred` (repo) or `npm` (npm candidates). |
| `title` | string | Human-readable title (`owner/repo` or package name). |
| `starred` | boolean | `true` for repo candidates, `false` for npm candidates. |
| `tags` | string[] | Includes pi classification tags and source tags. |
| `whyWatch` | string | Short reason summary from detected signals. |
| `status` | string | Default `new` in exports; synced notes may transition to `archived` when pruned. |
| `owner` | string | Default `you`. |
| `discoveredAt` | string | ISO timestamp. |

### Common optional fields

- `repo`, `repoUrl`, `repoNote`
- `package`, `fromRepos`, `fromRepoIds`
- explainability metadata: `signalReasons`, `signalSources`, `signalCount`, `confidence`
- npm enrichment (optional): `npmLatestVersion`, `npmDescription`, `npmKeywords`

### Sync-only frontmatter lifecycle fields

When using `--sync-watch-candidates` (with or without pruning), notes can include:

- `watch_updated_at` (last sync touch)
- `watch_reactivated_at` (set when an archived candidate reappears)
- `watch_archived_at` (set when pruned/archived)
- `watch_signal_sources`, `watch_signal_count`, `watch_confidence` (triage explainability fields)

### Optional telemetry artifact

If `CRAWLGITHUB_WATCH_TELEMETRY_FILE` is configured, each watch sync/export run writes
a machine-readable JSON summary containing:

- `event` (`watch-candidate-sync` or `watch-seed-export`)
- `written_at` (UTC timestamp)
- `stats` (including confidence/source distributions)

## Tagging heuristics

Classification tags:

- `pi/extension`
- `pi/skill`
- `pi/prompt`
- `pi/theme`

Source tags:

- `source/github-starred`
- `source/npm`

Signal sources used (local-first):

1. repo frontmatter (`topics`, `repo_name`, `repo_description`)
2. local README snapshot content (`23.03_READMEs/*`)
3. path-pattern hints in README text:
   - `extensions/*.ts|js`
   - `skills/**/SKILL.md`
   - `prompts/*.md`
   - `themes/*.json`
4. npm package strings extracted from README install commands / package snippets

False-positive guardrails:

- marker/phrase matching is boundary-aware (avoids accidental substring matches like `api extension` => `pi extension`)
- generic phrase matching is frontmatter-weighted; weak README/body phrase hits alone are not enough
- fallback repo-identity anchor is conservative (e.g. `owner/pi`), not broad `*-pi-*` name matching
- confidence is derived from signal source mix (`topic|signal|phrase|path|anchor|derived|npm-keyword`) to make triage sorting more explicit

Optional npm metadata lookup can be enabled with `--max-npm-lookups <N>`.

## Example objects

```json
{"id":"github:badlogic/pi","type":"repo","source":"github-starred","title":"badlogic/pi","starred":true,"tags":["pi/extension","source/github-starred"],"whyWatch":"topic:pi-coding-agent; signal:pi-coding-agent","signalReasons":["topic:pi-coding-agent","signal:pi-coding-agent"],"signalSources":["topic","signal"],"signalCount":2,"confidence":"high","status":"new","owner":"you","discoveredAt":"2026-02-16T19:40:00Z","repo":"badlogic/pi","repoUrl":"https://github.com/badlogic/pi","repoNote":"23.03.1197_pi"}
{"id":"npm:@badlogic/pi","type":"npm","source":"npm","title":"@badlogic/pi","starred":false,"tags":["pi/extension","source/npm"],"whyWatch":"derived-from:badlogic/pi","signalReasons":["derived-from:badlogic/pi"],"signalSources":["derived"],"signalCount":1,"confidence":"low","status":"new","owner":"you","discoveredAt":"2026-02-16T19:40:00Z","package":"@badlogic/pi","fromRepos":["badlogic/pi"]}
```
