from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Any, Sequence

from .. import config
from . import candidates as watch_candidates
from . import io as watch_io
from .contracts import WATCH_CANDIDATE_ALLOWED_CONFIDENCE
from .contracts import WATCH_FRONTMATTER_ARCHIVED_AT_FIELD
from .contracts import WATCH_FRONTMATTER_CANDIDATE_FIELD
from .contracts import WATCH_FRONTMATTER_CONFIDENCE_FIELD
from .contracts import WATCH_FRONTMATTER_DISCOVERED_AT_FIELD
from .contracts import WATCH_FRONTMATTER_OWNER_FIELD
from .contracts import WATCH_FRONTMATTER_REACTIVATED_AT_FIELD
from .contracts import WATCH_FRONTMATTER_SEED_ID_FIELD
from .contracts import WATCH_FRONTMATTER_SIGNAL_COUNT_FIELD
from .contracts import WATCH_FRONTMATTER_SIGNAL_SOURCES_FIELD
from .contracts import WATCH_FRONTMATTER_STATUS_FIELD
from .contracts import WATCH_FRONTMATTER_TAGS_FIELD
from .contracts import WATCH_FRONTMATTER_TYPE_FIELD
from .contracts import WATCH_FRONTMATTER_UPDATED_AT_FIELD
from .contracts import WATCH_FRONTMATTER_WHY_FIELD
from .contracts import WATCH_NOTE_FRONTMATTER_ORDER
from .models import WatchCandidate
from .models import as_watch_candidate
from .models import candidate_reason_fragments
from .models import refresh_watch_candidate_signal_metadata
from .models import watch_candidate_confidence_counts
from .models import watch_candidate_signal_source_counts

logger = logging.getLogger(__name__)

def _sanitize_filename(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "-", str(value or "").strip())
    sanitized = re.sub(r"-+", "-", sanitized).strip("-")
    return sanitized or "candidate"


def _repo_note_path_from_candidate(candidate: WatchCandidate | dict[str, Any]) -> str:
    candidate_model = as_watch_candidate(candidate)
    note_stem = candidate_model.repo_note.strip()
    if not note_stem:
        return ""
    return os.path.join(config.WORKING_DIRECTORY, f"{note_stem}.md")


def _npm_candidate_relative_path(candidate: WatchCandidate | dict[str, Any]) -> str:
    candidate_model = as_watch_candidate(candidate)

    candidate_id = candidate_model.id or candidate_model.package or candidate_model.title or "npm:unknown"
    digest = hashlib.sha256(candidate_id.lower().encode("utf-8")).hexdigest()[:12]
    package_name = candidate_model.package or candidate_model.title or "npm-candidate"
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


def _upsert_repo_candidate_note(
    candidate: WatchCandidate | dict[str, Any],
    now_iso: str,
) -> tuple[bool, bool, bool]:
    candidate_model = refresh_watch_candidate_signal_metadata(as_watch_candidate(candidate))

    note_path = _repo_note_path_from_candidate(candidate_model)
    if not note_path:
        return False, True, False

    if not os.path.exists(note_path):
        logger.warning("Repo candidate note not found: %s", note_path)
        return False, True, False

    try:
        content = watch_io._read_text(note_path)
    except OSError:
        logger.warning("Failed to read repo candidate note: %s", note_path)
        return False, True, False

    frontmatter, body = watch_io._parse_frontmatter(content)
    updated = dict(frontmatter)

    signal_reasons = candidate_reason_fragments(candidate_model)
    signal_sources = list(candidate_model.signal_sources)
    reason_text = candidate_model.why_watch or "; ".join(signal_reasons)

    confidence = candidate_model.confidence.strip().lower()
    if confidence not in WATCH_CANDIDATE_ALLOWED_CONFIDENCE:
        confidence = "low"

    signal_count = _as_int(candidate_model.signal_count, len(signal_reasons))

    updated[WATCH_FRONTMATTER_CANDIDATE_FIELD] = "true"
    updated[WATCH_FRONTMATTER_TYPE_FIELD] = "repo"
    updated[WATCH_FRONTMATTER_SEED_ID_FIELD] = candidate_model.id
    updated[WATCH_FRONTMATTER_TAGS_FIELD] = _as_joined_csv(candidate_model.tags)
    updated[WATCH_FRONTMATTER_SIGNAL_SOURCES_FIELD] = _as_joined_csv(signal_sources)
    updated[WATCH_FRONTMATTER_SIGNAL_COUNT_FIELD] = signal_count
    updated[WATCH_FRONTMATTER_CONFIDENCE_FIELD] = confidence
    updated[WATCH_FRONTMATTER_WHY_FIELD] = reason_text
    updated[WATCH_FRONTMATTER_DISCOVERED_AT_FIELD] = candidate_model.discovered_at or now_iso
    updated[WATCH_FRONTMATTER_UPDATED_AT_FIELD] = now_iso

    was_archived = (
        str(frontmatter.get(WATCH_FRONTMATTER_STATUS_FIELD) or "").strip().lower() == "archived"
    )
    if was_archived:
        updated[WATCH_FRONTMATTER_STATUS_FIELD] = "new"
        updated[WATCH_FRONTMATTER_REACTIVATED_AT_FIELD] = now_iso
        if WATCH_FRONTMATTER_ARCHIVED_AT_FIELD in updated:
            updated[WATCH_FRONTMATTER_ARCHIVED_AT_FIELD] = ""
    elif not str(updated.get(WATCH_FRONTMATTER_STATUS_FIELD) or "").strip():
        updated[WATCH_FRONTMATTER_STATUS_FIELD] = "new"

    if not str(updated.get(WATCH_FRONTMATTER_OWNER_FIELD) or "").strip():
        updated[WATCH_FRONTMATTER_OWNER_FIELD] = candidate_model.owner or "you"

    rewritten = watch_io._render_frontmatter(updated) + body.lstrip("\n")
    changed = watch_io._write_text_if_changed(note_path, rewritten)
    return changed, False, was_archived and changed


def _default_npm_candidate_body(candidate: WatchCandidate | dict[str, Any], note_stem: str) -> str:
    candidate_model = as_watch_candidate(candidate)

    title = candidate_model.title or candidate_model.package or note_stem
    package_name = candidate_model.package or title
    why_watch = candidate_model.why_watch
    tags_csv = _as_joined_csv(candidate_model.tags)
    repo_url = candidate_model.repo_url.strip()
    from_repos = list(candidate_model.from_repos)

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


def _upsert_npm_candidate_note(
    candidate: WatchCandidate | dict[str, Any],
    now_iso: str,
) -> tuple[bool, bool, bool]:
    candidate_model = refresh_watch_candidate_signal_metadata(as_watch_candidate(candidate))

    relative_path = _npm_candidate_relative_path(candidate_model)
    absolute_path = os.path.join(config.WORKING_DIRECTORY, relative_path)
    existed_before = os.path.exists(absolute_path)

    existing_content = ""
    if existed_before:
        try:
            existing_content = watch_io._read_text(absolute_path)
        except OSError:
            logger.warning("Failed to read npm candidate note: %s", absolute_path)
            existing_content = ""

    frontmatter, body = watch_io._parse_frontmatter(existing_content) if existing_content else ({}, "")
    updated = dict(frontmatter)

    title = candidate_model.title or candidate_model.package or "npm-candidate"
    package_name = candidate_model.package or title

    signal_reasons = candidate_reason_fragments(candidate_model)
    signal_sources = list(candidate_model.signal_sources)
    reason_text = candidate_model.why_watch or "; ".join(signal_reasons)

    confidence = candidate_model.confidence.strip().lower()
    if confidence not in WATCH_CANDIDATE_ALLOWED_CONFIDENCE:
        confidence = "low"

    signal_count = _as_int(candidate_model.signal_count, len(signal_reasons))

    updated["type"] = "watch_candidate"
    updated["source"] = "watch-seed"
    updated[WATCH_FRONTMATTER_CANDIDATE_FIELD] = "true"
    updated[WATCH_FRONTMATTER_TYPE_FIELD] = "npm"
    updated[WATCH_FRONTMATTER_SEED_ID_FIELD] = candidate_model.id
    updated[WATCH_FRONTMATTER_TAGS_FIELD] = _as_joined_csv(candidate_model.tags)
    updated[WATCH_FRONTMATTER_SIGNAL_SOURCES_FIELD] = _as_joined_csv(signal_sources)
    updated[WATCH_FRONTMATTER_SIGNAL_COUNT_FIELD] = signal_count
    updated[WATCH_FRONTMATTER_CONFIDENCE_FIELD] = confidence
    updated[WATCH_FRONTMATTER_WHY_FIELD] = reason_text
    updated[WATCH_FRONTMATTER_DISCOVERED_AT_FIELD] = candidate_model.discovered_at or now_iso
    updated[WATCH_FRONTMATTER_UPDATED_AT_FIELD] = now_iso
    updated["title"] = title
    updated["package"] = package_name

    repo_url = candidate_model.repo_url.strip()
    if repo_url:
        updated["repo_url"] = repo_url

    from_repos_csv = _as_joined_csv(candidate_model.from_repos)
    if from_repos_csv:
        updated["from_repos"] = from_repos_csv

    from_repo_ids_csv = _as_joined_csv(candidate_model.from_repo_ids)
    if from_repo_ids_csv:
        updated["from_repo_ids"] = from_repo_ids_csv

    was_archived = (
        str(frontmatter.get(WATCH_FRONTMATTER_STATUS_FIELD) or "").strip().lower() == "archived"
    )
    if was_archived:
        updated[WATCH_FRONTMATTER_STATUS_FIELD] = "new"
        updated[WATCH_FRONTMATTER_REACTIVATED_AT_FIELD] = now_iso
        if WATCH_FRONTMATTER_ARCHIVED_AT_FIELD in updated:
            updated[WATCH_FRONTMATTER_ARCHIVED_AT_FIELD] = ""
    elif not str(updated.get(WATCH_FRONTMATTER_STATUS_FIELD) or "").strip():
        updated[WATCH_FRONTMATTER_STATUS_FIELD] = "new"

    if not str(updated.get(WATCH_FRONTMATTER_OWNER_FIELD) or "").strip():
        updated[WATCH_FRONTMATTER_OWNER_FIELD] = candidate_model.owner or "you"

    note_stem = os.path.splitext(os.path.basename(relative_path))[0]
    effective_body = body if body.strip() else _default_npm_candidate_body(candidate_model, note_stem)

    rewritten = watch_io._render_frontmatter(updated, WATCH_NOTE_FRONTMATTER_ORDER) + effective_body.lstrip("\n")
    changed = watch_io._write_text_if_changed(absolute_path, rewritten)

    created = changed and not existed_before
    updated_existing = changed and existed_before
    reactivated = was_archived and changed
    return created, updated_existing, reactivated


def _archive_watch_candidate_note(
    note_path: str,
    frontmatter: dict[str, str],
    body: str,
    now_iso: str,
    key_order: Sequence[str] | None = None,
) -> bool:
    if str(frontmatter.get(WATCH_FRONTMATTER_STATUS_FIELD) or "").strip().lower() == "archived":
        return False

    updated = dict(frontmatter)
    updated[WATCH_FRONTMATTER_STATUS_FIELD] = "archived"
    updated[WATCH_FRONTMATTER_UPDATED_AT_FIELD] = now_iso
    updated[WATCH_FRONTMATTER_ARCHIVED_AT_FIELD] = now_iso

    rewritten = watch_io._render_frontmatter(updated, key_order=key_order) + body.lstrip("\n")
    return watch_io._write_text_if_changed(note_path, rewritten)


def _archive_missing_watch_candidates(active_seed_ids: set[str], now_iso: str) -> dict[str, int]:
    repo_notes_archived = 0
    npm_notes_archived = 0

    for note_path in watch_io._iter_repo_note_paths():
        try:
            content = watch_io._read_text(note_path)
        except OSError:
            logger.warning("Failed to read repo note for watch pruning: %s", note_path)
            continue

        frontmatter, body = watch_io._parse_frontmatter(content)

        if not watch_io._is_truthy(frontmatter.get(WATCH_FRONTMATTER_CANDIDATE_FIELD)):
            continue

        watch_seed_id = watch_io._normalize_watch_seed_id(
            frontmatter.get(WATCH_FRONTMATTER_SEED_ID_FIELD)
        )
        if not watch_seed_id:
            continue

        watch_type = str(frontmatter.get(WATCH_FRONTMATTER_TYPE_FIELD) or "").strip().lower()
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
            content = watch_io._read_text(note_path)
        except OSError:
            logger.warning("Failed to read npm candidate note for watch pruning: %s", note_path)
            continue

        frontmatter, body = watch_io._parse_frontmatter(content)

        if not watch_io._is_truthy(frontmatter.get(WATCH_FRONTMATTER_CANDIDATE_FIELD)):
            continue

        watch_seed_id = watch_io._normalize_watch_seed_id(
            frontmatter.get(WATCH_FRONTMATTER_SEED_ID_FIELD)
        )
        if not watch_seed_id:
            continue

        watch_type = str(frontmatter.get(WATCH_FRONTMATTER_TYPE_FIELD) or "").strip().lower()
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


def sync_watch_candidates_to_notes(
    max_npm_lookups: int = 0,
    prune_missing: bool = False,
) -> dict[str, Any]:
    """Sync watch candidates into Obsidian notes/frontmatter.

    - Repo candidates are synced into existing repo notes.
    - npm candidates are synced into dedicated notes under ``WATCH_CANDIDATES_SUBDIR``.
    - Optional pruning archives stale watch candidates (`watch_status: archived`).
    """
    collected = watch_candidates._collect_watch_seed_candidate_models(
        max_npm_lookups=max_npm_lookups
    )

    repo_candidates: list[WatchCandidate] = []
    for candidate in collected.get("repo_candidates", []):
        if isinstance(candidate, (dict, WatchCandidate)):
            repo_candidates.append(as_watch_candidate(candidate))

    npm_candidates: list[WatchCandidate] = []
    for candidate in collected.get("npm_candidates", []):
        if isinstance(candidate, (dict, WatchCandidate)):
            npm_candidates.append(as_watch_candidate(candidate))

    now_iso = watch_io._utc_now_iso()

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
                watch_io._normalize_watch_seed_id(candidate.id)
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
        "repo_confidence_counts": watch_candidate_confidence_counts(repo_candidates),
        "npm_confidence_counts": watch_candidate_confidence_counts(npm_candidates),
        "signal_source_counts": watch_candidate_signal_source_counts([*repo_candidates, *npm_candidates]),
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
