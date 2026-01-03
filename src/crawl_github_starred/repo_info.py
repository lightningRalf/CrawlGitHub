import os
import re
import datetime
import logging

from . import config
from . import github_api

logger = logging.getLogger(__name__)


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---\n", 4)
    if end == -1:
        return {}, content
    frontmatter_block = content[4:end].splitlines()
    frontmatter: dict[str, str] = {}
    for line in frontmatter_block:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip()
    body = content[end + 5 :]
    return frontmatter, body


def _render_frontmatter(frontmatter: dict[str, str]) -> str:
    if not frontmatter:
        return ""
    lines = ["---"]
    if "type" in frontmatter:
        lines.append(f"type: {frontmatter['type']}")
    if "maintained" in frontmatter:
        lines.append(f"maintained: {frontmatter['maintained']}")
    for key, value in frontmatter.items():
        if key in {"type", "maintained"}:
            continue
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _ensure_frontmatter(frontmatter: dict[str, str], maintained: bool) -> dict[str, str]:
    updated = dict(frontmatter)
    updated["type"] = updated.get("type", "checkbox")
    updated["maintained"] = "true" if maintained else "false"
    return updated


def _read_note(markdown_file_path: str) -> tuple[dict[str, str], str]:
    if not os.path.exists(markdown_file_path) or os.stat(markdown_file_path).st_size == 0:
        return {}, ""
    with open(markdown_file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return _parse_frontmatter(content)


def _write_note(markdown_file_path: str, frontmatter: dict[str, str], body: str) -> None:
    content = _render_frontmatter(frontmatter) + body.lstrip("\n")
    with open(markdown_file_path, "w", encoding="utf-8") as f:
        f.write(content)


def _insert_table_row(body: str, row: str) -> str:
    lines = body.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()

    insert_index = len(lines)
    for i, line in enumerate(lines):
        if line.startswith("| Date") and i + 1 < len(lines) and lines[i + 1].startswith("|---"):
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            insert_index = j
            break

    lines.insert(insert_index, row.rstrip("\n"))
    return "\n".join(lines) + "\n"


def _get_latest_commit_date(repo_data: dict) -> datetime.datetime | None:
    commit_date = repo_data.get("pushed_at") or repo_data.get("updated_at")
    if not commit_date:
        return None
    return datetime.datetime.fromisoformat(commit_date.replace("Z", "+00:00"))


def _has_row_for_date(body: str, date_str: str) -> bool:
    for line in body.splitlines():
        if line.startswith(f"| {date_str} |"):
            return True
    return False


def _build_header_block(repo_description: str, github_url: str, default_branch: str) -> str:
    return (
        f"## [{repo_description}]({github_url})\n"
        f"\n## README\n\n"
        f"{config.README_TEMPLATE.format(github_api.get_readme_url(github_url, default_branch))}"
        f"\n## Overview\n\n"
        "| Date       | Watchers | Forks | Stars | Contributors | Latest Release |\n"
        "|------------|----------|-------|-------|--------------|----------------|\n"
    )


def _resolve_markdown_file(repo_name: str) -> str:
    existing_files = [
        file
        for file in os.listdir(config.WORKING_DIRECTORY)
        if re.search(rf"23.03\.\d+_{repo_name}\.md", file)
    ]
    if existing_files:
        return existing_files[0]
    existing_numbers = [
        int(re.search(r"23.03\.(\d+)_", file).group(1))
        for file in os.listdir(config.WORKING_DIRECTORY)
        if re.search(r"23.03\.\d+_", file)
    ]
    next_number = max(existing_numbers, default=1) + 1
    return f"23.03.{next_number:03}_{repo_name}.md"


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
    return len(contributors_response.json()) if contributors_response else "Error"


def _fetch_latest_release(releases_url: str, headers: dict) -> str:
    releases_response = github_api.fetch_github_data(releases_url, headers.copy())
    if releases_response and releases_response.json():
        return releases_response.json()[0]["tag_name"]
    return "No release found"


def generate_repo_info(
    urls: list[str],
    skip_existing: bool = False,
    max_repos: int | None = None,
    resume_from: int | None = None,
) -> list[str]:
    """Generates repository information and saves/appends to markdown files."""
    headers = github_api.get_github_headers()
    
    logger.info(f"Processing {len(urls)} repositories")
    newly_unmaintained: list[str] = []
    repo_file_index, max_number = _index_repo_files()
    next_number = max_number + 1
    processed = 0
    
    for i, github_url in enumerate(urls, start=2):  # Start from 1 for more natural indexing
        if max_repos is not None and processed >= max_repos:
            break
        logger.info(f"Processing repository {i}/{len(urls)}: {github_url}")
        repo_name_hint = github_url.rstrip("/").split("/")[-1].lower()
        if resume_from is not None and repo_name_hint in repo_file_index:
            _, markdown_number = repo_file_index[repo_name_hint]
            if markdown_number < resume_from:
                logger.info(
                    f"Skipping {github_url} (file number {markdown_number} < resume-from {resume_from})"
                )
                continue
        api_url = github_url.replace("https://github.com", "https://api.github.com/repos")
        response = github_api.fetch_github_data(api_url, headers.copy())  # Fetch repo data

        if not response:
            logger.warning(f"Failed to get data for {github_url}, skipping")
            continue

        repo_data = response.json()

        # Extract information
        repo_name = repo_data["name"]
        repo_description = repo_data["description"] or "No description found"
        stars = repo_data["stargazers_count"]
        watching = repo_data["subscribers_count"]
        forks = repo_data["forks_count"]
        default_branch = repo_data["default_branch"]
        contributors_url = repo_data["contributors_url"]
        releases_url = repo_data["releases_url"].replace("{/id}", "")
        latest_commit_date = _get_latest_commit_date(repo_data)
        now = datetime.datetime.now(datetime.timezone.utc)
        is_unmaintained = (
            latest_commit_date is not None
            and (now - latest_commit_date).days > 14
        )

        # Find existing markdown file or create a new one
        if repo_name_hint in repo_file_index:
            markdown_file, _ = repo_file_index[repo_name_hint]
        else:
            markdown_file = f"23.03.{next_number:03}_{repo_name}.md"
            repo_file_index[repo_name_hint] = (markdown_file, next_number)
            next_number += 1
        markdown_file_path = os.path.join(config.WORKING_DIRECTORY, markdown_file)

        # Add check to see if the file path is writable
        if not os.access(os.path.dirname(markdown_file_path), os.W_OK):
            logger.error(f"No write permission for directory: {os.path.dirname(markdown_file_path)}")
            continue
            
        logger.info(f"Writing to file: {markdown_file_path}")

        today = datetime.datetime.now().strftime("%Y-%m-%d")
        has_today_row = False
        frontmatter, body = _read_note(markdown_file_path)
        previous_maintained = frontmatter.get("maintained", "true").lower() != "false"
        has_today_row = _has_row_for_date(body, today)
        frontmatter = _ensure_frontmatter(frontmatter, not is_unmaintained)
        if not body.strip():
            body = _build_header_block(repo_description, github_url, default_branch)
        _write_note(markdown_file_path, frontmatter, body)

        if previous_maintained and is_unmaintained:
            newly_unmaintained.append(markdown_file)
        if has_today_row:
            logger.info(
                f"Skipping row for {github_url} (already updated today): {markdown_file}"
            )
            continue

        contributors = _fetch_contributors_count(contributors_url, headers)
        latest_release = _fetch_latest_release(releases_url, headers)
        row = (
            f"| {datetime.datetime.now().strftime('%Y-%m-%d')} | {watching} | {forks}  | {stars} | {contributors} | {latest_release} |\n"
        )
        body = _insert_table_row(body, row)
        _write_note(markdown_file_path, frontmatter, body)
        logger.info(f"Data has been added to {markdown_file} for {repo_name} ({i}/{len(urls)})")
        processed += 1
    return newly_unmaintained
