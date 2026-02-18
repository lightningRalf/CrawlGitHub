from pathlib import Path
from typing import Any

from crawl_github_starred.watch import candidates as watch_candidates
from crawl_github_starred.watch import contracts as watch_contracts
from crawl_github_starred.watch import io as watch_io
from crawl_github_starred.watch import sync as watch_sync
from crawl_github_starred.watch.models import WatchCandidate


def _read_frontmatter(path: Path) -> dict[str, str]:
    content = path.read_text(encoding="utf-8")
    frontmatter, _ = watch_io._parse_frontmatter(content)
    return frontmatter


def test_candidate_and_frontmatter_contract_fields_are_canonical() -> None:
    assert watch_contracts.WATCH_CANDIDATE_SIGNAL_FIELDS == (
        "signalReasons",
        "signalSources",
        "signalCount",
        "confidence",
    )
    assert watch_contracts.WATCH_FRONTMATTER_SIGNAL_FIELDS == (
        "watch_signal_sources",
        "watch_signal_count",
    )
    assert watch_contracts.WATCH_FRONTMATTER_LIFECYCLE_FIELDS == (
        "watch_discovered_at",
        "watch_updated_at",
        "watch_reactivated_at",
        "watch_archived_at",
    )


def test_sync_frontmatter_order_uses_contract_source_of_truth() -> None:
    assert tuple(watch_sync.WATCH_NOTE_FRONTMATTER_ORDER) == watch_contracts.WATCH_NOTE_FRONTMATTER_ORDER

    signal_prefixed = tuple(
        key
        for key in watch_contracts.WATCH_NOTE_FRONTMATTER_ORDER
        if key.startswith("watch_signal_")
    )
    assert signal_prefixed == watch_contracts.WATCH_FRONTMATTER_SIGNAL_FIELDS


def test_watch_candidate_payload_exposes_only_contract_signal_keys() -> None:
    candidate = WatchCandidate.from_dict(
        {
            "id": "github:acme/rocket",
            "type": "repo",
            "source": "github-starred",
            "title": "acme/rocket",
            "whyWatch": "topic:pi-extension",
        }
    )

    payload = candidate.to_dict()

    signal_contract_keys = {
        key
        for key in payload
        if key.startswith("signal") or key == watch_contracts.WATCH_CANDIDATE_CONFIDENCE_FIELD
    }
    assert signal_contract_keys == set(watch_contracts.WATCH_CANDIDATE_SIGNAL_FIELDS)


def test_sync_writes_signal_and_lifecycle_contract_fields(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(watch_sync.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(watch_sync.config, "WATCH_CANDIDATES_SUBDIR", "watch-candidates")

    repo_note_path = tmp_path / "23.03.950_contracts.md"
    repo_note_path.write_text(
        "---\n"
        "type: checkbox\n"
        "source: github-star\n"
        "repo: acme/contracts\n"
        "repo_url: https://github.com/acme/contracts\n"
        "---\n\n"
        "# Repo note\n",
        encoding="utf-8",
    )

    npm_candidate = {
        "id": "npm:@badlogic/pi",
        "title": "@badlogic/pi",
        "package": "@badlogic/pi",
        "tags": ["pi/extension", "source/npm"],
        "whyWatch": "derived-from:acme/contracts",
        "discoveredAt": "2026-02-16T00:00:00Z",
        "owner": "you",
        "repoUrl": "https://github.com/acme/contracts",
        "fromRepos": ["acme/contracts"],
        "fromRepoIds": ["github:acme/contracts"],
    }

    def fake_collect(max_npm_lookups: int = 0) -> dict[str, Any]:
        return {
            "scanned_notes": 1,
            "pi_candidates": 1,
            "repo_candidates": [
                {
                    "id": "github:acme/contracts",
                    "title": "acme/contracts",
                    "repo": "acme/contracts",
                    "repoUrl": "https://github.com/acme/contracts",
                    "repoNote": "23.03.950_contracts",
                    "tags": ["pi/extension", "source/github-starred"],
                    "whyWatch": "topic:pi-extension",
                    "discoveredAt": "2026-02-16T00:00:00Z",
                    "owner": "you",
                }
            ],
            "npm_candidates": [npm_candidate],
            "npm_lookups": 0,
        }

    monkeypatch.setattr(watch_candidates, "_collect_watch_seed_candidates", fake_collect)

    watch_sync.sync_watch_candidates_to_notes(max_npm_lookups=0)

    repo_frontmatter = _read_frontmatter(repo_note_path)
    npm_note_path = tmp_path / watch_sync._npm_candidate_relative_path(npm_candidate)
    npm_frontmatter = _read_frontmatter(npm_note_path)

    for frontmatter in (repo_frontmatter, npm_frontmatter):
        signal_keys = {key for key in frontmatter if key.startswith("watch_signal_")}
        assert signal_keys == set(watch_contracts.WATCH_FRONTMATTER_SIGNAL_FIELDS)

        assert frontmatter.get(watch_contracts.WATCH_FRONTMATTER_DISCOVERED_AT_FIELD)
        assert frontmatter.get(watch_contracts.WATCH_FRONTMATTER_UPDATED_AT_FIELD)


def test_sync_archive_and_reactivation_write_lifecycle_contract_fields(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(watch_sync.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(watch_sync.config, "WATCH_CANDIDATES_SUBDIR", "watch-candidates")

    repo_note_path = tmp_path / "23.03.951_lifecycle.md"
    repo_note_path.write_text(
        "---\n"
        "type: checkbox\n"
        "source: github-star\n"
        "repo: acme/lifecycle\n"
        "repo_url: https://github.com/acme/lifecycle\n"
        "watch_candidate: true\n"
        "watch_type: repo\n"
        "watch_seed_id: github:acme/lifecycle\n"
        "watch_status: inbox\n"
        "watch_discovered_at: 2026-02-15T00:00:00Z\n"
        "---\n\n"
        "# Repo note\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        watch_candidates,
        "_collect_watch_seed_candidates",
        lambda **_kwargs: {
            "scanned_notes": 1,
            "pi_candidates": 0,
            "repo_candidates": [],
            "npm_candidates": [],
            "npm_lookups": 0,
        },
    )

    watch_sync.sync_watch_candidates_to_notes(max_npm_lookups=0, prune_missing=True)

    archived_frontmatter = _read_frontmatter(repo_note_path)
    assert archived_frontmatter[watch_contracts.WATCH_FRONTMATTER_STATUS_FIELD] == "archived"
    assert archived_frontmatter.get(watch_contracts.WATCH_FRONTMATTER_UPDATED_AT_FIELD)
    assert archived_frontmatter.get(watch_contracts.WATCH_FRONTMATTER_ARCHIVED_AT_FIELD)

    def fake_reactivate(max_npm_lookups: int = 0) -> dict[str, Any]:
        return {
            "scanned_notes": 1,
            "pi_candidates": 1,
            "repo_candidates": [
                {
                    "id": "github:acme/lifecycle",
                    "title": "acme/lifecycle",
                    "repo": "acme/lifecycle",
                    "repoUrl": "https://github.com/acme/lifecycle",
                    "repoNote": "23.03.951_lifecycle",
                    "tags": ["pi/extension", "source/github-starred"],
                    "whyWatch": "topic:pi-extension",
                    "discoveredAt": "2026-02-16T00:00:00Z",
                    "owner": "you",
                }
            ],
            "npm_candidates": [],
            "npm_lookups": 0,
        }

    monkeypatch.setattr(watch_candidates, "_collect_watch_seed_candidates", fake_reactivate)

    watch_sync.sync_watch_candidates_to_notes(max_npm_lookups=0)

    reactivated_frontmatter = _read_frontmatter(repo_note_path)
    assert reactivated_frontmatter[watch_contracts.WATCH_FRONTMATTER_STATUS_FIELD] == "new"
    assert reactivated_frontmatter.get(watch_contracts.WATCH_FRONTMATTER_REACTIVATED_AT_FIELD)
    assert watch_contracts.WATCH_FRONTMATTER_DISCOVERED_AT_FIELD in reactivated_frontmatter
    assert watch_contracts.WATCH_FRONTMATTER_UPDATED_AT_FIELD in reactivated_frontmatter
