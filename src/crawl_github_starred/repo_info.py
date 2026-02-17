from __future__ import annotations

import datetime
import hashlib
import logging
import os
import re
from typing import Any

import requests

from . import config
from . import github_api

logger = logging.getLogger(__name__)


FRONTMATTER_SCHEMA_VERSION = 2

FRONTMATTER_ORDER = [
    "type",
    "schema_version",
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
    "readme_last_attempt_at",
    "readme_last_status",
    "readme_etag",
    "readme_last_modified",
    "readme_source_pushed_at",
]

README_STATUS_RETRY_COOLDOWN_DAYS = {
    "not_found": 30,
    "forbidden": 7,
    "error": 2,
}

USER_AUTHORED_FRONTMATTER_FIELDS = {
    "review_status",
    "why_starred",
    "next_action",
}


TABLE_ROW_PATTERN = re.compile(
    r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$"
)


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


def _parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    if not content.startswith("---\n"):
        return {}, content

    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content

    frontmatter_block = content[4:end].splitlines()
    frontmatter: dict[str, Any] = {}
    for line in frontmatter_block:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = _strip_quotes(value.strip())

    body = content[end + 5 :]
    return frontmatter, body


def _render_frontmatter(frontmatter: dict[str, Any]) -> str:
    if not frontmatter:
        return ""

    ordered_keys: list[str] = []
    for key in FRONTMATTER_ORDER:
        if key in frontmatter:
            ordered_keys.append(key)
    for key in frontmatter:
        if key not in ordered_keys:
            ordered_keys.append(key)

    lines = ["---"]
    for key in ordered_keys:
        lines.append(f"{key}: {_yaml_scalar(frontmatter[key])}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _write_text_if_changed(path: str, content: str) -> bool:
    existing = ""
    if os.path.exists(path):
        existing = _read_text(path)
        if existing == content:
            return False

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def _read_note(markdown_file_path: str) -> tuple[dict[str, Any], str]:
    if not os.path.exists(markdown_file_path) or os.stat(markdown_file_path).st_size == 0:
        return {}, ""
    content = _read_text(markdown_file_path)
    return _parse_frontmatter(content)


def _write_note(markdown_file_path: str, frontmatter: dict[str, Any], body: str) -> bool:
    content = _render_frontmatter(frontmatter) + body.lstrip("\n")
    return _write_text_if_changed(markdown_file_path, content)


def _find_overview_table_bounds(lines: list[str]) -> tuple[int, int] | None:
    for i, line in enumerate(lines):
        if line.startswith("| Date") and i + 1 < len(lines) and lines[i + 1].startswith("|---"):
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            return i, j
    return None


def _parse_table_row(line: str) -> dict[str, str] | None:
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


def _format_table_row(row: dict[str, str]) -> str:
    return (
        f"| {row['date']} | {row['watchers']} | {row['forks']} | "
        f"{row['stars']} | {row['contributors']} | {row['latest_release']} |"
    )


def _dedupe_overview_rows(body: str) -> tuple[str, bool, dict[str, str] | None]:
    if not body.strip():
        return body, False, None

    lines = body.splitlines()
    bounds = _find_overview_table_bounds(lines)
    if not bounds:
        return body, False, None

    start, end = bounds
    row_lines = lines[start + 2 : end]

    parsed_rows: list[dict[str, str]] = []
    for line in row_lines:
        row = _parse_table_row(line)
        if row:
            parsed_rows.append(row)

    if not parsed_rows:
        return body, False, None

    by_date: dict[str, dict[str, str]] = {}
    for row in parsed_rows:
        by_date[row["date"]] = row  # keep latest row for each date

    ordered_dates = sorted(by_date.keys())
    ordered_rows = [by_date[date] for date in ordered_dates]
    new_row_lines = [_format_table_row(row) for row in ordered_rows]

    changed = new_row_lines != row_lines
    if changed:
        lines = lines[: start + 2] + new_row_lines + lines[end:]
        body = "\n".join(lines).rstrip("\n") + "\n"

    return body, changed, ordered_rows[-1]


def _append_overview_row(body: str, row: dict[str, str]) -> str:
    lines = body.splitlines()
    bounds = _find_overview_table_bounds(lines)
    if not bounds:
        return body

    _, end = bounds
    lines.insert(end, _format_table_row(row))
    return "\n".join(lines).rstrip("\n") + "\n"


def _has_row_for_date(body: str, date_str: str) -> bool:
    for line in body.splitlines():
        if line.startswith(f"| {date_str} |"):
            return True
    return False


def _build_header_block(
    repo_description: str,
    github_url: str,
    default_branch: str,
    readme_note_relative_path: str,
) -> str:
    github_readme_url = github_api.get_readme_url(github_url, default_branch)
    return (
        f"## [{repo_description}]({github_url})\n\n"
        "## README\n\n"
        f"- Lokal (durchsuchbar): [[{readme_note_relative_path}]]\n"
        f"- GitHub: [README online]({github_readme_url})\n\n"
        f"{config.README_TEMPLATE.format(github_readme_url)}\n"
        "## Overview\n\n"
        "| Date       | Watchers | Forks | Stars | Contributors | Latest Release |\n"
        "|------------|----------|-------|-------|--------------|----------------|\n"
    )


def _ensure_readme_links(
    body: str,
    readme_note_relative_path: str,
    github_url: str,
    default_branch: str,
) -> str:
    if not body.strip():
        return body

    local_line = f"- Lokal (durchsuchbar): [[{readme_note_relative_path}]]"
    github_line = f"- GitHub: [README online]({github_api.get_readme_url(github_url, default_branch)})"

    lines = body.splitlines()
    readme_index = next((i for i, line in enumerate(lines) if line.strip().startswith("## README")), None)
    overview_index = next((i for i, line in enumerate(lines) if line.strip().startswith("## Overview")), None)

    if readme_index is None:
        insert_at = overview_index if overview_index is not None else len(lines)
        section = ["## README", "", local_line, github_line, ""]
        lines[insert_at:insert_at] = section
        return "\n".join(lines).rstrip("\n") + "\n"

    section_end = len(lines)
    for i in range(readme_index + 1, len(lines)):
        if lines[i].startswith("## "):
            section_end = i
            break

    section_text = "\n".join(lines[readme_index:section_end])
    additions: list[str] = []
    if "Lokal (durchsuchbar):" not in section_text:
        additions.append(local_line)
    if "README online" not in section_text:
        additions.append(github_line)

    if not additions:
        return body

    insert_at = readme_index + 1
    while insert_at < section_end and lines[insert_at].strip() == "":
        insert_at += 1

    lines[insert_at:insert_at] = additions + [""]
    return "\n".join(lines).rstrip("\n") + "\n"


def _sanitize_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "-", value)


def _readme_relative_path(github_url: str, owner: str, repo_name: str) -> str:
    digest = hashlib.sha256(github_url.lower().encode("utf-8")).hexdigest()[:12]
    filename = f"{_sanitize_name(owner)}__{_sanitize_name(repo_name)}__{digest}.md"
    return os.path.join(config.README_NOTES_SUBDIR, filename).replace("\\", "/")


def _readme_absolute_path(relative_path: str) -> str:
    return os.path.join(config.WORKING_DIRECTORY, relative_path)


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def _write_readme_snapshot(
    readme_path: str,
    repo_note_filename: str,
    repo_full_name: str,
    github_url: str,
    default_branch: str,
    readme_content: str | None,
    readme_sha256: str,
    source_pushed_at: str,
) -> bool:
    now_iso = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    repo_note_link = repo_note_filename[:-3] if repo_note_filename.lower().endswith(".md") else repo_note_filename
    readme_online_url = github_api.get_readme_url(github_url, default_branch)

    if readme_content and readme_content.strip():
        readme_block = readme_content.strip() + "\n"
    else:
        readme_block = "_README snapshot not available yet._\n"

    snapshot = (
        "---\n"
        "type: repo_readme_snapshot\n"
        "source: github-star\n"
        f"repo: {_yaml_scalar(repo_full_name)}\n"
        f"repo_url: {_yaml_scalar(github_url)}\n"
        f"repo_note: {_yaml_scalar(repo_note_link)}\n"
        f"readme_sha256: {_yaml_scalar(readme_sha256)}\n"
        f"readme_synced_at: {_yaml_scalar(now_iso)}\n"
        f"readme_source_pushed_at: {_yaml_scalar(source_pushed_at)}\n"
        "---\n\n"
        f"# README snapshot for {repo_full_name}\n\n"
        f"- Repo note: [[{repo_note_link}]]\n"
        f"- GitHub: {github_url}\n"
        f"- README online: {readme_online_url}\n"
        f"- SHA256: `{readme_sha256}`\n"
        f"- Synced: `{now_iso}`\n\n"
        "---\n\n"
        f"{readme_block}"
    )

    return _write_text_if_changed(readme_path, snapshot)


def _to_int(value: Any) -> int | None:
    try:
        text = str(value).strip()
        if text == "":
            return None
        return int(text)
    except (TypeError, ValueError):
        return None


def _extract_markdown_number(filename: str) -> int | None:
    match = re.match(r"23\.03\.(\d+)_", filename)
    if not match:
        return None
    return int(match.group(1))


def _index_repo_files() -> tuple[dict[str, tuple[str, int]], int]:
    mapping: dict[str, tuple[str, int]] = {}
    max_number = 0

    for file in os.listdir(config.WORKING_DIRECTORY):
        number = _extract_markdown_number(file)
        if number is None:
            continue

        name_match = re.match(r"23\.03\.\d+_(.+)\.md", file)
        if not name_match:
            continue

        repo_name = name_match.group(1).lower()
        mapping[repo_name] = (file, number)
        max_number = max(max_number, number)

    return mapping, max_number


def _fetch_contributors_count(contributors_url: str, headers: dict) -> str | int:
    contributors_response = github_api.fetch_github_data(contributors_url, headers.copy())
    if not contributors_response:
        return "Error"

    payload = contributors_response.json()
    if isinstance(payload, dict) and "count" in payload:
        return payload["count"]
    if isinstance(payload, list):
        return len(payload)
    return "Error"


def _fetch_latest_release(releases_url: str, headers: dict) -> str:
    releases_response = github_api.fetch_github_data(releases_url, headers.copy())
    if not releases_response:
        return "No release found"

    payload = releases_response.json()
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        tag_name = payload[0].get("tag_name")
        if tag_name:
            return str(tag_name)
    return "No release found"


def _parse_iso_datetime(value: str) -> datetime.datetime | None:
    text = str(value or "").strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)

    return parsed.astimezone(datetime.timezone.utc)


def _is_readme_stale(
    readme_reference_at: str,
    stale_fallback_days: int,
    now_utc: datetime.datetime,
) -> bool:
    if stale_fallback_days <= 0:
        return False

    reference_dt = _parse_iso_datetime(readme_reference_at)
    if reference_dt is None:
        return True

    stale_delta = datetime.timedelta(days=stale_fallback_days)
    return now_utc - reference_dt >= stale_delta


def _stale_days_with_repo_jitter(
    stale_fallback_days: int,
    repo_identity: str,
    jitter_span_days: int,
) -> int:
    base_days = max(0, stale_fallback_days)
    jitter_span = max(0, jitter_span_days)
    if base_days <= 0 or jitter_span <= 0:
        return base_days

    normalized_identity = str(repo_identity or "").strip().lower()
    if not normalized_identity:
        return base_days

    digest = hashlib.sha256(normalized_identity.encode("utf-8")).hexdigest()
    jitter_days = int(digest[:8], 16) % jitter_span
    return base_days + jitter_days


def _readme_retry_cooldown_remaining(
    readme_last_status: str,
    readme_last_attempt_at: str,
    now_utc: datetime.datetime,
) -> datetime.timedelta | None:
    retry_cooldown_days = README_STATUS_RETRY_COOLDOWN_DAYS.get(str(readme_last_status or "").strip().lower(), 0)
    if retry_cooldown_days <= 0:
        return None

    attempt_dt = _parse_iso_datetime(readme_last_attempt_at)
    if attempt_dt is None:
        return None

    cooldown_delta = datetime.timedelta(days=retry_cooldown_days)
    elapsed = now_utc - attempt_dt
    if elapsed >= cooldown_delta:
        return None

    return cooldown_delta - elapsed


def _is_readme_retry_cooldown_active(
    readme_last_status: str,
    readme_last_attempt_at: str,
    now_utc: datetime.datetime,
) -> bool:
    return _readme_retry_cooldown_remaining(readme_last_status, readme_last_attempt_at, now_utc) is not None


def _readme_sync_reason(
    mode: str,
    readme_exists: bool,
    previous_source_pushed_at: str,
    current_source_pushed_at: str,
    readme_synced_at: str = "",
    readme_last_attempt_at: str = "",
    stale_fallback_days: int = 0,
    now_utc: datetime.datetime | None = None,
) -> str:
    mode = mode.lower()

    if mode == "off":
        return "mode-off"

    if mode == "always":
        return "always"

    if mode == "new":
        return "missing" if not readme_exists else "new-skip-existing"

    if mode == "if-pushed":
        if not readme_exists:
            return "missing"

        if current_source_pushed_at and previous_source_pushed_at != current_source_pushed_at:
            return "pushed"

        current_now_utc = now_utc or datetime.datetime.now(datetime.timezone.utc)
        stale_reference_at = str(readme_last_attempt_at or readme_synced_at)
        if _is_readme_stale(stale_reference_at, stale_fallback_days, current_now_utc):
            return "stale"

        return "if-pushed-skip-fresh"

    return "unknown-mode"


def _should_sync_readme(
    mode: str,
    readme_exists: bool,
    previous_source_pushed_at: str,
    current_source_pushed_at: str,
    readme_synced_at: str = "",
    readme_last_attempt_at: str = "",
    stale_fallback_days: int = 0,
    now_utc: datetime.datetime | None = None,
) -> bool:
    reason = _readme_sync_reason(
        mode=mode,
        readme_exists=readme_exists,
        previous_source_pushed_at=previous_source_pushed_at,
        current_source_pushed_at=current_source_pushed_at,
        readme_synced_at=readme_synced_at,
        readme_last_attempt_at=readme_last_attempt_at,
        stale_fallback_days=stale_fallback_days,
        now_utc=now_utc,
    )
    return reason in {"always", "missing", "pushed", "stale"}


def _collect_latest_metrics(
    latest_row: dict[str, str] | None,
    repo_data: dict[str, Any],
) -> dict[str, Any]:
    stars = _to_int(latest_row["stars"]) if latest_row else None
    watchers = _to_int(latest_row["watchers"]) if latest_row else None
    forks = _to_int(latest_row["forks"]) if latest_row else None
    contributors = _to_int(latest_row["contributors"]) if latest_row else None
    latest_release = latest_row["latest_release"] if latest_row else None

    return {
        "stars": stars if stars is not None else repo_data.get("stargazers_count", 0),
        "watchers": watchers if watchers is not None else repo_data.get("subscribers_count", 0),
        "forks": forks if forks is not None else repo_data.get("forks_count", 0),
        "contributors": contributors,
        "latest_release": latest_release,
    }


def _resolved_schema_version(current_value: Any) -> int:
    parsed = _to_int(current_value)
    if parsed is None:
        return FRONTMATTER_SCHEMA_VERSION
    return max(parsed, FRONTMATTER_SCHEMA_VERSION)


def _ensure_user_field(frontmatter: dict[str, Any], key: str, default_value: Any) -> None:
    if key not in USER_AUTHORED_FRONTMATTER_FIELDS:
        return

    if key not in frontmatter:
        frontmatter[key] = default_value
        return

    if key == "review_status" and not str(frontmatter.get(key, "")).strip():
        frontmatter[key] = default_value


def _upsert_frontmatter(
    frontmatter: dict[str, Any],
    repo_data: dict[str, Any],
    github_url: str,
    repo_description: str,
    maintained: bool,
    readme_note_relative_path: str,
    readme_sha256: str,
    readme_source_pushed_at: str,
    metrics: dict[str, Any],
    today: str,
) -> dict[str, Any]:
    updated = dict(frontmatter)

    owner_login = repo_data.get("owner_login")
    if not owner_login and isinstance(repo_data.get("owner"), dict):
        owner_login = repo_data["owner"].get("login")
    owner_login = owner_login or github_api.split_owner_repo(github_url)[0]

    license_spdx = repo_data.get("license_spdx_id")
    if not license_spdx and isinstance(repo_data.get("license"), dict):
        license_spdx = repo_data["license"].get("spdx_id")

    topics = repo_data.get("topics")
    if isinstance(topics, list):
        topics_text = ", ".join(sorted({str(topic).strip() for topic in topics if str(topic).strip()}))
    else:
        topics_text = str(topics or "")

    updated["type"] = updated.get("type", "checkbox")
    updated["schema_version"] = _resolved_schema_version(updated.get("schema_version"))
    updated["source"] = "github-star"
    updated["maintained"] = "true" if maintained else "false"
    updated["repo"] = repo_data.get("full_name") or f"{owner_login}/{repo_data.get('name', '')}".strip("/")
    updated["repo_url"] = github_url
    updated["owner"] = owner_login
    updated["repo_name"] = repo_data.get("name", "")
    updated["repo_description"] = repo_description
    updated["stars"] = metrics.get("stars", 0)
    updated["watchers"] = metrics.get("watchers", 0)
    updated["forks"] = metrics.get("forks", 0)

    contributors = metrics.get("contributors")
    if contributors is not None:
        updated["contributors"] = contributors

    latest_release = metrics.get("latest_release")
    if latest_release:
        updated["last_release"] = latest_release

    updated["last_pushed_at"] = readme_source_pushed_at
    updated["last_seen_date"] = today
    updated["topics"] = topics_text
    updated["language"] = repo_data.get("language") or ""
    updated["license"] = license_spdx or ""
    updated["readme_note"] = readme_note_relative_path

    if readme_sha256:
        updated["readme_sha256"] = readme_sha256

    if readme_source_pushed_at:
        updated["readme_source_pushed_at"] = readme_source_pushed_at

    _ensure_user_field(updated, "review_status", "inbox")
    _ensure_user_field(updated, "why_starred", "")
    _ensure_user_field(updated, "next_action", "")

    return updated


def generate_repo_info(
    urls: list[str],
    skip_existing: bool = False,
    max_repos: int | None = None,
    resume_from: int | None = None,
    readme_sync_mode: str | None = None,
    readme_stale_days: int | None = None,
    readme_stale_jitter_days: int | None = None,
    max_readme_updates: int | None = None,
) -> list[str]:
    """Generate repository information and update markdown notes."""
    headers = github_api.get_github_headers()

    effective_readme_sync_mode = (readme_sync_mode or config.README_SYNC_MODE).lower()
    if effective_readme_sync_mode not in config.README_SYNC_MODES:
        effective_readme_sync_mode = config.README_SYNC_MODE

    effective_readme_stale_days = (
        config.README_SYNC_STALE_DAYS if readme_stale_days is None else max(0, readme_stale_days)
    )
    effective_readme_stale_jitter_days = (
        config.README_SYNC_STALE_JITTER_DAYS
        if readme_stale_jitter_days is None
        else max(0, readme_stale_jitter_days)
    )

    readme_updates_remaining = (
        config.MAX_README_UPDATES_PER_RUN if max_readme_updates is None else max(0, max_readme_updates)
    )

    logger.info(f"Processing {len(urls)} repositories")
    logger.info(
        "README sync: mode=%s, stale_days=%s, stale_jitter_days=%s, max_updates=%s",
        effective_readme_sync_mode,
        effective_readme_stale_days,
        effective_readme_stale_jitter_days,
        readme_updates_remaining,
    )

    readme_sync_reason_counts: dict[str, int] = {}
    readme_sync_status_counts: dict[str, int] = {}
    readme_stale_window_counts: dict[int, int] = {}
    readme_sync_due_count = 0
    readme_sync_attempted_count = 0
    readme_sync_skipped_budget_count = 0
    readme_sync_skipped_cooldown_count = 0

    newly_unmaintained: list[str] = []
    repo_file_index, max_number = _index_repo_files()
    next_number = max_number + 1
    processed = 0

    for i, github_url in enumerate(urls, start=1):
        if max_repos is not None and processed >= max_repos:
            break

        logger.info(f"Processing repository {i}/{len(urls)}: {github_url}")
        repo_name_hint = github_url.rstrip("/").split("/")[-1].lower()

        if resume_from is not None and repo_name_hint in repo_file_index:
            _, markdown_number = repo_file_index[repo_name_hint]
            if markdown_number < resume_from:
                logger.info(
                    "Skipping %s (file number %s < resume-from %s)",
                    github_url,
                    markdown_number,
                    resume_from,
                )
                continue

        api_url = github_url.replace("https://github.com", "https://api.github.com/repos")
        response = github_api.fetch_github_data(api_url, headers.copy())
        if not response:
            logger.warning(f"Failed to get data for {github_url}, skipping")
            continue

        repo_data = response.json()
        repo_name = repo_data.get("name", repo_name_hint)
        repo_description = repo_data.get("description") or "No description found"
        default_branch = repo_data.get("default_branch", "main")
        contributors_url = repo_data.get("contributors_url", "")
        releases_url = str(repo_data.get("releases_url", "")).replace("{/id}", "")

        latest_commit_date = repo_data.get("pushed_at") or repo_data.get("updated_at") or ""
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        latest_commit_dt = None
        if latest_commit_date:
            try:
                latest_commit_dt = datetime.datetime.fromisoformat(
                    latest_commit_date.replace("Z", "+00:00")
                )
            except ValueError:
                latest_commit_dt = None

        is_unmaintained = (
            latest_commit_dt is not None and (now_utc - latest_commit_dt).days > 14
        )

        if repo_name_hint in repo_file_index:
            markdown_file, _ = repo_file_index[repo_name_hint]
        else:
            markdown_file = f"23.03.{next_number:03}_{repo_name}.md"
            repo_file_index[repo_name_hint] = (markdown_file, next_number)
            next_number += 1

        markdown_file_path = os.path.join(config.WORKING_DIRECTORY, markdown_file)
        if not os.access(os.path.dirname(markdown_file_path), os.W_OK):
            logger.error(f"No write permission for directory: {os.path.dirname(markdown_file_path)}")
            continue

        frontmatter, body = _read_note(markdown_file_path)
        previous_maintained = str(frontmatter.get("maintained", "true")).lower() != "false"

        readme_note_relative_path = frontmatter.get("readme_note") or _readme_relative_path(
            github_url,
            github_api.split_owner_repo(github_url)[0],
            repo_name,
        )
        readme_note_absolute_path = _readme_absolute_path(readme_note_relative_path)
        readme_exists = os.path.exists(readme_note_absolute_path)

        body, _, latest_row = _dedupe_overview_rows(body)

        if not body.strip():
            body = _build_header_block(
                repo_description,
                github_url,
                default_branch,
                readme_note_relative_path,
            )
        else:
            body = _ensure_readme_links(
                body,
                readme_note_relative_path,
                github_url,
                default_branch,
            )

        previous_readme_source_pushed_at = str(frontmatter.get("readme_source_pushed_at", ""))
        previous_readme_synced_at = str(frontmatter.get("readme_synced_at", ""))
        previous_readme_last_attempt_at = str(frontmatter.get("readme_last_attempt_at", ""))
        previous_readme_last_status = str(frontmatter.get("readme_last_status", ""))
        previous_readme_etag = str(frontmatter.get("readme_etag", ""))
        previous_readme_last_modified = str(frontmatter.get("readme_last_modified", ""))

        repo_identity = str(repo_data.get("full_name") or github_url)
        effective_repo_stale_days = _stale_days_with_repo_jitter(
            effective_readme_stale_days,
            repo_identity=repo_identity,
            jitter_span_days=effective_readme_stale_jitter_days,
        )
        readme_stale_window_counts[effective_repo_stale_days] = (
            readme_stale_window_counts.get(effective_repo_stale_days, 0) + 1
        )

        readme_sync_reason = _readme_sync_reason(
            effective_readme_sync_mode,
            readme_exists,
            previous_readme_source_pushed_at,
            latest_commit_date,
            readme_synced_at=previous_readme_synced_at,
            readme_last_attempt_at=previous_readme_last_attempt_at,
            stale_fallback_days=effective_repo_stale_days,
            now_utc=now_utc,
        )
        readme_sync_reason_counts[readme_sync_reason] = (
            readme_sync_reason_counts.get(readme_sync_reason, 0) + 1
        )

        should_sync_readme_by_policy = readme_sync_reason in {"always", "missing", "pushed", "stale"}
        if should_sync_readme_by_policy:
            readme_sync_due_count += 1

        retry_cooldown_remaining = _readme_retry_cooldown_remaining(
            previous_readme_last_status,
            previous_readme_last_attempt_at,
            now_utc,
        )
        retry_cooldown_active = should_sync_readme_by_policy and retry_cooldown_remaining is not None

        if should_sync_readme_by_policy:
            if retry_cooldown_active:
                readme_sync_skipped_cooldown_count += 1
            elif readme_updates_remaining <= 0:
                readme_sync_skipped_budget_count += 1

        should_sync_readme = (
            readme_updates_remaining > 0
            and should_sync_readme_by_policy
            and not retry_cooldown_active
        )

        if should_sync_readme_by_policy and retry_cooldown_active:
            remaining_hours = retry_cooldown_remaining.total_seconds() / 3600 if retry_cooldown_remaining else 0
            logger.info(
                "Skipping README sync for %s due cooldown: status=%s, remaining_hours=%.1f",
                github_url,
                previous_readme_last_status or "unknown",
                remaining_hours,
            )

        readme_sha256 = str(frontmatter.get("readme_sha256", ""))
        if should_sync_readme:
            readme_sync_attempted_count += 1
            readme_updates_remaining -= 1
            readme_attempt_at = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
            try:
                readme_result = github_api.fetch_readme_markdown_with_metadata(
                    github_url,
                    headers.copy(),
                    if_none_match=previous_readme_etag,
                    if_modified_since=previous_readme_last_modified,
                )
            except requests.exceptions.RequestException as exc:
                logger.warning("README fetch request error for %s: %s", github_url, exc)
                readme_result = github_api.ReadmeFetchResult(status="error", content=None)

            readme_sync_status_counts[readme_result.status] = (
                readme_sync_status_counts.get(readme_result.status, 0) + 1
            )

            frontmatter["readme_last_attempt_at"] = readme_attempt_at
            frontmatter["readme_last_status"] = readme_result.status

            if readme_result.etag:
                frontmatter["readme_etag"] = readme_result.etag
            if readme_result.last_modified:
                frontmatter["readme_last_modified"] = readme_result.last_modified

            if readme_result.status == "ok" and readme_result.content is not None:
                readme_sha256 = _hash_text(readme_result.content)
                _write_readme_snapshot(
                    readme_note_absolute_path,
                    markdown_file,
                    repo_data.get("full_name") or f"{github_api.split_owner_repo(github_url)[0]}/{repo_name}",
                    github_url,
                    default_branch,
                    readme_result.content,
                    readme_sha256,
                    latest_commit_date,
                )
                readme_exists = True
                frontmatter["readme_synced_at"] = readme_attempt_at

            elif readme_result.status == "not_modified":
                frontmatter["readme_synced_at"] = readme_attempt_at
                logger.info("README unchanged (304): %s", github_url)

            elif readme_result.status == "not_found":
                logger.info("README not found (404): %s", github_url)

            elif readme_result.status == "forbidden":
                logger.info("README fetch forbidden (403): %s", github_url)

            else:
                logger.info("README fetch did not update snapshot for %s (status=%s)", github_url, readme_result.status)

        if not readme_exists:
            placeholder_hash = "pending"
            _write_readme_snapshot(
                readme_note_absolute_path,
                markdown_file,
                repo_data.get("full_name") or f"{github_api.split_owner_repo(github_url)[0]}/{repo_name}",
                github_url,
                default_branch,
                None,
                placeholder_hash,
                latest_commit_date,
            )
            readme_sha256 = readme_sha256 or placeholder_hash

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        has_today_row = _has_row_for_date(body, today)

        metrics = _collect_latest_metrics(latest_row, repo_data)

        if has_today_row and skip_existing:
            logger.info(
                "Skipping metrics refresh for %s (already updated today): %s",
                github_url,
                markdown_file,
            )
        elif has_today_row:
            logger.info(
                "Skipping row for %s (already updated today): %s",
                github_url,
                markdown_file,
            )
        else:
            contributors = _fetch_contributors_count(contributors_url, headers) if contributors_url else "Error"
            latest_release = _fetch_latest_release(releases_url, headers) if releases_url else "No release found"

            row = {
                "date": today,
                "watchers": str(repo_data.get("subscribers_count", 0)),
                "forks": str(repo_data.get("forks_count", 0)),
                "stars": str(repo_data.get("stargazers_count", 0)),
                "contributors": str(contributors),
                "latest_release": str(latest_release),
            }

            body = _append_overview_row(body, row)
            body, _, latest_row = _dedupe_overview_rows(body)
            metrics = _collect_latest_metrics(latest_row, repo_data)

            logger.info(
                "Data has been added to %s for %s (%s/%s)",
                markdown_file,
                repo_name,
                i,
                len(urls),
            )

        frontmatter = _upsert_frontmatter(
            frontmatter=frontmatter,
            repo_data=repo_data,
            github_url=github_url,
            repo_description=repo_description,
            maintained=not is_unmaintained,
            readme_note_relative_path=readme_note_relative_path,
            readme_sha256=readme_sha256,
            readme_source_pushed_at=latest_commit_date,
            metrics=metrics,
            today=today,
        )

        if previous_maintained and is_unmaintained:
            newly_unmaintained.append(markdown_file)

        _write_note(markdown_file_path, frontmatter, body)
        processed += 1

    evaluated_repos = sum(readme_sync_reason_counts.values())
    reason_summary = ", ".join(
        f"{key}={value}" for key, value in sorted(readme_sync_reason_counts.items())
    ) or "none"
    status_summary = ", ".join(
        f"{key}={value}" for key, value in sorted(readme_sync_status_counts.items())
    ) or "none"

    logger.info(
        "README sync summary: evaluated=%s, due=%s, attempted=%s, skipped_budget=%s, skipped_cooldown=%s, statuses=[%s], reasons=[%s]",
        evaluated_repos,
        readme_sync_due_count,
        readme_sync_attempted_count,
        readme_sync_skipped_budget_count,
        readme_sync_skipped_cooldown_count,
        status_summary,
        reason_summary,
    )

    if effective_readme_sync_mode == "if-pushed" and readme_stale_window_counts:
        stale_window_summary = ", ".join(
            f"{days}d={count}"
            for days, count in sorted(readme_stale_window_counts.items())
        )
        logger.info("README stale window distribution (days->repos): %s", stale_window_summary)

    return newly_unmaintained
