#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(r"C:\Users\mjpa\Documents\Obsidian\20-29_Input\23_Schriftliches\23.03_Code")
README_SUBDIR = "23.03_READMEs"

TABLE_ROW_PATTERN = re.compile(
    r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$"
)

FRONTMATTER_ORDER = [
    "type",
    "source",
    "repo",
    "repo_url",
    "owner",
    "repo_name",
    "repo_description",
    "maintained",
    "review_status",
    "why_starred",
    "next_action",
    "stars",
    "watchers",
    "forks",
    "contributors",
    "last_release",
    "last_pushed_at",
    "last_seen_date",
    "topics",
    "language",
    "license",
    "readme_note",
    "readme_sha256",
    "readme_synced_at",
    "readme_source_pushed_at",
]


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value is None:
        return '""'

    text = str(value).strip()
    if text == "":
        return '""'

    if re.fullmatch(r"[A-Za-z0-9_./:@+\-]+", text):
        return text

    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---\n"):
        return {}, content

    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content

    block = content[4:end]
    body = content[end + 5 :]

    data: dict[str, Any] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = _strip_quotes(value.strip())

    return data, body


def render_frontmatter(frontmatter: dict[str, Any]) -> str:
    if not frontmatter:
        return ""

    keys: list[str] = []
    for key in FRONTMATTER_ORDER:
        if key in frontmatter:
            keys.append(key)
    for key in frontmatter:
        if key not in keys:
            keys.append(key)

    lines = ["---"]
    for key in keys:
        lines.append(f"{key}: {_yaml_scalar(frontmatter[key])}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def sanitize_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "-", value)


def readme_relative_path(repo_url: str, owner: str, repo_name: str) -> str:
    digest = hashlib.sha256(repo_url.lower().encode("utf-8")).hexdigest()[:12]
    filename = f"{sanitize_name(owner)}__{sanitize_name(repo_name)}__{digest}.md"
    return (Path(README_SUBDIR) / filename).as_posix()


def infer_repo_header(body: str) -> tuple[str, str] | tuple[None, None]:
    match = re.search(r"^## \[(.+?)\]\((https://github.com/[^)]+)\)", body, re.MULTILINE)
    if not match:
        return None, None
    return match.group(1).strip(), match.group(2).strip()


def split_owner_repo(repo_url: str) -> tuple[str, str] | tuple[None, None]:
    cleaned = repo_url.rstrip("/")
    parts = cleaned.split("/")
    if len(parts) < 5:
        return None, None
    return parts[-2], parts[-1]


def infer_default_readme_url(body: str, repo_url: str) -> str:
    iframe_match = re.search(r'src="(https://github.com/[^" ]+)"', body)
    if iframe_match:
        iframe_url = iframe_match.group(1)
        if "/blob/" in iframe_url:
            return iframe_url
    return repo_url.rstrip("/") + "/blob/main/README.md"


def find_overview_table_bounds(lines: list[str]) -> tuple[int, int] | None:
    for i, line in enumerate(lines):
        if line.startswith("| Date") and i + 1 < len(lines) and lines[i + 1].startswith("|---"):
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            return i, j
    return None


def parse_table_row(line: str) -> dict[str, str] | None:
    match = TABLE_ROW_PATTERN.match(line.strip())
    if not match:
        return None
    date, watchers, forks, stars, contributors, release = match.groups()
    return {
        "date": date,
        "watchers": watchers.strip(),
        "forks": forks.strip(),
        "stars": stars.strip(),
        "contributors": contributors.strip(),
        "latest_release": release.strip(),
    }


def format_table_row(row: dict[str, str]) -> str:
    return (
        f"| {row['date']} | {row['watchers']} | {row['forks']} | "
        f"{row['stars']} | {row['contributors']} | {row['latest_release']} |"
    )


def dedupe_overview_rows(body: str) -> tuple[str, int, dict[str, str] | None]:
    lines = body.splitlines()
    bounds = find_overview_table_bounds(lines)
    if not bounds:
        return body, 0, None

    start, end = bounds
    row_lines = lines[start + 2 : end]

    parsed: list[dict[str, str]] = []
    for line in row_lines:
        row = parse_table_row(line)
        if row:
            parsed.append(row)

    if not parsed:
        return body, 0, None

    by_date: dict[str, dict[str, str]] = {}
    for row in parsed:
        by_date[row["date"]] = row

    ordered_rows = [by_date[d] for d in sorted(by_date.keys())]
    new_row_lines = [format_table_row(r) for r in ordered_rows]

    removed = max(0, len(row_lines) - len(new_row_lines))
    if new_row_lines != row_lines:
        lines = lines[: start + 2] + new_row_lines + lines[end:]
        body = "\n".join(lines).rstrip("\n") + "\n"

    return body, removed, ordered_rows[-1]


def ensure_readme_links(body: str, readme_note_path: str, readme_online_url: str) -> tuple[str, bool]:
    local_line = f"- Lokal (durchsuchbar): [[{readme_note_path}]]"
    github_line = f"- GitHub: [README online]({readme_online_url})"

    lines = body.splitlines()
    readme_index = next((i for i, line in enumerate(lines) if line.strip().startswith("## README")), None)
    overview_index = next((i for i, line in enumerate(lines) if line.strip().startswith("## Overview")), None)

    if readme_index is None:
        insert_at = overview_index if overview_index is not None else len(lines)
        lines[insert_at:insert_at] = ["## README", "", local_line, github_line, ""]
        return "\n".join(lines).rstrip("\n") + "\n", True

    section_end = len(lines)
    for i in range(readme_index + 1, len(lines)):
        if lines[i].startswith("## "):
            section_end = i
            break

    section = "\n".join(lines[readme_index:section_end])
    additions: list[str] = []
    if "Lokal (durchsuchbar):" not in section:
        additions.append(local_line)
    if "README online" not in section:
        additions.append(github_line)

    if not additions:
        return body, False

    insert_at = readme_index + 1
    while insert_at < section_end and lines[insert_at].strip() == "":
        insert_at += 1
    lines[insert_at:insert_at] = additions + [""]

    return "\n".join(lines).rstrip("\n") + "\n", True


def ensure_readme_placeholder(
    root: Path,
    readme_note_path: str,
    repo: str,
    repo_url: str,
    repo_note: str,
    dry_run: bool,
) -> bool:
    if not readme_note_path:
        return False

    abs_path = root / Path(readme_note_path)
    if abs_path.exists():
        return False

    content = (
        "---\n"
        "type: repo_readme_snapshot\n"
        "source: github-star\n"
        f"repo: {_yaml_scalar(repo)}\n"
        f"repo_url: {_yaml_scalar(repo_url)}\n"
        f"repo_note: {_yaml_scalar(repo_note)}\n"
        "readme_sha256: pending\n"
        "readme_synced_at: pending\n"
        "---\n\n"
        f"# README snapshot for {repo}\n\n"
        f"- Repo note: [[{repo_note}]]\n"
        f"- GitHub: {repo_url}\n\n"
        "_README snapshot pending. This placeholder was created by migrate_repo_notes.py._\n"
    )

    if not dry_run:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")

    return True


def infer_number(path: Path) -> int | None:
    m = re.match(r"23\.03\.(\d+)_", path.name)
    if not m:
        return None
    return int(m.group(1))


def process_repo_file(path: Path, root: Path, dry_run: bool, create_readme_placeholders: bool) -> dict[str, Any]:
    original = path.read_text(encoding="utf-8", errors="ignore")
    frontmatter, body = parse_frontmatter(original)

    changed = False
    frontmatter_added = not original.startswith("---\n")

    header_description, repo_url = infer_repo_header(body)
    repo_description = header_description or frontmatter.get("repo_description") or "No description found"

    owner, repo_name_from_url = split_owner_repo(repo_url or "")
    filename_repo_name = re.sub(r"^23\.03\.\d+_", "", path.stem)
    repo_name = repo_name_from_url or filename_repo_name

    readme_note = frontmatter.get("readme_note")
    if not readme_note and repo_url and owner and repo_name:
        readme_note = readme_relative_path(repo_url, owner, repo_name)

    body, removed_rows, latest_row = dedupe_overview_rows(body)

    readme_links_added = False
    if repo_url and readme_note:
        readme_online_url = infer_default_readme_url(body, repo_url)
        body, readme_links_added = ensure_readme_links(body, readme_note, readme_online_url)

    readme_placeholder_created = False
    if create_readme_placeholders and repo_url and readme_note and owner and repo_name:
        readme_placeholder_created = ensure_readme_placeholder(
            root=root,
            readme_note_path=readme_note,
            repo=f"{owner}/{repo_name}",
            repo_url=repo_url,
            repo_note=path.stem,
            dry_run=dry_run,
        )

    if latest_row:
        frontmatter["stars"] = latest_row["stars"]
        frontmatter["watchers"] = latest_row["watchers"]
        frontmatter["forks"] = latest_row["forks"]
        frontmatter["contributors"] = latest_row["contributors"]
        frontmatter["last_release"] = latest_row["latest_release"]
        frontmatter["last_seen_date"] = latest_row["date"]

    if repo_url:
        frontmatter["repo_url"] = repo_url
    if owner:
        frontmatter["owner"] = owner
    if repo_name:
        frontmatter["repo_name"] = repo_name
    if owner and repo_name:
        frontmatter["repo"] = f"{owner}/{repo_name}"

    frontmatter["repo_description"] = repo_description
    frontmatter["type"] = frontmatter.get("type", "checkbox")
    frontmatter["source"] = "github-star"
    frontmatter["maintained"] = frontmatter.get("maintained", "true")
    frontmatter["review_status"] = frontmatter.get("review_status") or "inbox"
    frontmatter.setdefault("why_starred", "")
    frontmatter.setdefault("next_action", "")
    frontmatter.setdefault("topics", "")
    frontmatter.setdefault("language", "")
    frontmatter.setdefault("license", "")

    if readme_note:
        frontmatter["readme_note"] = readme_note

    rewritten = render_frontmatter(frontmatter) + body.lstrip("\n")
    if rewritten != original:
        changed = True
        if not dry_run:
            path.write_text(rewritten, encoding="utf-8")

    return {
        "file": str(path),
        "changed": changed,
        "frontmatter_added": frontmatter_added,
        "rows_removed": removed_rows,
        "readme_links_added": readme_links_added,
        "readme_placeholder_created": readme_placeholder_created,
    }


def dedupe_starred_file(path: Path, dry_run: bool) -> dict[str, Any]:
    if not path.exists():
        return {"file": str(path), "changed": False, "entries_removed": 0}

    content = path.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()

    if "## no longer maintained" not in content or "## files to scrape" not in content:
        return {"file": str(path), "changed": False, "entries_removed": 0}

    before, rest = content.split("## no longer maintained", 1)
    no_longer, after = rest.split("## files to scrape", 1)

    heading = None
    groups: list[tuple[str, list[str]]] = []
    idx: dict[str, int] = {}

    for raw in no_longer.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("### [[") and line.endswith("]]"):
            heading = line
            if heading not in idx:
                idx[heading] = len(groups)
                groups.append((heading, []))
            continue
        if line.startswith("- [[") and line.endswith("]]"):
            if heading is None:
                heading = "### [[Legacy]]"
                if heading not in idx:
                    idx[heading] = len(groups)
                    groups.append((heading, []))
            groups[idx[heading]][1].append(line)

    seen = set()
    removed = 0
    out_groups: list[tuple[str, list[str]]] = []
    for h, entries in groups:
        uniq: list[str] = []
        for e in entries:
            if e in seen:
                removed += 1
                continue
            seen.add(e)
            uniq.append(e)
        if uniq:
            out_groups.append((h, uniq))

    files_to_scrape_lines = [ln.strip() for ln in after.splitlines() if ln.strip().startswith("http")]
    dedup_urls: list[str] = []
    seen_urls = set()
    for url in files_to_scrape_lines:
        if url in seen_urls:
            removed += 1
            continue
        seen_urls.add(url)
        dedup_urls.append(url)

    no_longer_lines: list[str] = []
    for h, entries in out_groups:
        no_longer_lines.append(h)
        no_longer_lines.extend(entries)
        no_longer_lines.append("")
    while no_longer_lines and not no_longer_lines[-1].strip():
        no_longer_lines.pop()

    rewritten = (
        before.rstrip() + "\n"
        + "## no longer maintained\n"
        + "\n".join(no_longer_lines).rstrip()
        + "\n\n"
        + "## files to scrape\n"
        + "\n".join(dedup_urls).rstrip()
        + "\n"
    )

    changed = rewritten != content
    if changed and not dry_run:
        path.write_text(rewritten, encoding="utf-8")

    return {"file": str(path), "changed": changed, "entries_removed": removed}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch-migrate CrawlGitHub repo notes without API calls."
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--start-number", type=int, default=1)
    parser.add_argument("--limit", type=int, default=150)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional JSON report path.",
    )
    parser.add_argument(
        "--dedupe-starred-file",
        action="store_true",
        help="Also dedupe 23.03.01_CrawlGitHubURLs.md.",
    )
    parser.add_argument(
        "--create-readme-placeholders",
        action="store_true",
        help="Create placeholder files for missing local README notes.",
    )
    args = parser.parse_args()

    files = sorted(
        [p for p in args.root.glob("23.03.*_*.md") if p.name != "23.03.01_CrawlGitHubURLs.md"],
        key=lambda p: infer_number(p) or 0,
    )

    selected: list[Path] = []
    effective_limit = max(0, args.limit)
    if effective_limit > 0:
        for path in files:
            number = infer_number(path)
            if number is None:
                continue
            if number < args.start_number:
                continue
            selected.append(path)
            if len(selected) >= effective_limit:
                break

    report: dict[str, Any] = {
        "root": str(args.root),
        "start_number": args.start_number,
        "limit": args.limit,
        "dry_run": args.dry_run,
        "selected_files": len(selected),
        "changed_files": 0,
        "frontmatter_added": 0,
        "rows_removed": 0,
        "readme_links_added": 0,
        "readme_placeholders_created": 0,
        "files": [],
    }

    for path in selected:
        result = process_repo_file(
            path,
            root=args.root,
            dry_run=args.dry_run,
            create_readme_placeholders=args.create_readme_placeholders,
        )
        report["files"].append(result)
        if result["changed"]:
            report["changed_files"] += 1
        if result["frontmatter_added"]:
            report["frontmatter_added"] += 1
        report["rows_removed"] += int(result["rows_removed"])
        if result["readme_links_added"]:
            report["readme_links_added"] += 1
        if result["readme_placeholder_created"]:
            report["readme_placeholders_created"] += 1

    if args.dedupe_starred_file:
        starred_file = args.root / "23.03.01_CrawlGitHubURLs.md"
        dedupe_result = dedupe_starred_file(starred_file, dry_run=args.dry_run)
        report["starred_file"] = dedupe_result

    output = json.dumps(report, indent=2, ensure_ascii=False)
    print(output)

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
