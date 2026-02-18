from __future__ import annotations

import logging
import os
import re
from typing import Any

from . import io as watch_io
from . import npm as watch_npm
from .contracts import WATCH_CANDIDATE_SIGNAL_REASONS_FIELD
from .contracts import WATCH_CANDIDATE_WHY_FIELD
from .contracts import WATCH_CANDIDATE_DISCOVERED_AT_FIELD
from .models import WatchCandidate
from .models import as_watch_candidate
from .models import candidate_reason_fragments
from .models import candidate_signal_sources
from .models import coerce_watch_candidate_dict
from .models import refresh_watch_candidate_signal_metadata
from .signals import _append_unique
from .signals import _classify_repo_candidate
from .signals import _normalize_reason_fragments

logger = logging.getLogger(__name__)


def _normalize_discovered_at(frontmatter: dict[str, str], fallback_iso: str) -> str:
    last_seen = str(frontmatter.get("last_seen_date") or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", last_seen):
        return f"{last_seen}T00:00:00Z"
    return fallback_iso


def _format_repo_id(repo_name: str, repo_url: str, note_stem: str) -> str:
    if repo_name:
        return f"github:{repo_name.lower()}"

    guessed = watch_io._guess_repo_from_url(repo_url)
    if guessed:
        return f"github:{guessed.lower()}"

    return f"github:{note_stem.lower()}"


def _build_repo_candidate(
    note_path: str,
    frontmatter: dict[str, str],
    tags: list[str],
    reasons: list[str],
    fallback_discovered_at: str,
) -> WatchCandidate:
    note_filename = os.path.basename(note_path)
    note_stem = os.path.splitext(note_filename)[0]

    repo_url = str(frontmatter.get("repo_url") or "").strip()
    repo_name = str(frontmatter.get("repo") or "").strip() or watch_io._guess_repo_from_url(repo_url)
    title = repo_name or str(frontmatter.get("repo_name") or "").strip() or note_stem

    normalized_reasons = _normalize_reason_fragments(reasons)
    payload: dict[str, Any] = {
        "id": _format_repo_id(repo_name, repo_url, note_stem),
        "type": "repo",
        "source": "github-starred",
        "title": title,
        "starred": True,
        "tags": sorted({*tags, "source/github-starred"}),
        WATCH_CANDIDATE_WHY_FIELD: "; ".join(normalized_reasons)
        if normalized_reasons
        else "pi-related repository signal",
        WATCH_CANDIDATE_SIGNAL_REASONS_FIELD: normalized_reasons,
        "status": "new",
        "owner": "you",
        WATCH_CANDIDATE_DISCOVERED_AT_FIELD: _normalize_discovered_at(
            frontmatter,
            fallback_discovered_at,
        ),
    }

    if repo_name:
        payload["repo"] = repo_name
    if repo_url:
        payload["repoUrl"] = repo_url

    payload["repoNote"] = note_stem
    return refresh_watch_candidate_signal_metadata(as_watch_candidate(payload))


def _build_npm_candidate(
    package_name: str,
    repo_candidate: WatchCandidate | dict[str, Any],
    fallback_discovered_at: str,
) -> WatchCandidate:
    repo_candidate_model = as_watch_candidate(repo_candidate)

    repo_title = repo_candidate_model.title or "repo"
    repo_id = repo_candidate_model.id
    base_tags = [tag for tag in repo_candidate_model.tags if tag != "source/github-starred"]

    reason_fragment = f"derived-from:{repo_title}"
    payload: dict[str, Any] = {
        "id": f"npm:{package_name.lower()}",
        "type": "npm",
        "source": "npm",
        "title": package_name,
        "starred": False,
        "tags": sorted({*base_tags, "source/npm"}),
        WATCH_CANDIDATE_WHY_FIELD: reason_fragment,
        WATCH_CANDIDATE_SIGNAL_REASONS_FIELD: [reason_fragment],
        "status": "new",
        "owner": "you",
        WATCH_CANDIDATE_DISCOVERED_AT_FIELD: fallback_discovered_at,
        "package": package_name,
        "fromRepos": [repo_title],
    }

    repo_url = repo_candidate_model.repo_url.strip()
    if repo_url:
        payload["repoUrl"] = repo_url

    if repo_id:
        payload["fromRepoIds"] = [repo_id]

    return refresh_watch_candidate_signal_metadata(as_watch_candidate(payload))


def _merge_repo_candidate(
    store: dict[str, WatchCandidate],
    candidate: WatchCandidate | dict[str, Any],
) -> None:
    candidate_model = refresh_watch_candidate_signal_metadata(as_watch_candidate(candidate))
    candidate_reasons = candidate_reason_fragments(candidate_model)

    candidate_id = candidate_model.id
    existing_model = store.get(candidate_id)
    if existing_model is None:
        store[candidate_id] = as_watch_candidate(candidate_model.to_dict())
        return

    existing_model.tags = sorted({*existing_model.tags, *candidate_model.tags})

    merged_reasons = candidate_reason_fragments(existing_model)
    for reason in candidate_reasons:
        _append_unique(merged_reasons, reason)
    existing_model.signal_reasons = merged_reasons

    merged_sources = candidate_signal_sources(existing_model, merged_reasons)
    for source in candidate_signal_sources(candidate_model, candidate_reasons):
        _append_unique(merged_sources, source)
    existing_model.signal_sources = merged_sources

    existing_model.confidence = ""
    refresh_watch_candidate_signal_metadata(existing_model)


def _merge_npm_candidate(
    store: dict[str, WatchCandidate],
    candidate: WatchCandidate | dict[str, Any],
) -> None:
    candidate_model = refresh_watch_candidate_signal_metadata(as_watch_candidate(candidate))
    candidate_reasons = candidate_reason_fragments(candidate_model)

    candidate_id = candidate_model.id
    existing_model = store.get(candidate_id)
    if existing_model is None:
        store[candidate_id] = as_watch_candidate(candidate_model.to_dict())
        return

    existing_model.tags = sorted({*existing_model.tags, *candidate_model.tags})

    merged_from_repos = list(existing_model.from_repos)
    for repo in candidate_model.from_repos:
        if repo not in merged_from_repos:
            merged_from_repos.append(repo)
    existing_model.from_repos = merged_from_repos

    merged_from_repo_ids = list(existing_model.from_repo_ids)
    for repo_id in candidate_model.from_repo_ids:
        if repo_id not in merged_from_repo_ids:
            merged_from_repo_ids.append(repo_id)
    existing_model.from_repo_ids = merged_from_repo_ids

    merged_reasons = candidate_reason_fragments(existing_model)
    for reason in candidate_reasons:
        _append_unique(merged_reasons, reason)

    for repo in candidate_model.from_repos:
        fragment = f"derived-from:{repo}"
        _append_unique(merged_reasons, fragment)

    existing_model.signal_reasons = merged_reasons

    merged_sources = candidate_signal_sources(existing_model, merged_reasons)
    for source in candidate_signal_sources(candidate_model, candidate_reasons):
        _append_unique(merged_sources, source)
    existing_model.signal_sources = merged_sources

    existing_model.confidence = ""
    refresh_watch_candidate_signal_metadata(existing_model)


def _collect_watch_seed_candidate_models(max_npm_lookups: int = 0) -> dict[str, Any]:
    fallback_discovered_at = watch_io._utc_now_iso()

    repo_candidates_by_id: dict[str, WatchCandidate] = {}
    npm_candidates_by_id: dict[str, WatchCandidate] = {}

    scanned_notes = 0
    pi_candidates = 0

    for note_path in watch_io._iter_repo_note_paths():
        scanned_notes += 1

        try:
            note_content = watch_io._read_text(note_path)
        except OSError:
            logger.warning("Failed to read repo note: %s", note_path)
            continue

        frontmatter, body = watch_io._parse_frontmatter(note_content)

        header_description, header_repo_url = watch_io._infer_repo_header(body)

        repo_url = str(frontmatter.get("repo_url") or "").strip() or str(header_repo_url or "").strip()
        if not repo_url.startswith("https://github.com/"):
            continue
        frontmatter["repo_url"] = repo_url

        if "repo" not in frontmatter or not str(frontmatter.get("repo") or "").strip():
            guessed_repo = watch_io._guess_repo_from_url(repo_url)
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
            or watch_io._infer_readme_note_path(body)
        )
        readme_text = watch_io._read_readme_text(readme_relative_path)

        tags, reasons = _classify_repo_candidate(frontmatter, body, readme_text)
        if not tags:
            continue

        pi_candidates += 1

        repo_candidate = _build_repo_candidate(
            note_path=note_path,
            frontmatter=frontmatter,
            tags=tags,
            reasons=reasons,
            fallback_discovered_at=fallback_discovered_at,
        )
        _merge_repo_candidate(repo_candidates_by_id, repo_candidate)

        repo_name = str(frontmatter.get("repo_name") or "").strip()
        package_names = watch_npm._extract_npm_packages(readme_text, repo_name)

        for package_name in package_names:
            if not watch_npm._is_pi_relevant_package(package_name):
                continue

            npm_candidate = _build_npm_candidate(
                package_name=package_name,
                repo_candidate=repo_candidate,
                fallback_discovered_at=fallback_discovered_at,
            )
            _merge_npm_candidate(npm_candidates_by_id, npm_candidate)

    repo_candidates_models = sorted(repo_candidates_by_id.values(), key=lambda item: item.id)
    npm_candidates_models = sorted(npm_candidates_by_id.values(), key=lambda item: item.id)

    npm_lookups_done = watch_npm._enrich_npm_candidates(npm_candidates_models, max(0, max_npm_lookups))

    return {
        "scanned_notes": scanned_notes,
        "pi_candidates": pi_candidates,
        "repo_candidates": repo_candidates_models,
        "npm_candidates": npm_candidates_models,
        "npm_lookups": npm_lookups_done,
    }


def _collect_watch_seed_candidates(max_npm_lookups: int = 0) -> dict[str, Any]:
    collected = _collect_watch_seed_candidate_models(max_npm_lookups=max_npm_lookups)

    repo_candidates = [
        coerce_watch_candidate_dict(candidate)
        for candidate in collected.get("repo_candidates", [])
        if isinstance(candidate, (WatchCandidate, dict))
    ]
    npm_candidates = [
        coerce_watch_candidate_dict(candidate)
        for candidate in collected.get("npm_candidates", [])
        if isinstance(candidate, (WatchCandidate, dict))
    ]

    return {
        "scanned_notes": int(collected.get("scanned_notes", 0)),
        "pi_candidates": int(collected.get("pi_candidates", 0)),
        "repo_candidates": repo_candidates,
        "npm_candidates": npm_candidates,
        "npm_lookups": int(collected.get("npm_lookups", 0)),
    }
