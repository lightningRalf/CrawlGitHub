from pathlib import Path
from typing import Any

from crawl_github_starred import watchlist_exports


def test_npm_candidate_relative_path_is_stable(monkeypatch: Any) -> None:
    monkeypatch.setattr(watchlist_exports.config, "WATCH_CANDIDATES_SUBDIR", "watch-candidates")

    candidate = {
        "id": "npm:@badlogic/pi",
        "package": "@badlogic/pi",
        "title": "@badlogic/pi",
    }

    path_a = watchlist_exports._npm_candidate_relative_path(candidate)
    path_b = watchlist_exports._npm_candidate_relative_path(candidate)

    assert path_a == path_b
    assert path_a.startswith("watch-candidates/")
    assert path_a.endswith(".md")


def test_sync_watch_candidates_to_notes_updates_repo_and_creates_npm_note(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(watchlist_exports.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(watchlist_exports.config, "WATCH_CANDIDATES_SUBDIR", "watch-candidates")

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

    monkeypatch.setattr(watchlist_exports, "_collect_watch_seed_candidates", fake_collect)

    stats = watchlist_exports.sync_watch_candidates_to_notes(max_npm_lookups=0)

    assert stats["repo_notes_updated"] == 1
    assert stats["npm_notes_created"] == 1

    repo_text = repo_note_path.read_text(encoding="utf-8")
    assert "watch_candidate: true" in repo_text or 'watch_candidate: "true"' in repo_text
    assert "watch_type: repo" in repo_text
    assert "watch_seed_id: github:acme/rocket" in repo_text

    watch_dir = tmp_path / "watch-candidates"
    npm_files = list(watch_dir.glob("*.md"))
    assert len(npm_files) == 1

    npm_text = npm_files[0].read_text(encoding="utf-8")
    assert "type: watch_candidate" in npm_text
    assert "watch_type: npm" in npm_text
    assert "package: @badlogic/pi" in npm_text
