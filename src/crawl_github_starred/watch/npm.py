from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import quote

import requests

from .. import config
from .models import WatchCandidate
from .models import as_watch_candidate
from .models import candidate_reason_fragments
from .models import coerce_watch_candidate_dict
from .models import refresh_watch_candidate_signal_metadata
from .signals import PI_MARKER_TO_TAG
from .signals import _append_unique

logger = logging.getLogger(__name__)

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


def _apply_npm_metadata(
    candidate: WatchCandidate | dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    candidate_model = as_watch_candidate(candidate)

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
        candidate_model.extra["npmLatestVersion"] = latest_version
    if npm_description:
        candidate_model.extra["npmDescription"] = npm_description

    keywords = _extract_npm_keywords(payload, latest_version_payload)
    if keywords:
        candidate_model.extra["npmKeywords"] = keywords

    tags = set(candidate_model.tags)
    reason_fragments = candidate_reason_fragments(candidate_model)

    for keyword in keywords:
        tag = PI_MARKER_TO_TAG.get(keyword)
        if not tag:
            continue

        tags.add(tag)
        fragment = f"npm-keyword:{keyword}"
        _append_unique(reason_fragments, fragment)

    candidate_model.tags = sorted(tags)
    candidate_model.signal_reasons = reason_fragments
    candidate_model.confidence = ""
    refresh_watch_candidate_signal_metadata(candidate_model)

    updated_payload = coerce_watch_candidate_dict(candidate_model)

    if isinstance(candidate, dict):
        candidate.clear()
        candidate.update(updated_payload)
        return candidate

    return updated_payload


def _enrich_npm_candidates(
    candidates: list[WatchCandidate | dict[str, Any]],
    max_npm_lookups: int,
) -> int:
    if max_npm_lookups <= 0:
        return 0

    lookups_done = 0
    for index, raw_candidate in enumerate(candidates):
        if lookups_done >= max_npm_lookups:
            break

        if not isinstance(raw_candidate, (dict, WatchCandidate)):
            continue

        candidate_model = as_watch_candidate(raw_candidate)
        if isinstance(raw_candidate, WatchCandidate):
            candidates[index] = candidate_model
        else:
            normalized_dict = coerce_watch_candidate_dict(candidate_model)
            candidates[index] = normalized_dict

        package_name = (candidate_model.package or candidate_model.title).strip()
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
                updated_payload = _apply_npm_metadata(candidate_model, payload)
                if isinstance(raw_candidate, dict):
                    raw_candidate.clear()
                    raw_candidate.update(updated_payload)
                    candidates[index] = raw_candidate
                else:
                    candidates[index] = candidate_model

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
