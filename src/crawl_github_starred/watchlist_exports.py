from __future__ import annotations

import datetime
import hashlib
import json
import logging
import os
import re
import time
from typing import Any
from urllib.parse import quote

import requests

from . import config
from .watch.signals import (
    PI_MARKER_TO_TAG,
    _append_unique,
    _candidate_reason_fragments,
    _candidate_signal_sources,
    _classify_repo_candidate,
    _confidence_counts,
    _contains_term,
    _normalize_reason_fragments,
    _populate_signal_metadata,
    _signal_source_counts,
    _signal_sources_from_reasons,
    _watch_confidence,
)

logger = logging.getLogger(__name__)

REPO_NOTE_PATTERN = re.compile(r"^23\.03\.\d+_.+\.md$")
REPO_HEADER_PATTERN = re.compile(r"^## \[(.+?)\]\((https://github\.com/[^)]+)\)", re.MULTILINE)
README_LOCAL_LINK_PATTERN = re.compile(r"Lokal\s*\(durchsuchbar\):\s*\[\[([^\]]+)\]\]")
PACKAGE_NAME_PATTERN = re.compile(
    r"^@?[a-z0-9][a-z0-9._-]*(?:/[a-z0-9][a-z0-9._-]*)?$",
    re.IGNORECASE,
)

INSTALL_COMMAND_PATTERN = re.compile(
    r"\b(?:npm\s+(?:install|i)|pnpm\s+add|yarn\s+add|bun\s+add)\s+([^\n\r`]+)",
    re.IGNORECASE,
)
PACKAGE_JSON_NAME_PATTERN = re.compile(
    r'"name"\s*:\s*"(@?[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?)"'
)

WATCH_NOTE_FRONTMATTER_ORDER = [
    "type",
    "source",
    "watch_candidate",
    "watch_type",
    "watch_seed_id",
    "watch_status",
    "watch_owner",
    "watch_tags",
    "watch_signal_sources",
    "watch_signal_count",
    "watch_confidence",
    "watch_why",
    "watch_discovered_at",
    "watch_updated_at",
    "watch_reactivated_at",
    "watch_archived_at",
    "title",
    "repo",
    "repo_url",
    "package",
    "from_repos",
    "from_repo_ids",
]


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


def _normalize_discovered_at(frontmatter: dict[str, str], fallback_iso: str) -> str:
    last_seen = str(frontmatter.get("last_seen_date") or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_seen):
        return f"{last_seen}T00:00:00Z"
    return fallback_iso


def _format_repo_id(repo_name: str, repo_url: str, note_stem: str) -> str:
    if repo_name:
        return f"github:{repo_name.lower()}"

    guessed = _guess_repo_from_url(repo_url)
    if guessed:
        return f"github:{guessed.lower()}"

    return f"github:{note_stem.lower()}"


def _as_repo_candidate(
    note_path: str,
    frontmatter: dict[str, str],
    tags: list[str],
    reasons: list[str],
    fallback_discovered_at: str,
) -> dict[str, Any]:
    note_filename = os.path.basename(note_path)
    note_stem = os.path.splitext(note_filename)[0]

    repo_url = str(frontmatter.get("repo_url") or "").strip()
    repo_name = str(frontmatter.get("repo") or "").strip() or _guess_repo_from_url(repo_url)
    title = repo_name or str(frontmatter.get("repo_name") or "").strip() or note_stem

    normalized_reasons = _normalize_reason_fragments(reasons)
    payload: dict[str, Any] = {
        "id": _format_repo_id(repo_name, repo_url, note_stem),
        "type": "repo",
        "source": "github-starred",
        "title": title,
        "starred": True,
        "tags": sorted({*tags, "source/github-starred"}),
        "whyWatch": "; ".join(normalized_reasons) if normalized_reasons else "pi-related repository signal",
        "signalReasons": normalized_reasons,
        "status": "new",
        "owner": "you",
        "discoveredAt": _normalize_discovered_at(frontmatter, fallback_discovered_at),
    }

    if repo_name:
        payload["repo"] = repo_name
    if repo_url:
        payload["repoUrl"] = repo_url

    payload["repoNote"] = note_stem
    _populate_signal_metadata(payload)
    return payload


def _merge_repo_candidate(store: dict[str, dict[str, Any]], candidate: dict[str, Any]) -> None:
    candidate_id = str(candidate["id"])
    existing = store.get(candidate_id)
    if existing is None:
        _populate_signal_metadata(candidate)
        store[candidate_id] = candidate
        return

    existing_tags = set(existing.get("tags", []))
    existing_tags.update(candidate.get("tags", []))
    existing["tags"] = sorted(existing_tags)

    merged_reasons = _candidate_reason_fragments(existing)
    for reason in _candidate_reason_fragments(candidate):
        _append_unique(merged_reasons, reason)
    existing["signalReasons"] = merged_reasons

    merged_sources = _candidate_signal_sources(existing, merged_reasons)
    for source in _candidate_signal_sources(candidate, _candidate_reason_fragments(candidate)):
        _append_unique(merged_sources, source)
    existing["signalSources"] = merged_sources

    existing["confidence"] = ""
    _populate_signal_metadata(existing)


def _normalize_package_token(token: str) -> str | None:
    cleaned = token.strip().strip('"\'`').strip("()[]{}")
    cleaned = cleaned.rstrip(",;")
    if not cleaned:
        return None

    if cleaned.startswith("npm:"):
        cleaned = cleaned[4:]

    if cleaned.startswith("-"):
        return None
    if cleaned.startswith(("http://", "https://", "./", "../", "/")):
        return None

    if cleaned.startswith("@"):
        at_pos = cleaned.rfind("@")
        slash_pos = cleaned.find("/")
        if at_pos > slash_pos >= 0:
            cleaned = cleaned[:at_pos]
    elif "@" in cleaned:
        cleaned = cleaned.split("@", 1)[0]

    if not PACKAGE_NAME_PATTERN.fullmatch(cleaned):
        return None

    return cleaned


def _extract_npm_packages(readme_text: str, repo_name: str) -> list[str]:
    packages: list[str] = []

    for match in INSTALL_COMMAND_PATTERN.finditer(readme_text):
        segment = match.group(1)
        segment = re.split(r"[;#|]", segment, maxsplit=1)[0]
        for raw_token in re.split(r"\s+", segment.strip()):
            package_name = _normalize_package_token(raw_token)
            if package_name:
                _append_unique(packages, package_name)

    for match in PACKAGE_JSON_NAME_PATTERN.finditer(readme_text):
        package_name = _normalize_package_token(match.group(1))
        if package_name:
            _append_unique(packages, package_name)

    if repo_name:
        candidate = _normalize_package_token(repo_name)
        if candidate:
            _append_unique(packages, candidate)

    return packages


def _is_pi_relevant_package(package_name: str) -> bool:
    lowered = package_name.lower()
    if lowered.startswith("@badlogic/"):
        return True
    if re.search(r"(?:^|[-_/])pi(?:[-_/]|$)", lowered):
        return True
    if "pi-coding-agent" in lowered:
        return True
    return False


def _as_npm_candidate(
    package_name: str,
    repo_candidate: dict[str, Any],
    fallback_discovered_at: str,
) -> dict[str, Any]:
    repo_title = str(repo_candidate.get("title", "repo"))
    repo_id = str(repo_candidate.get("id", ""))
    base_tags = [tag for tag in repo_candidate.get("tags", []) if tag != "source/github-starred"]

    reason_fragment = f"derived-from:{repo_title}"
    payload: dict[str, Any] = {
        "id": f"npm:{package_name.lower()}",
        "type": "npm",
        "source": "npm",
        "title": package_name,
        "starred": False,
        "tags": sorted({*base_tags, "source/npm"}),
        "whyWatch": reason_fragment,
        "signalReasons": [reason_fragment],
        "status": "new",
        "owner": "you",
        "discoveredAt": fallback_discovered_at,
        "package": package_name,
        "fromRepos": [repo_title],
    }

    repo_url = str(repo_candidate.get("repoUrl", "")).strip()
    if repo_url:
        payload["repoUrl"] = repo_url

    if repo_id:
        payload["fromRepoIds"] = [repo_id]

    _populate_signal_metadata(payload)
    return payload


def _merge_npm_candidate(store: dict[str, dict[str, Any]], candidate: dict[str, Any]) -> None:
    candidate_id = str(candidate["id"])
    existing = store.get(candidate_id)
    if existing is None:
        _populate_signal_metadata(candidate)
        store[candidate_id] = candidate
        return

    existing_tags = set(existing.get("tags", []))
    existing_tags.update(candidate.get("tags", []))
    existing["tags"] = sorted(existing_tags)

    from_repos = list(existing.get("fromRepos", []))
    for repo in candidate.get("fromRepos", []):
        if repo not in from_repos:
            from_repos.append(repo)
    existing["fromRepos"] = from_repos

    from_repo_ids = list(existing.get("fromRepoIds", []))
    for repo_id in candidate.get("fromRepoIds", []):
        if repo_id not in from_repo_ids:
            from_repo_ids.append(repo_id)
    if from_repo_ids:
        existing["fromRepoIds"] = from_repo_ids

    merged_reasons = _candidate_reason_fragments(existing)
    for reason in _candidate_reason_fragments(candidate):
        _append_unique(merged_reasons, reason)

    for repo in candidate.get("fromRepos", []):
        fragment = f"derived-from:{repo}"
        _append_unique(merged_reasons, fragment)

    existing["signalReasons"] = merged_reasons

    merged_sources = _candidate_signal_sources(existing, merged_reasons)
    for source in _candidate_signal_sources(candidate, _candidate_reason_fragments(candidate)):
        _append_unique(merged_sources, source)
    existing["signalSources"] = merged_sources

    existing["confidence"] = ""
    _populate_signal_metadata(existing)


def _extract_npm_keywords(payload: dict[str, Any], latest_version_payload: dict[str, Any]) -> list[str]:
    raw_keywords: Any = latest_version_payload.get("keywords")
    if not raw_keywords:
        raw_keywords = payload.get("keywords")

    if isinstance(raw_keywords, str):
        raw_keywords = [raw_keywords]

    keywords: list[str] = []
    if isinstance(raw_keywords, list):
        for item in raw_keywords:
            value = str(item).strip().lower()
            if value:
                _append_unique(keywords, value)

    return keywords


def _apply_npm_metadata(candidate: dict[str, Any], payload: dict[str, Any]) -> None:
    dist_tags = payload.get("dist-tags", {})
    latest_version = ""
    if isinstance(dist_tags, dict):
        latest_version = str(dist_tags.get("latest") or "").strip()

    versions_payload = payload.get("versions", {})
    latest_version_payload: dict[str, Any] = {}
    if latest_version and isinstance(versions_payload, dict):
        maybe_payload = versions_payload.get(latest_version)
        if isinstance(maybe_payload, dict):
            latest_version_payload = maybe_payload

    npm_description = (
        str(latest_version_payload.get("description") or "").strip()
        or str(payload.get("description") or "").strip()
    )

    if latest_version:
        candidate["npmLatestVersion"] = latest_version
    if npm_description:
        candidate["npmDescription"] = npm_description

    keywords = _extract_npm_keywords(payload, latest_version_payload)
    if keywords:
        candidate["npmKeywords"] = keywords

    tags = set(candidate.get("tags", []))
    reason_fragments = _candidate_reason_fragments(candidate)

    for keyword in keywords:
        tag = PI_MARKER_TO_TAG.get(keyword)
        if not tag:
            continue

        tags.add(tag)
        fragment = f"npm-keyword:{keyword}"
        _append_unique(reason_fragments, fragment)

    candidate["tags"] = sorted(tags)
    candidate["signalReasons"] = reason_fragments
    candidate["confidence"] = ""
    _populate_signal_metadata(candidate)


def _enrich_npm_candidates(candidates: list[dict[str, Any]], max_npm_lookups: int) -> int:
    if max_npm_lookups <= 0:
        return 0

    lookups_done = 0
    for candidate in candidates:
        if lookups_done >= max_npm_lookups:
            break

        package_name = str(candidate.get("package") or candidate.get("title") or "").strip()
        if not package_name:
            continue

        registry_url = f"https://registry.npmjs.org/{quote(package_name, safe='@/')}"

        try:
            response = requests.get(registry_url, timeout=15)
        except requests.RequestException as exc:
            logger.warning("npm lookup failed for %s: %s", package_name, exc)
            continue

        lookups_done += 1

        if response.status_code == 200:
            try:
                payload = response.json()
            except ValueError:
                logger.warning("npm lookup returned invalid JSON for %s", package_name)
                payload = {}

            if isinstance(payload, dict):
                _apply_npm_metadata(candidate, payload)

        elif response.status_code == 404:
            logger.info("npm package not found: %s", package_name)

        elif response.status_code == 429:
            logger.warning("npm rate limit hit while resolving %s", package_name)
            break

        else:
            logger.warning(
                "npm lookup for %s failed with status %s",
                package_name,
                response.status_code,
            )

        if lookups_done < max_npm_lookups and config.REQUEST_DELAY_SECONDS > 0:
            time.sleep(config.REQUEST_DELAY_SECONDS)

    return lookups_done


def _write_jsonl(path: str, rows: list[dict[str, Any]]) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _collect_watch_seed_candidates(max_npm_lookups: int = 0) -> dict[str, Any]:
    fallback_discovered_at = _utc_now_iso()

    repo_candidates_by_id: dict[str, dict[str, Any]] = {}
    npm_candidates_by_id: dict[str, dict[str, Any]] = {}

    scanned_notes = 0
    pi_candidates = 0

    for note_path in _iter_repo_note_paths():
        scanned_notes += 1

        try:
            note_content = _read_text(note_path)
        except OSError:
            logger.warning("Failed to read repo note: %s", note_path)
            continue

        frontmatter, body = _parse_frontmatter(note_content)

        header_description, header_repo_url = _infer_repo_header(body)

        repo_url = str(frontmatter.get("repo_url") or "").strip() or str(header_repo_url or "").strip()
        if not repo_url.startswith("https://github.com/"):
            continue
        frontmatter["repo_url"] = repo_url

        if "repo" not in frontmatter or not str(frontmatter.get("repo") or "").strip():
            guessed_repo = _guess_repo_from_url(repo_url)
            if guessed_repo:
                frontmatter["repo"] = guessed_repo

        if "repo_name" not in frontmatter or not str(frontmatter.get("repo_name") or "").strip():
            guessed_repo = str(frontmatter.get("repo") or "")
            repo_name = guessed_repo.split("/")[-1] if "/" in guessed_repo else guessed_repo
            if repo_name:
                frontmatter["repo_name"] = repo_name

        if "repo_description" not in frontmatter or not str(frontmatter.get("repo_description") or "").strip():
            if header_description:
                frontmatter["repo_description"] = header_description

        readme_relative_path = (
            str(frontmatter.get("readme_note") or "").strip()
            or _infer_readme_note_path(body)
        )
        readme_text = _read_readme_text(readme_relative_path)

        tags, reasons = _classify_repo_candidate(frontmatter, body, readme_text)
        if not tags:
            continue

        pi_candidates += 1

        repo_candidate = _as_repo_candidate(
            note_path=note_path,
            frontmatter=frontmatter,
            tags=tags,
            reasons=reasons,
            fallback_discovered_at=fallback_discovered_at,
        )
        _merge_repo_candidate(repo_candidates_by_id, repo_candidate)

        repo_name = str(frontmatter.get("repo_name") or "").strip()
        package_names = _extract_npm_packages(readme_text, repo_name)

        for package_name in package_names:
            if not _is_pi_relevant_package(package_name):
                continue

            npm_candidate = _as_npm_candidate(
                package_name=package_name,
                repo_candidate=repo_candidate,
                fallback_discovered_at=fallback_discovered_at,
            )
            _merge_npm_candidate(npm_candidates_by_id, npm_candidate)

    repo_candidates = sorted(repo_candidates_by_id.values(), key=lambda item: str(item.get("id", "")))
    npm_candidates = sorted(npm_candidates_by_id.values(), key=lambda item: str(item.get("id", "")))

    npm_lookups_done = _enrich_npm_candidates(npm_candidates, max(0, max_npm_lookups))

    return {
        "scanned_notes": scanned_notes,
        "pi_candidates": pi_candidates,
        "repo_candidates": repo_candidates,
        "npm_candidates": npm_candidates,
        "npm_lookups": npm_lookups_done,
    }


def _sanitize_filename(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "-", str(value or "").strip())
    sanitized = re.sub(r"-+", "-", sanitized).strip("-")
    return sanitized or "candidate"


def _repo_note_path_from_candidate(candidate: dict[str, Any]) -> str:
    note_stem = str(candidate.get("repoNote") or "").strip()
    if not note_stem:
        return ""
    return os.path.join(config.WORKING_DIRECTORY, f"{note_stem}.md")


def _npm_candidate_relative_path(candidate: dict[str, Any]) -> str:
    candidate_id = str(candidate.get("id") or candidate.get("package") or candidate.get("title") or "npm:unknown")
    digest = hashlib.sha256(candidate_id.lower().encode("utf-8")).hexdigest()[:12]
    package_name = str(candidate.get("package") or candidate.get("title") or "npm-candidate")
    filename = f"npm__{_sanitize_filename(package_name)}__{digest}.md"
    return os.path.join(config.WATCH_CANDIDATES_SUBDIR, filename).replace("\\", "/")


def _iter_watch_candidate_npm_note_paths() -> list[str]:
    watch_dir = os.path.join(config.WORKING_DIRECTORY, config.WATCH_CANDIDATES_SUBDIR)
    if not os.path.isdir(watch_dir):
        return []

    paths: list[str] = []
    for filename in sorted(os.listdir(watch_dir)):
        if not filename.lower().endswith(".md"):
            continue
        paths.append(os.path.join(watch_dir, filename))

    return paths


def _as_joined_csv(values: Any) -> str:
    if not isinstance(values, list):
        return ""
    cleaned = [str(value).strip() for value in values if str(value).strip()]
    return ", ".join(cleaned)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _upsert_repo_candidate_note(candidate: dict[str, Any], now_iso: str) -> tuple[bool, bool, bool]:
    note_path = _repo_note_path_from_candidate(candidate)
    if not note_path:
        return False, True, False

    if not os.path.exists(note_path):
        logger.warning("Repo candidate note not found: %s", note_path)
        return False, True, False

    try:
        content = _read_text(note_path)
    except OSError:
        logger.warning("Failed to read repo candidate note: %s", note_path)
        return False, True, False

    frontmatter, body = _parse_frontmatter(content)
    updated = dict(frontmatter)

    signal_reasons = _candidate_reason_fragments(candidate)
    signal_sources = _candidate_signal_sources(candidate, signal_reasons)
    reason_text = "; ".join(signal_reasons) if signal_reasons else str(candidate.get("whyWatch") or "")
    candidate_tags = [str(tag).strip() for tag in candidate.get("tags", []) if str(tag).strip()]

    confidence = str(candidate.get("confidence") or "").strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = _watch_confidence(candidate_tags, signal_reasons)

    signal_count = _as_int(candidate.get("signalCount"), len(signal_reasons))

    updated["watch_candidate"] = "true"
    updated["watch_type"] = "repo"
    updated["watch_seed_id"] = str(candidate.get("id") or "")
    updated["watch_tags"] = _as_joined_csv(candidate.get("tags"))
    updated["watch_signal_sources"] = _as_joined_csv(signal_sources)
    updated["watch_signal_count"] = signal_count
    updated["watch_confidence"] = confidence
    updated["watch_why"] = reason_text
    updated["watch_discovered_at"] = str(candidate.get("discoveredAt") or now_iso)
    updated["watch_updated_at"] = now_iso

    was_archived = str(frontmatter.get("watch_status") or "").strip().lower() == "archived"
    if was_archived:
        updated["watch_status"] = "new"
        updated["watch_reactivated_at"] = now_iso
        if "watch_archived_at" in updated:
            updated["watch_archived_at"] = ""
    elif not str(updated.get("watch_status") or "").strip():
        updated["watch_status"] = "new"

    if not str(updated.get("watch_owner") or "").strip():
        updated["watch_owner"] = str(candidate.get("owner") or "you")

    rewritten = _render_frontmatter(updated) + body.lstrip("\n")
    changed = _write_text_if_changed(note_path, rewritten)
    return changed, False, was_archived and changed


def _default_npm_candidate_body(candidate: dict[str, Any], note_stem: str) -> str:
    title = str(candidate.get("title") or candidate.get("package") or note_stem)
    package_name = str(candidate.get("package") or title)
    why_watch = str(candidate.get("whyWatch") or "")
    tags_csv = _as_joined_csv(candidate.get("tags"))
    repo_url = str(candidate.get("repoUrl") or "").strip()
    from_repos = candidate.get("fromRepos") if isinstance(candidate.get("fromRepos"), list) else []

    lines = [
        f"# Watch candidate — {title}",
        "",
        f"- Package: `{package_name}`",
        f"- Why watch: {why_watch or '-'}",
        f"- Tags: {tags_csv or '-'}",
    ]

    if repo_url:
        lines.append(f"- Related repo: {repo_url}")

    if from_repos:
        lines.append("- Derived from repos:")
        for repo in from_repos:
            lines.append(f"  - {repo}")

    lines.append("")
    return "\n".join(lines)


def _upsert_npm_candidate_note(candidate: dict[str, Any], now_iso: str) -> tuple[bool, bool, bool]:
    relative_path = _npm_candidate_relative_path(candidate)
    absolute_path = os.path.join(config.WORKING_DIRECTORY, relative_path)
    existed_before = os.path.exists(absolute_path)

    existing_content = ""
    if existed_before:
        try:
            existing_content = _read_text(absolute_path)
        except OSError:
            logger.warning("Failed to read npm candidate note: %s", absolute_path)
            existing_content = ""

    frontmatter, body = _parse_frontmatter(existing_content) if existing_content else ({}, "")
    updated = dict(frontmatter)

    title = str(candidate.get("title") or candidate.get("package") or "npm-candidate")
    package_name = str(candidate.get("package") or title)

    signal_reasons = _candidate_reason_fragments(candidate)
    signal_sources = _candidate_signal_sources(candidate, signal_reasons)
    reason_text = "; ".join(signal_reasons) if signal_reasons else str(candidate.get("whyWatch") or "")
    candidate_tags = [str(tag).strip() for tag in candidate.get("tags", []) if str(tag).strip()]

    confidence = str(candidate.get("confidence") or "").strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = _watch_confidence(candidate_tags, signal_reasons)

    signal_count = _as_int(candidate.get("signalCount"), len(signal_reasons))

    updated["type"] = "watch_candidate"
    updated["source"] = "watch-seed"
    updated["watch_candidate"] = "true"
    updated["watch_type"] = "npm"
    updated["watch_seed_id"] = str(candidate.get("id") or "")
    updated["watch_tags"] = _as_joined_csv(candidate.get("tags"))
    updated["watch_signal_sources"] = _as_joined_csv(signal_sources)
    updated["watch_signal_count"] = signal_count
    updated["watch_confidence"] = confidence
    updated["watch_why"] = reason_text
    updated["watch_discovered_at"] = str(candidate.get("discoveredAt") or now_iso)
    updated["watch_updated_at"] = now_iso
    updated["title"] = title
    updated["package"] = package_name

    repo_url = str(candidate.get("repoUrl") or "").strip()
    if repo_url:
        updated["repo_url"] = repo_url

    from_repos_csv = _as_joined_csv(candidate.get("fromRepos"))
    if from_repos_csv:
        updated["from_repos"] = from_repos_csv

    from_repo_ids_csv = _as_joined_csv(candidate.get("fromRepoIds"))
    if from_repo_ids_csv:
        updated["from_repo_ids"] = from_repo_ids_csv

    was_archived = str(frontmatter.get("watch_status") or "").strip().lower() == "archived"
    if was_archived:
        updated["watch_status"] = "new"
        updated["watch_reactivated_at"] = now_iso
        if "watch_archived_at" in updated:
            updated["watch_archived_at"] = ""
    elif not str(updated.get("watch_status") or "").strip():
        updated["watch_status"] = "new"

    if not str(updated.get("watch_owner") or "").strip():
        updated["watch_owner"] = str(candidate.get("owner") or "you")

    note_stem = os.path.splitext(os.path.basename(relative_path))[0]
    effective_body = body if body.strip() else _default_npm_candidate_body(candidate, note_stem)

    rewritten = _render_frontmatter(updated, WATCH_NOTE_FRONTMATTER_ORDER) + effective_body.lstrip("\n")
    changed = _write_text_if_changed(absolute_path, rewritten)

    created = changed and not existed_before
    updated_existing = changed and existed_before
    reactivated = was_archived and changed
    return created, updated_existing, reactivated


def _archive_watch_candidate_note(
    note_path: str,
    frontmatter: dict[str, str],
    body: str,
    now_iso: str,
    key_order: list[str] | None = None,
) -> bool:
    if str(frontmatter.get("watch_status") or "").strip().lower() == "archived":
        return False

    updated = dict(frontmatter)
    updated["watch_status"] = "archived"
    updated["watch_updated_at"] = now_iso
    updated["watch_archived_at"] = now_iso

    rewritten = _render_frontmatter(updated, key_order=key_order) + body.lstrip("\n")
    return _write_text_if_changed(note_path, rewritten)


def _archive_missing_watch_candidates(active_seed_ids: set[str], now_iso: str) -> dict[str, int]:
    repo_notes_archived = 0
    npm_notes_archived = 0

    for note_path in _iter_repo_note_paths():
        try:
            content = _read_text(note_path)
        except OSError:
            logger.warning("Failed to read repo note for watch pruning: %s", note_path)
            continue

        frontmatter, body = _parse_frontmatter(content)

        if not _is_truthy(frontmatter.get("watch_candidate")):
            continue

        watch_seed_id = _normalize_watch_seed_id(frontmatter.get("watch_seed_id"))
        if not watch_seed_id:
            continue

        watch_type = str(frontmatter.get("watch_type") or "").strip().lower()
        if watch_type and watch_type != "repo":
            continue
        if not watch_type and not watch_seed_id.startswith("github:"):
            continue

        if watch_seed_id in active_seed_ids:
            continue

        if _archive_watch_candidate_note(note_path, frontmatter, body, now_iso):
            repo_notes_archived += 1

    for note_path in _iter_watch_candidate_npm_note_paths():
        try:
            content = _read_text(note_path)
        except OSError:
            logger.warning("Failed to read npm candidate note for watch pruning: %s", note_path)
            continue

        frontmatter, body = _parse_frontmatter(content)

        if not _is_truthy(frontmatter.get("watch_candidate")):
            continue

        watch_seed_id = _normalize_watch_seed_id(frontmatter.get("watch_seed_id"))
        if not watch_seed_id:
            continue

        watch_type = str(frontmatter.get("watch_type") or "").strip().lower()
        if watch_type and watch_type != "npm":
            continue
        if not watch_type and not watch_seed_id.startswith("npm:"):
            continue

        if watch_seed_id in active_seed_ids:
            continue

        if _archive_watch_candidate_note(
            note_path,
            frontmatter,
            body,
            now_iso,
            key_order=WATCH_NOTE_FRONTMATTER_ORDER,
        ):
            npm_notes_archived += 1

    return {
        "repo_notes_archived": repo_notes_archived,
        "npm_notes_archived": npm_notes_archived,
    }


def export_watch_seed_files(
    github_output_path: str | None,
    npm_output_path: str | None,
    max_npm_lookups: int = 0,
) -> dict[str, Any]:
    """Export watchlist seed candidates from local CrawlGitHub notes.

    The export is local-first and does not call GitHub APIs.
    Optional npm metadata enrichment is bounded by ``max_npm_lookups``.
    """
    collected = _collect_watch_seed_candidates(max_npm_lookups=max_npm_lookups)

    repo_candidates = list(collected.get("repo_candidates", []))
    npm_candidates = list(collected.get("npm_candidates", []))

    if github_output_path:
        _write_jsonl(github_output_path, repo_candidates)

    if npm_output_path:
        _write_jsonl(npm_output_path, npm_candidates)

    return {
        "scanned_notes": int(collected.get("scanned_notes", 0)),
        "pi_candidates": int(collected.get("pi_candidates", 0)),
        "repo_candidates": len(repo_candidates),
        "npm_candidates": len(npm_candidates),
        "npm_lookups": int(collected.get("npm_lookups", 0)),
        "repo_confidence_counts": _confidence_counts(repo_candidates),
        "npm_confidence_counts": _confidence_counts(npm_candidates),
        "signal_source_counts": _signal_source_counts([*repo_candidates, *npm_candidates]),
        "github_output_path": github_output_path,
        "npm_output_path": npm_output_path,
    }


def sync_watch_candidates_to_notes(
    max_npm_lookups: int = 0,
    prune_missing: bool = False,
) -> dict[str, Any]:
    """Sync watch candidates into Obsidian notes/frontmatter.

    - Repo candidates are synced into existing repo notes.
    - npm candidates are synced into dedicated notes under ``WATCH_CANDIDATES_SUBDIR``.
    - Optional pruning archives stale watch candidates (`watch_status: archived`).
    """
    collected = _collect_watch_seed_candidates(max_npm_lookups=max_npm_lookups)
    repo_candidates = list(collected.get("repo_candidates", []))
    npm_candidates = list(collected.get("npm_candidates", []))

    now_iso = _utc_now_iso()

    repo_notes_updated = 0
    repo_notes_missing = 0
    repo_notes_reactivated = 0

    for candidate in repo_candidates:
        changed, missing, reactivated = _upsert_repo_candidate_note(candidate, now_iso)
        if missing:
            repo_notes_missing += 1
        if changed:
            repo_notes_updated += 1
        if reactivated:
            repo_notes_reactivated += 1

    npm_notes_created = 0
    npm_notes_updated = 0
    npm_notes_reactivated = 0

    for candidate in npm_candidates:
        created, updated, reactivated = _upsert_npm_candidate_note(candidate, now_iso)
        if created:
            npm_notes_created += 1
        elif updated:
            npm_notes_updated += 1
        if reactivated:
            npm_notes_reactivated += 1

    repo_notes_archived = 0
    npm_notes_archived = 0

    if prune_missing:
        active_seed_ids = {
            seed_id
            for seed_id in (
                _normalize_watch_seed_id(candidate.get("id"))
                for candidate in [*repo_candidates, *npm_candidates]
            )
            if seed_id
        }
        prune_stats = _archive_missing_watch_candidates(active_seed_ids=active_seed_ids, now_iso=now_iso)
        repo_notes_archived = int(prune_stats.get("repo_notes_archived", 0))
        npm_notes_archived = int(prune_stats.get("npm_notes_archived", 0))

    return {
        "scanned_notes": int(collected.get("scanned_notes", 0)),
        "pi_candidates": int(collected.get("pi_candidates", 0)),
        "repo_candidates": len(repo_candidates),
        "npm_candidates": len(npm_candidates),
        "npm_lookups": int(collected.get("npm_lookups", 0)),
        "repo_confidence_counts": _confidence_counts(repo_candidates),
        "npm_confidence_counts": _confidence_counts(npm_candidates),
        "signal_source_counts": _signal_source_counts([*repo_candidates, *npm_candidates]),
        "repo_notes_updated": repo_notes_updated,
        "repo_notes_missing": repo_notes_missing,
        "repo_notes_reactivated": repo_notes_reactivated,
        "npm_notes_created": npm_notes_created,
        "npm_notes_updated": npm_notes_updated,
        "npm_notes_reactivated": npm_notes_reactivated,
        "repo_notes_archived": repo_notes_archived,
        "npm_notes_archived": npm_notes_archived,
        "watch_notes_archived_total": repo_notes_archived + npm_notes_archived,
        "prune_watch_candidates": prune_missing,
        "watch_candidates_subdir": config.WATCH_CANDIDATES_SUBDIR,
    }
