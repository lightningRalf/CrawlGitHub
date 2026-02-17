from __future__ import annotations

import datetime
import json
import os
import re
from typing import Any

from .. import config

REPO_NOTE_PATTERN = re.compile(r"^23\.03\.\d+_.+\.md$")
REPO_HEADER_PATTERN = re.compile(r"^## \[(.+?)\]\((https://github\.com/[^)]+)\)", re.MULTILINE)
README_LOCAL_LINK_PATTERN = re.compile(r"Lokal\s*\(durchsuchbar\):\s*\[\[([^\]]+)\]\]")


def _utc_now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    normalized = content.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized

    end = normalized.find("\n---\n", 4)
    if end == -1:
        return {}, normalized

    frontmatter: dict[str, str] = {}
    for line in normalized[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = _strip_quotes(value.strip())

    body = normalized[end + 5 :]
    return frontmatter, body


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


def _render_frontmatter(frontmatter: dict[str, Any], key_order: list[str] | None = None) -> str:
    if not frontmatter:
        return ""

    ordered: list[str] = []
    if key_order:
        for key in key_order:
            if key in frontmatter:
                ordered.append(key)

    for key in frontmatter:
        if key not in ordered:
            ordered.append(key)

    lines = ["---"]
    for key in ordered:
        lines.append(f"{key}: {_yaml_scalar(frontmatter[key])}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _write_text_if_changed(path: str, content: str) -> bool:
    existing = ""
    if os.path.exists(path):
        existing = _read_text(path)
        if existing == content:
            return False

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return True


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _is_truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalize_watch_seed_id(value: Any) -> str:
    return str(value or "").strip().lower()


def _is_repo_note_file(filename: str) -> bool:
    if filename == config.STARRED_REPOS_FILE:
        return False
    return REPO_NOTE_PATTERN.match(filename) is not None


def _iter_repo_note_paths() -> list[str]:
    if not os.path.isdir(config.WORKING_DIRECTORY):
        return []

    paths: list[str] = []
    for filename in sorted(os.listdir(config.WORKING_DIRECTORY)):
        if not _is_repo_note_file(filename):
            continue
        paths.append(os.path.join(config.WORKING_DIRECTORY, filename))
    return paths


def _read_readme_text(readme_relative_path: str) -> str:
    if not readme_relative_path:
        return ""

    readme_path = os.path.join(config.WORKING_DIRECTORY, readme_relative_path)
    if not os.path.exists(readme_path):
        return ""

    try:
        content = _read_text(readme_path)
    except OSError:
        return ""

    _, body = _parse_frontmatter(content)
    return body


def _guess_repo_from_url(repo_url: str) -> str:
    cleaned = repo_url.rstrip("/")
    parts = cleaned.split("/")
    if len(parts) < 5:
        return ""
    return f"{parts[-2]}/{parts[-1]}"


def _infer_repo_header(body: str) -> tuple[str | None, str | None]:
    match = REPO_HEADER_PATTERN.search(body)
    if not match:
        return None, None
    description = match.group(1).strip()
    repo_url = match.group(2).strip()
    return description or None, repo_url or None


def _infer_readme_note_path(body: str) -> str:
    match = README_LOCAL_LINK_PATTERN.search(body)
    if not match:
        return ""
    return match.group(1).strip()


def _write_jsonl(path: str, rows: list[dict[str, Any]]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
