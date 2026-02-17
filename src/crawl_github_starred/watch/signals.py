from __future__ import annotations

import re
from typing import Any

PI_MARKER_TO_TAG = {
    "pi-package": "pi/extension",
    "pi-extension": "pi/extension",
    "pi-extensions": "pi/extension",
    "pi-coding-agent": "pi/extension",
    "pi-apps": "pi/extension",
    "pi-skill": "pi/skill",
    "pi-skills": "pi/skill",
    "pi-prompt": "pi/prompt",
    "pi-prompts": "pi/prompt",
    "pi-theme": "pi/theme",
    "pi-themes": "pi/theme",
}

PI_PHRASE_TO_TAG = {
    "pi extension": "pi/extension",
    "pi package": "pi/extension",
    "pi coding agent": "pi/extension",
    "pi skill": "pi/skill",
    "pi prompt": "pi/prompt",
    "pi theme": "pi/theme",
}

PATH_SIGNAL_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "pi/extension",
        re.compile(r"(?:^|[\s`\"'])extensions/[^\s`\"']+\.(?:ts|tsx|js|mjs|cjs)\b", re.IGNORECASE),
        "readme-path:extensions/*.{ts,js}",
    ),
    (
        "pi/skill",
        re.compile(r"(?:^|[\s`\"'])skills/[^\s`\"']*SKILL\.md\b", re.IGNORECASE),
        "readme-path:skills/**/SKILL.md",
    ),
    (
        "pi/prompt",
        re.compile(r"(?:^|[\s`\"'])prompts/[^\s`\"']+\.md\b", re.IGNORECASE),
        "readme-path:prompts/*.md",
    ),
    (
        "pi/theme",
        re.compile(r"(?:^|[\s`\"'])themes/[^\s`\"']+\.json\b", re.IGNORECASE),
        "readme-path:themes/*.json",
    ),
]


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _contains_term(text_lower: str, term: str) -> bool:
    normalized_term = str(term or "").strip().lower()
    if not normalized_term:
        return False

    pattern = re.compile(
        rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])",
        re.IGNORECASE,
    )
    return pattern.search(text_lower) is not None


_SIGNAL_SOURCE_ORDER = [
    "topic",
    "signal",
    "phrase",
    "path",
    "anchor",
    "derived",
    "npm-keyword",
    "other",
]

_SIGNAL_SOURCE_WEIGHT = {
    "topic": 3,
    "signal": 3,
    "phrase": 2,
    "path": 2,
    "anchor": 2,
    "derived": 1,
    "npm-keyword": 2,
    "other": 1,
}


def _split_semicolon_values(value: Any) -> list[str]:
    raw_text = str(value or "")
    parts = [part.strip() for part in raw_text.split(";")]
    return [part for part in parts if part]


def _normalize_reason_fragments(value: Any) -> list[str]:
    fragments: list[str] = []

    if isinstance(value, list):
        for item in value:
            cleaned = str(item).strip()
            if cleaned:
                _append_unique(fragments, cleaned)
        return fragments

    for fragment in _split_semicolon_values(value):
        _append_unique(fragments, fragment)
    return fragments


def _reason_source(reason: str) -> str:
    cleaned = str(reason or "").strip().lower()
    if cleaned.startswith("topic:"):
        return "topic"
    if cleaned.startswith("signal:"):
        return "signal"
    if cleaned.startswith("phrase:"):
        return "phrase"
    if cleaned.startswith("readme-path:"):
        return "path"
    if cleaned.startswith("repo:") or cleaned.startswith("repo-name:"):
        return "anchor"
    if cleaned.startswith("derived-from:"):
        return "derived"
    if cleaned.startswith("npm-keyword:"):
        return "npm-keyword"
    return "other"


def _signal_sources_from_reasons(reasons: list[str]) -> list[str]:
    sources: list[str] = []
    for reason in reasons:
        _append_unique(sources, _reason_source(reason))

    ordered: list[str] = []
    for source in _SIGNAL_SOURCE_ORDER:
        if source in sources:
            ordered.append(source)

    for source in sources:
        if source not in ordered:
            ordered.append(source)

    return ordered


def _watch_confidence(tags: list[str], reasons: list[str]) -> str:
    sources = _signal_sources_from_reasons(reasons)
    score = sum(_SIGNAL_SOURCE_WEIGHT.get(source, 1) for source in sources)

    non_source_tags = [
        tag
        for tag in tags
        if not str(tag).strip().lower().startswith("source/")
    ]
    if len(set(non_source_tags)) >= 2:
        score += 1

    if score >= 5:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def _candidate_reason_fragments(candidate: dict[str, Any]) -> list[str]:
    reasons = _normalize_reason_fragments(candidate.get("signalReasons"))
    if reasons:
        return reasons
    return _normalize_reason_fragments(candidate.get("whyWatch"))


def _candidate_signal_sources(candidate: dict[str, Any], reasons: list[str]) -> list[str]:
    provided = candidate.get("signalSources")
    provided_sources: list[str] = []

    if isinstance(provided, list):
        for source in provided:
            cleaned = str(source).strip().lower()
            if cleaned:
                _append_unique(provided_sources, cleaned)
    else:
        for source in str(provided or "").split(","):
            cleaned = source.strip().lower()
            if cleaned:
                _append_unique(provided_sources, cleaned)

    if provided_sources:
        ordered: list[str] = []
        for source in _SIGNAL_SOURCE_ORDER:
            if source in provided_sources:
                ordered.append(source)

        for source in provided_sources:
            if source not in ordered:
                ordered.append(source)

        return ordered

    return _signal_sources_from_reasons(reasons)


def _populate_signal_metadata(candidate: dict[str, Any]) -> None:
    reasons = _candidate_reason_fragments(candidate)
    if not reasons:
        fallback = str(candidate.get("whyWatch") or "").strip()
        if fallback:
            reasons = [fallback]

    tags = [str(tag).strip() for tag in candidate.get("tags", []) if str(tag).strip()]
    sources = _candidate_signal_sources(candidate, reasons)

    provided_confidence = str(candidate.get("confidence") or "").strip().lower()
    if provided_confidence not in {"low", "medium", "high"}:
        provided_confidence = ""

    candidate["signalReasons"] = reasons
    candidate["signalSources"] = sources
    candidate["signalCount"] = len(reasons)
    candidate["confidence"] = provided_confidence or _watch_confidence(tags, reasons)
    candidate["whyWatch"] = "; ".join(reasons) if reasons else ""


def _confidence_counts(candidates: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0}

    for candidate in candidates:
        reasons = _candidate_reason_fragments(candidate)
        tags = [str(tag).strip() for tag in candidate.get("tags", []) if str(tag).strip()]

        confidence = str(candidate.get("confidence") or "").strip().lower()
        if confidence not in counts:
            confidence = _watch_confidence(tags, reasons)

        counts[confidence] = counts.get(confidence, 0) + 1

    return {key: value for key, value in counts.items() if value > 0}


def _signal_source_counts(candidates: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}

    for candidate in candidates:
        reasons = _candidate_reason_fragments(candidate)
        sources = _candidate_signal_sources(candidate, reasons)

        for source in sources:
            counts[source] = counts.get(source, 0) + 1

    ordered_sources: list[str] = []
    for source in _SIGNAL_SOURCE_ORDER:
        if source in counts:
            ordered_sources.append(source)

    for source in sorted(counts):
        if source not in ordered_sources:
            ordered_sources.append(source)

    return {source: counts[source] for source in ordered_sources}


def _split_topics(raw_topics: str) -> list[str]:
    topics: list[str] = []
    for topic in str(raw_topics or "").split(","):
        cleaned = topic.strip().lower()
        if cleaned:
            topics.append(cleaned)
    return topics


def _looks_like_pi_anchor(frontmatter: dict[str, str]) -> str | None:
    """Return a strong repository-identity anchor for the Pi ecosystem.

    This intentionally stays conservative to avoid broad false positives from
    generic "...-pi-..." repository names.
    """
    repo_name = str(frontmatter.get("repo_name") or "").strip().lower()
    repo_full_name = str(frontmatter.get("repo") or "").strip().lower()

    if repo_name == "pi":
        return f"repo-name:{repo_name}"

    if repo_full_name.endswith("/pi"):
        return f"repo:{repo_full_name}"

    return None


def _classify_repo_candidate(
    frontmatter: dict[str, str],
    body: str,
    readme_text: str,
) -> tuple[list[str], list[str]]:
    tags: list[str] = []
    reasons: list[str] = []

    topics = _split_topics(str(frontmatter.get("topics") or ""))

    frontmatter_text = "\n".join(
        [
            str(frontmatter.get("repo") or ""),
            str(frontmatter.get("repo_name") or ""),
            str(frontmatter.get("repo_description") or ""),
            str(frontmatter.get("topics") or ""),
        ]
    )
    frontmatter_text_lower = frontmatter_text.lower()

    combined_text = "\n".join([frontmatter_text, body, readme_text])
    combined_text_lower = combined_text.lower()

    for topic in topics:
        tag = PI_MARKER_TO_TAG.get(topic)
        if not tag:
            continue
        _append_unique(tags, tag)
        _append_unique(reasons, f"topic:{topic}")

    for marker, tag in PI_MARKER_TO_TAG.items():
        if _contains_term(frontmatter_text_lower, marker):
            _append_unique(tags, tag)
            _append_unique(reasons, f"signal:{marker}")

    for phrase, tag in PI_PHRASE_TO_TAG.items():
        source_text = combined_text_lower if phrase == "pi coding agent" else frontmatter_text_lower
        if _contains_term(source_text, phrase):
            _append_unique(tags, tag)
            _append_unique(reasons, f"phrase:{phrase}")

    pi_anchor_reason = _looks_like_pi_anchor(frontmatter)

    for tag, pattern, reason in PATH_SIGNAL_PATTERNS:
        if pattern.search(readme_text):
            if tags or pi_anchor_reason:
                _append_unique(tags, tag)
                _append_unique(reasons, reason)

    if not tags and pi_anchor_reason:
        _append_unique(tags, "pi/extension")
        _append_unique(reasons, pi_anchor_reason)

    return sorted(tags), reasons
