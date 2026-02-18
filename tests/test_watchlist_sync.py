from pathlib import Path
from typing import Any

from crawl_github_starred.watch import candidates as watch_candidates
from crawl_github_starred.watch import sync as watch_sync
from crawl_github_starred.watch.models import WatchCandidate


def test_npm_candidate_relative_path_is_stable(monkeypatch: Any) -> None:
    monkeypatch.setattr(watch_sync.config, "WATCH_CANDIDATES_SUBDIR", "watch-candidates")

    candidate = {
        "id": "npm:@badlogic/pi",
        "package": "@badlogic/pi",
        "title": "@badlogic/pi",
    }

    path_a = watch_sync._npm_candidate_relative_path(candidate)
    path_b = watch_sync._npm_candidate_relative_path(candidate)

    assert path_a == path_b
    assert path_a.startswith("watch-candidates/")
    assert path_a.endswith(".md")


def test_npm_candidate_relative_path_accepts_typed_model(monkeypatch: Any) -> None:
    monkeypatch.setattr(watch_sync.config, "WATCH_CANDIDATES_SUBDIR", "watch-candidates")

    candidate = WatchCandidate.from_dict(
        {
            "id": "npm:@badlogic/pi",
            "type": "npm",
            "source": "npm",
            "title": "@badlogic/pi",
            "package": "@badlogic/pi",
        }
    )

    path_value = watch_sync._npm_candidate_relative_path(candidate)

    assert path_value.startswith("watch-candidates/")
    assert path_value.endswith(".md")


def test_sync_watch_candidates_to_notes_updates_repo_and_creates_npm_note(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(watch_sync.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(watch_sync.config, "WATCH_CANDIDATES_SUBDIR", "watch-candidates")

    repo_note_path = tmp_path / "23.03.999_rocket.md"
    repo_note_path.write_text(
        "---\n"
        "type: checkbox\n"
        "source: github-star\n"
        "repo: acme/rocket\n"
        "repo_url: https://github.com/acme/rocket\n"
        "---\n\n"
        "# Repo note\n",
        encoding="utf-8",
    )

    def fake_collect(max_npm_lookups: int = 0) -> dict[str, Any]:
        return {
            "scanned_notes": 1,
            "pi_candidates": 1,
            "repo_candidates": [
                {
                    "id": "github:acme/rocket",
                    "title": "acme/rocket",
                    "repo": "acme/rocket",
                    "repoUrl": "https://github.com/acme/rocket",
                    "repoNote": "23.03.999_rocket",
                    "tags": ["pi/extension", "source/github-starred"],
                    "whyWatch": "topic:pi-extension",
                    "discoveredAt": "2026-02-16T00:00:00Z",
                    "owner": "you",
                }
            ],
            "npm_candidates": [
                {
                    "id": "npm:@badlogic/pi",
                    "title": "@badlogic/pi",
                    "package": "@badlogic/pi",
                    "tags": ["pi/extension", "source/npm"],
                    "whyWatch": "derived-from:acme/rocket",
                    "discoveredAt": "2026-02-16T00:00:00Z",
                    "owner": "you",
                    "repoUrl": "https://github.com/acme/rocket",
                    "fromRepos": ["acme/rocket"],
                    "fromRepoIds": ["github:acme/rocket"],
                }
            ],
            "npm_lookups": 0,
        }

    monkeypatch.setattr(watch_candidates, "_collect_watch_seed_candidate_models", fake_collect)

    stats = watch_sync.sync_watch_candidates_to_notes(max_npm_lookups=0)

    assert stats["repo_notes_updated"] == 1
    assert stats["npm_notes_created"] == 1
    assert stats["repo_confidence_counts"] == {"medium": 1}
    assert stats["npm_confidence_counts"] == {"low": 1}
    assert stats["signal_source_counts"] == {"topic": 1, "derived": 1}

    repo_text = repo_note_path.read_text(encoding="utf-8")
    assert "watch_candidate: true" in repo_text or 'watch_candidate: "true"' in repo_text
    assert "watch_type: repo" in repo_text
    assert "watch_seed_id: github:acme/rocket" in repo_text
    assert "watch_signal_sources: topic" in repo_text
    assert "watch_confidence: medium" in repo_text

    watch_dir = tmp_path / "watch-candidates"
    npm_files = list(watch_dir.glob("*.md"))
    assert len(npm_files) == 1

    npm_text = npm_files[0].read_text(encoding="utf-8")
    assert "type: watch_candidate" in npm_text
    assert "watch_type: npm" in npm_text
    assert "package: @badlogic/pi" in npm_text
    assert "watch_signal_sources: derived" in npm_text
    assert "watch_confidence: low" in npm_text


def test_sync_watch_candidates_accepts_typed_candidate_collection(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(watch_sync.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(watch_sync.config, "WATCH_CANDIDATES_SUBDIR", "watch-candidates")

    repo_note_path = tmp_path / "23.03.998_typed.md"
    repo_note_path.write_text(
        "---\n"
        "type: checkbox\n"
        "source: github-star\n"
        "repo: acme/typed\n"
        "repo_url: https://github.com/acme/typed\n"
        "---\n\n"
        "# Repo note\n",
        encoding="utf-8",
    )

    typed_repo_candidate = WatchCandidate.from_dict(
        {
            "id": "github:acme/typed",
            "type": "repo",
            "source": "github-starred",
            "title": "acme/typed",
            "repo": "acme/typed",
            "repoUrl": "https://github.com/acme/typed",
            "repoNote": "23.03.998_typed",
            "tags": ["pi/extension", "source/github-starred"],
            "whyWatch": "topic:pi-extension",
            "signalReasons": ["topic:pi-extension"],
            "signalSources": ["topic"],
            "signalCount": 1,
            "confidence": "medium",
            "discoveredAt": "2026-02-16T00:00:00Z",
            "owner": "you",
        }
    )

    typed_npm_candidate = WatchCandidate.from_dict(
        {
            "id": "npm:@badlogic/pi",
            "type": "npm",
            "source": "npm",
            "title": "@badlogic/pi",
            "package": "@badlogic/pi",
            "tags": ["pi/extension", "source/npm"],
            "whyWatch": "derived-from:acme/typed",
            "signalReasons": ["derived-from:acme/typed"],
            "signalSources": ["derived"],
            "signalCount": 1,
            "confidence": "low",
            "discoveredAt": "2026-02-16T00:00:00Z",
            "owner": "you",
            "repoUrl": "https://github.com/acme/typed",
            "fromRepos": ["acme/typed"],
            "fromRepoIds": ["github:acme/typed"],
        }
    )

    def fake_collect(max_npm_lookups: int = 0) -> dict[str, Any]:
        return {
            "scanned_notes": 1,
            "pi_candidates": 1,
            "repo_candidates": [typed_repo_candidate],
            "npm_candidates": [typed_npm_candidate],
            "npm_lookups": 0,
        }

    monkeypatch.setattr(watch_candidates, "_collect_watch_seed_candidate_models", fake_collect)

    stats = watch_sync.sync_watch_candidates_to_notes(max_npm_lookups=0)

    assert stats["repo_notes_updated"] == 1
    assert stats["npm_notes_created"] == 1


def test_sync_watch_candidates_uses_typed_collector_only(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(watch_sync.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(watch_sync.config, "WATCH_CANDIDATES_SUBDIR", "watch-candidates")

    repo_note_path = tmp_path / "23.03.997_typed-collector.md"
    repo_note_path.write_text(
        "---\n"
        "type: checkbox\n"
        "source: github-star\n"
        "repo: acme/typed-collector\n"
        "repo_url: https://github.com/acme/typed-collector\n"
        "---\n\n"
        "# Repo note\n",
        encoding="utf-8",
    )

    collect_calls: list[int] = []

    def fake_collect_models(max_npm_lookups: int = 0) -> dict[str, Any]:
        collect_calls.append(max_npm_lookups)
        return {
            "scanned_notes": 1,
            "pi_candidates": 1,
            "repo_candidates": [
                WatchCandidate.from_dict(
                    {
                        "id": "github:acme/typed-collector",
                        "type": "repo",
                        "source": "github-starred",
                        "title": "acme/typed-collector",
                        "repo": "acme/typed-collector",
                        "repoUrl": "https://github.com/acme/typed-collector",
                        "repoNote": "23.03.997_typed-collector",
                        "tags": ["pi/extension", "source/github-starred"],
                        "whyWatch": "topic:pi-extension",
                        "discoveredAt": "2026-02-16T00:00:00Z",
                        "owner": "you",
                    }
                )
            ],
            "npm_candidates": [],
            "npm_lookups": 0,
        }

    def fail_collect_dict(**_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("Legacy dict collector should not be used by sync path.")

    monkeypatch.setattr(
        watch_candidates,
        "_collect_watch_seed_candidate_models",
        fake_collect_models,
    )
    monkeypatch.setattr(
        watch_candidates,
        "_collect_watch_seed_candidates",
        fail_collect_dict,
    )

    stats = watch_sync.sync_watch_candidates_to_notes(max_npm_lookups=2)

    assert collect_calls == [2]
    assert stats["repo_notes_updated"] == 1
    assert stats["repo_candidates"] == 1

    repo_text = repo_note_path.read_text(encoding="utf-8")
    assert "watch_seed_id: github:acme/typed-collector" in repo_text


def test_sync_watch_candidates_reactivates_archived_notes(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(watch_sync.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(watch_sync.config, "WATCH_CANDIDATES_SUBDIR", "watch-candidates")

    repo_note_path = tmp_path / "23.03.900_archived-repo.md"
    repo_note_path.write_text(
        "---\n"
        "type: checkbox\n"
        "source: github-star\n"
        "repo: acme/archived\n"
        "repo_url: https://github.com/acme/archived\n"
        "watch_candidate: true\n"
        "watch_type: repo\n"
        "watch_seed_id: github:acme/archived\n"
        "watch_status: archived\n"
        "---\n\n"
        "# Repo note\n",
        encoding="utf-8",
    )

    npm_candidate = {
        "id": "npm:@badlogic/pi",
        "title": "@badlogic/pi",
        "package": "@badlogic/pi",
        "tags": ["pi/extension", "source/npm"],
        "whyWatch": "derived-from:acme/archived",
        "discoveredAt": "2026-02-16T00:00:00Z",
        "owner": "you",
        "repoUrl": "https://github.com/acme/archived",
        "fromRepos": ["acme/archived"],
        "fromRepoIds": ["github:acme/archived"],
    }
    npm_relative_path = watch_sync._npm_candidate_relative_path(npm_candidate)
    npm_note_path = tmp_path / npm_relative_path
    npm_note_path.parent.mkdir(parents=True, exist_ok=True)
    npm_note_path.write_text(
        "---\n"
        "type: watch_candidate\n"
        "source: watch-seed\n"
        "watch_candidate: true\n"
        "watch_type: npm\n"
        "watch_seed_id: npm:@badlogic/pi\n"
        "watch_status: archived\n"
        "package: @badlogic/pi\n"
        "---\n\n"
        "# Existing npm note\n",
        encoding="utf-8",
    )

    def fake_collect(max_npm_lookups: int = 0) -> dict[str, Any]:
        return {
            "scanned_notes": 1,
            "pi_candidates": 1,
            "repo_candidates": [
                {
                    "id": "github:acme/archived",
                    "title": "acme/archived",
                    "repo": "acme/archived",
                    "repoUrl": "https://github.com/acme/archived",
                    "repoNote": "23.03.900_archived-repo",
                    "tags": ["pi/extension", "source/github-starred"],
                    "whyWatch": "topic:pi-extension",
                    "discoveredAt": "2026-02-16T00:00:00Z",
                    "owner": "you",
                }
            ],
            "npm_candidates": [npm_candidate],
            "npm_lookups": 0,
        }

    monkeypatch.setattr(watch_candidates, "_collect_watch_seed_candidate_models", fake_collect)

    stats = watch_sync.sync_watch_candidates_to_notes(max_npm_lookups=0)

    assert stats["repo_notes_reactivated"] == 1
    assert stats["npm_notes_reactivated"] == 1

    repo_text = repo_note_path.read_text(encoding="utf-8")
    assert "watch_status: new" in repo_text
    assert "watch_reactivated_at:" in repo_text

    npm_text = npm_note_path.read_text(encoding="utf-8")
    assert "watch_status: new" in npm_text
    assert "watch_reactivated_at:" in npm_text


def test_sync_watch_candidates_prunes_missing_candidates(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(watch_sync.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(watch_sync.config, "WATCH_CANDIDATES_SUBDIR", "watch-candidates")

    active_repo_path = tmp_path / "23.03.901_active.md"
    active_repo_path.write_text(
        "---\n"
        "type: checkbox\n"
        "source: github-star\n"
        "repo: acme/active\n"
        "repo_url: https://github.com/acme/active\n"
        "---\n\n"
        "# Active\n",
        encoding="utf-8",
    )

    stale_repo_path = tmp_path / "23.03.902_stale.md"
    stale_repo_path.write_text(
        "---\n"
        "type: checkbox\n"
        "source: github-star\n"
        "repo: acme/stale\n"
        "repo_url: https://github.com/acme/stale\n"
        "watch_candidate: true\n"
        "watch_type: repo\n"
        "watch_seed_id: github:acme/stale\n"
        "watch_status: inbox\n"
        "---\n\n"
        "# Stale\n",
        encoding="utf-8",
    )

    stale_npm_note = tmp_path / "watch-candidates" / "npm__stale__abc123.md"
    stale_npm_note.parent.mkdir(parents=True, exist_ok=True)
    stale_npm_note.write_text(
        "---\n"
        "type: watch_candidate\n"
        "source: watch-seed\n"
        "watch_candidate: true\n"
        "watch_type: npm\n"
        "watch_seed_id: npm:@badlogic/stale\n"
        "watch_status: new\n"
        "package: @badlogic/stale\n"
        "---\n\n"
        "# Stale npm\n",
        encoding="utf-8",
    )

    def fake_collect(max_npm_lookups: int = 0) -> dict[str, Any]:
        return {
            "scanned_notes": 2,
            "pi_candidates": 1,
            "repo_candidates": [
                {
                    "id": "github:acme/active",
                    "title": "acme/active",
                    "repo": "acme/active",
                    "repoUrl": "https://github.com/acme/active",
                    "repoNote": "23.03.901_active",
                    "tags": ["pi/extension", "source/github-starred"],
                    "whyWatch": "topic:pi-extension",
                    "discoveredAt": "2026-02-16T00:00:00Z",
                    "owner": "you",
                }
            ],
            "npm_candidates": [],
            "npm_lookups": 0,
        }

    monkeypatch.setattr(watch_candidates, "_collect_watch_seed_candidate_models", fake_collect)

    stats = watch_sync.sync_watch_candidates_to_notes(
        max_npm_lookups=0,
        prune_missing=True,
    )

    assert stats["repo_notes_archived"] == 1
    assert stats["npm_notes_archived"] == 1
    assert stats["watch_notes_archived_total"] == 2

    stale_repo_text = stale_repo_path.read_text(encoding="utf-8")
    assert "watch_status: archived" in stale_repo_text
    assert "watch_archived_at:" in stale_repo_text

    stale_npm_text = stale_npm_note.read_text(encoding="utf-8")
    assert "watch_status: archived" in stale_npm_text
    assert "watch_archived_at:" in stale_npm_text

    active_repo_text = active_repo_path.read_text(encoding="utf-8")
    assert "watch_seed_id: github:acme/active" in active_repo_text
    assert "watch_status: archived" not in active_repo_text
