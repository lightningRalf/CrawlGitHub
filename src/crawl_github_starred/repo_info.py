from __future__ import annotations

import datetime
import hashlib
import logging
import os
import re
from typing import Any

from . import config
from . import github_api

logger = logging.getLogger(__name__)


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


def _should_sync_readme(
    mode: str,
    readme_exists: bool,
    previous_source_pushed_at: str,
    current_source_pushed_at: str,
) -> bool:
    mode = mode.lower()
    if mode == "off":
        return False
    if mode == "always":
        return True
    if mode == "new":
        return not readme_exists
    if mode == "if-pushed":
        if not readme_exists:
            return True
        if not current_source_pushed_at:
            return False
        return previous_source_pushed_at != current_source_pushed_at
    return False


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

    if "review_status" not in updated or not str(updated["review_status"]).strip():
        updated["review_status"] = "inbox"
    if "why_starred" not in updated:
        updated["why_starred"] = ""
    if "next_action" not in updated:
        updated["next_action"] = ""

    return updated


def generate_repo_info(
    urls: list[str],
    skip_existing: bool = False,
    max_repos: int | None = None,
    resume_from: int | None = None,
    readme_sync_mode: str | None = None,
    max_readme_updates: int | None = None,
) -> list[str]:
    """Generate repository information and update markdown notes."""
    headers = github_api.get_github_headers()

    effective_readme_sync_mode = (readme_sync_mode or config.README_SYNC_MODE).lower()
    if effective_readme_sync_mode not in config.README_SYNC_MODES:
        effective_readme_sync_mode = config.README_SYNC_MODE

    readme_updates_remaining = (
        config.MAX_README_UPDATES_PER_RUN if max_readme_updates is None else max(0, max_readme_updates)
    )

    logger.info(f"Processing {len(urls)} repositories")
    logger.info(
        "README sync: mode=%s, max_updates=%s",
        effective_readme_sync_mode,
        readme_updates_remaining,
    )

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
        should_sync_readme = (
            readme_updates_remaining > 0
            and _should_sync_readme(
                effective_readme_sync_mode,
                readme_exists,
                previous_readme_source_pushed_at,
                latest_commit_date,
            )
        )

        readme_sha256 = str(frontmatter.get("readme_sha256", ""))
        if should_sync_readme:
            readme_updates_remaining -= 1
            readme_content = github_api.fetch_readme_markdown(github_url, headers.copy())
            if readme_content is not None:
                readme_sha256 = _hash_text(readme_content)
                _write_readme_snapshot(
                    readme_note_absolute_path,
                    markdown_file,
                    repo_data.get("full_name") or f"{github_api.split_owner_repo(github_url)[0]}/{repo_name}",
                    github_url,
                    default_branch,
                    readme_content,
                    readme_sha256,
                    latest_commit_date,
                )
                readme_exists = True
                frontmatter["readme_synced_at"] = now_utc.replace(microsecond=0).isoformat()
            else:
                logger.info(f"No README content returned for {github_url}")

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

    return newly_unmaintained
