from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def _as_str(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    if text:
        return text
    return str(default).strip()


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value

    text = str(value if value is not None else "").strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False

    if value is None:
        return default
    return bool(value)


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    items: list[str] = []
    for item in value:
        cleaned = str(item).strip()
        if cleaned:
            items.append(cleaned)

    return items


@dataclass
class WatchCandidate:
    id: str
    type: str
    source: str
    title: str
    starred: bool = False
    tags: list[str] = field(default_factory=list)
    why_watch: str = ""
    signal_reasons: list[str] = field(default_factory=list)
    signal_sources: list[str] = field(default_factory=list)
    signal_count: int = 0
    confidence: str = ""
    status: str = "new"
    owner: str = "you"
    discovered_at: str = ""
    repo: str = ""
    repo_url: str = ""
    repo_note: str = ""
    package: str = ""
    from_repos: list[str] = field(default_factory=list)
    from_repo_ids: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "WatchCandidate":
        known_keys = {
            "id",
            "type",
            "source",
            "title",
            "starred",
            "tags",
            "whyWatch",
            "signalReasons",
            "signalSources",
            "signalCount",
            "confidence",
            "status",
            "owner",
            "discoveredAt",
            "repo",
            "repoUrl",
            "repoNote",
            "package",
            "fromRepos",
            "fromRepoIds",
        }

        reasons = _as_str_list(payload.get("signalReasons"))
        signal_count = _as_int(payload.get("signalCount"), len(reasons))

        extra: dict[str, Any] = {
            key: value
            for key, value in payload.items()
            if key not in known_keys
        }

        return cls(
            id=_as_str(payload.get("id")),
            type=_as_str(payload.get("type")),
            source=_as_str(payload.get("source")),
            title=_as_str(payload.get("title")),
            starred=_as_bool(payload.get("starred"), default=False),
            tags=_as_str_list(payload.get("tags")),
            why_watch=_as_str(payload.get("whyWatch")),
            signal_reasons=reasons,
            signal_sources=_as_str_list(payload.get("signalSources")),
            signal_count=signal_count,
            confidence=_as_str(payload.get("confidence")),
            status=_as_str(payload.get("status"), default="new") or "new",
            owner=_as_str(payload.get("owner"), default="you") or "you",
            discovered_at=_as_str(payload.get("discoveredAt")),
            repo=_as_str(payload.get("repo")),
            repo_url=_as_str(payload.get("repoUrl")),
            repo_note=_as_str(payload.get("repoNote")),
            package=_as_str(payload.get("package")),
            from_repos=_as_str_list(payload.get("fromRepos")),
            from_repo_ids=_as_str_list(payload.get("fromRepoIds")),
            extra=extra,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "source": self.source,
            "title": self.title,
            "starred": self.starred,
            "tags": list(self.tags),
            "whyWatch": self.why_watch,
            "signalReasons": list(self.signal_reasons),
            "signalSources": list(self.signal_sources),
            "signalCount": int(self.signal_count),
            "confidence": self.confidence,
            "status": self.status,
            "owner": self.owner,
            "discoveredAt": self.discovered_at,
        }

        if self.repo:
            payload["repo"] = self.repo
        if self.repo_url:
            payload["repoUrl"] = self.repo_url
        if self.repo_note:
            payload["repoNote"] = self.repo_note
        if self.package:
            payload["package"] = self.package
        if self.from_repos:
            payload["fromRepos"] = list(self.from_repos)
        if self.from_repo_ids:
            payload["fromRepoIds"] = list(self.from_repo_ids)

        payload.update(self.extra)
        return payload

WatchCandidateLike = WatchCandidate | Mapping[str, Any]


def as_watch_candidate(payload: WatchCandidateLike) -> WatchCandidate:
    if isinstance(payload, WatchCandidate):
        return payload

    return WatchCandidate.from_dict(payload)


def candidate_reason_fragments(candidate: WatchCandidateLike) -> list[str]:
    from .signals import _normalize_reason_fragments

    candidate_model = as_watch_candidate(candidate)

    reasons = _normalize_reason_fragments(candidate_model.signal_reasons)
    if reasons:
        return reasons

    return _normalize_reason_fragments(candidate_model.why_watch)


def refresh_watch_candidate_signal_metadata(candidate: WatchCandidateLike) -> WatchCandidate:
    from .signals import _candidate_signal_sources
    from .signals import _watch_confidence

    candidate_model = as_watch_candidate(candidate)

    reasons = candidate_reason_fragments(candidate_model)
    if not reasons and candidate_model.why_watch.strip():
        reasons = [candidate_model.why_watch.strip()]

    tags = [str(tag).strip() for tag in candidate_model.tags if str(tag).strip()]
    sources = _candidate_signal_sources(candidate_model.to_dict(), reasons)

    confidence = candidate_model.confidence.strip().lower()
    if confidence not in {"low", "medium", "high"}:
        confidence = _watch_confidence(tags, reasons)

    candidate_model.signal_reasons = reasons
    candidate_model.signal_sources = sources
    candidate_model.signal_count = len(reasons)
    candidate_model.confidence = confidence
    candidate_model.why_watch = "; ".join(reasons) if reasons else ""

    return candidate_model


def coerce_watch_candidate_dict(payload: WatchCandidateLike) -> dict[str, Any]:
    return as_watch_candidate(payload).to_dict()
