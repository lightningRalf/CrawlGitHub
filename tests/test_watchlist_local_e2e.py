from pathlib import Path
from typing import Any

from crawl_github_starred import bases_files
from crawl_github_starred import watchlist_exports


def test_local_only_watch_sync_prune_and_base_generation(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(watchlist_exports.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(watchlist_exports.config, "WATCH_CANDIDATES_SUBDIR", "watch-candidates")

    monkeypatch.setattr(bases_files.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(bases_files.config, "WATCH_CANDIDATES_BASE_FILE", "watch-candidates.base")

    readme_relative_path = "23.03_READMEs/acme__rocket-e2e__abc123.md"
    readme_path = tmp_path / readme_relative_path
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text(
        "# README\n\n"
        "Install:\n\n"
        "npm install @badlogic/pi\n",
        encoding="utf-8",
    )

    repo_note_path = tmp_path / "23.03.111_rocket-e2e.md"
    repo_note_path.write_text(
        "---\n"
        "type: checkbox\n"
        "source: github-star\n"
        "repo: acme/rocket-e2e\n"
        "repo_name: rocket-e2e\n"
        "repo_url: https://github.com/acme/rocket-e2e\n"
        "topics: pi-extension, tooling\n"
        f"readme_note: {readme_relative_path}\n"
        "---\n\n"
        "# Repo note\n",
        encoding="utf-8",
    )

    stats_first = watchlist_exports.sync_watch_candidates_to_notes(
        max_npm_lookups=0,
        prune_missing=True,
    )

    assert stats_first["repo_candidates"] == 1
    assert stats_first["npm_candidates"] == 1
    assert stats_first["repo_notes_archived"] == 0
    assert stats_first["npm_notes_archived"] == 0

    repo_text_after_first_sync = repo_note_path.read_text(encoding="utf-8")
    assert "watch_status: new" in repo_text_after_first_sync
    assert "watch_signal_sources:" in repo_text_after_first_sync
    assert "watch_signal_count:" in repo_text_after_first_sync
    assert "watch_confidence:" in repo_text_after_first_sync

    watch_dir = tmp_path / "watch-candidates"
    npm_notes = sorted(watch_dir.glob("*.md"))
    assert len(npm_notes) == 1

    npm_note_path = npm_notes[0]
    npm_text_after_first_sync = npm_note_path.read_text(encoding="utf-8")
    assert "watch_type: npm" in npm_text_after_first_sync
    assert "watch_status: new" in npm_text_after_first_sync

    # Remove the strong pi marker; second run should archive stale candidates.
    repo_note_path.write_text(
        repo_text_after_first_sync.replace("pi-extension", "tooling-only"),
        encoding="utf-8",
    )

    stats_second = watchlist_exports.sync_watch_candidates_to_notes(
        max_npm_lookups=0,
        prune_missing=True,
    )

    assert stats_second["repo_candidates"] == 0
    assert stats_second["npm_candidates"] == 0
    assert stats_second["repo_notes_archived"] == 1
    assert stats_second["npm_notes_archived"] == 1

    repo_text_after_prune = repo_note_path.read_text(encoding="utf-8")
    assert "watch_status: archived" in repo_text_after_prune
    assert "watch_archived_at:" in repo_text_after_prune

    npm_text_after_prune = npm_note_path.read_text(encoding="utf-8")
    assert "watch_status: archived" in npm_text_after_prune
    assert "watch_archived_at:" in npm_text_after_prune

    # Third run is idempotent: already-archived stale notes stay unchanged.
    stats_third = watchlist_exports.sync_watch_candidates_to_notes(
        max_npm_lookups=0,
        prune_missing=True,
    )
    assert stats_third["repo_notes_archived"] == 0
    assert stats_third["npm_notes_archived"] == 0

    base_path = Path(bases_files.write_watch_candidates_base())
    assert base_path.exists()

    base_text = base_path.read_text(encoding="utf-8")
    assert "name: Needs triage" in base_text
    assert "name: Archived" in base_text
    assert "watch_signal_sources" in base_text
    assert "watch_signal_count" in base_text
    assert "watch_confidence" in base_text
