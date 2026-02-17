from __future__ import annotations

from typing import Any

from . import candidates as watch_candidates
from . import io as watch_io
from .models import watch_candidate_confidence_counts
from .models import watch_candidate_signal_source_counts


def export_watch_seed_files(
    github_output_path: str | None,
    npm_output_path: str | None,
    max_npm_lookups: int = 0,
) -> dict[str, Any]:
    """Export watchlist seed candidates from local CrawlGitHub notes.

    The export is local-first and does not call GitHub APIs.
    Optional npm metadata enrichment is bounded by ``max_npm_lookups``.
    """
    collected = watch_candidates._collect_watch_seed_candidates(max_npm_lookups=max_npm_lookups)

    repo_candidates = list(collected.get("repo_candidates", []))
    npm_candidates = list(collected.get("npm_candidates", []))

    if github_output_path:
        watch_io._write_jsonl(github_output_path, repo_candidates)

    if npm_output_path:
        watch_io._write_jsonl(npm_output_path, npm_candidates)

    return {
        "scanned_notes": int(collected.get("scanned_notes", 0)),
        "pi_candidates": int(collected.get("pi_candidates", 0)),
        "repo_candidates": len(repo_candidates),
        "npm_candidates": len(npm_candidates),
        "npm_lookups": int(collected.get("npm_lookups", 0)),
        "repo_confidence_counts": watch_candidate_confidence_counts(repo_candidates),
        "npm_confidence_counts": watch_candidate_confidence_counts(npm_candidates),
        "signal_source_counts": watch_candidate_signal_source_counts([*repo_candidates, *npm_candidates]),
        "github_output_path": github_output_path,
        "npm_output_path": npm_output_path,
    }
