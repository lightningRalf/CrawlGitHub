import sys
from pathlib import Path
from typing import Any

import pytest

from crawl_github_starred import main


def test_watch_sync_subcommand_runs_local_sync_only(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(main.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(main.config, "LOG_FILE", "test.log")
    monkeypatch.setattr(main.config, "WATCH_TELEMETRY_FILE", "")

    calls = {"sync": 0, "export": 0}

    def fake_sync(max_npm_lookups: int = 0, prune_missing: bool = False) -> dict[str, object]:
        calls["sync"] += 1
        assert max_npm_lookups == 0
        assert prune_missing is False
        return {}

    def fake_export(
        github_output_path: str | None,
        npm_output_path: str | None,
        max_npm_lookups: int = 0,
    ) -> dict[str, object]:
        calls["export"] += 1
        return {}

    monkeypatch.setattr(main.watchlist_exports, "sync_watch_candidates_to_notes", fake_sync)
    monkeypatch.setattr(main.watchlist_exports, "export_watch_seed_files", fake_export)

    monkeypatch.setattr(
        sys,
        "argv",
        ["crawl-github", "watch", "sync", "--skip-bases", "--max-npm-lookups", "0"],
    )

    main.main()

    assert calls["sync"] == 1
    assert calls["export"] == 0


def test_watch_export_subcommand_runs_local_export_only(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(main.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(main.config, "LOG_FILE", "test.log")
    monkeypatch.setattr(main.config, "WATCH_TELEMETRY_FILE", "")

    calls = {"sync": 0, "export": 0}

    def fake_sync(max_npm_lookups: int = 0, prune_missing: bool = False) -> dict[str, object]:
        calls["sync"] += 1
        return {}

    expected_github_path = str(tmp_path / "watch-github.jsonl")
    expected_npm_path = str(tmp_path / "watch-npm.jsonl")

    def fake_export(
        github_output_path: str | None,
        npm_output_path: str | None,
        max_npm_lookups: int = 0,
    ) -> dict[str, object]:
        calls["export"] += 1
        assert github_output_path == expected_github_path
        assert npm_output_path == expected_npm_path
        assert max_npm_lookups == 3
        return {}

    monkeypatch.setattr(main.watchlist_exports, "sync_watch_candidates_to_notes", fake_sync)
    monkeypatch.setattr(main.watchlist_exports, "export_watch_seed_files", fake_export)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crawl-github",
            "watch",
            "export",
            "--export-watch-seeds",
            expected_github_path,
            "--export-npm-seeds",
            expected_npm_path,
            "--max-npm-lookups",
            "3",
        ],
    )

    main.main()

    assert calls["sync"] == 0
    assert calls["export"] == 1


def test_crawl_subcommand_keeps_legacy_local_only_flag_flow(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(main.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(main.config, "LOG_FILE", "test.log")
    monkeypatch.setattr(main.config, "WATCH_TELEMETRY_FILE", "")

    calls = {"sync": 0, "export": 0}

    def fake_sync(max_npm_lookups: int = 0, prune_missing: bool = False) -> dict[str, object]:
        calls["sync"] += 1
        assert max_npm_lookups == 0
        return {}

    def fake_export(
        github_output_path: str | None,
        npm_output_path: str | None,
        max_npm_lookups: int = 0,
    ) -> dict[str, object]:
        calls["export"] += 1
        return {}

    monkeypatch.setattr(main.watchlist_exports, "sync_watch_candidates_to_notes", fake_sync)
    monkeypatch.setattr(main.watchlist_exports, "export_watch_seed_files", fake_export)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crawl-github",
            "crawl",
            "--export-seeds-only",
            "--sync-watch-candidates",
            "--max-npm-lookups",
            "0",
            "--skip-bases",
        ],
    )

    main.main()

    assert calls["sync"] == 1
    assert calls["export"] == 0


def test_legacy_flag_only_invocation_is_backward_compatible(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(main.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(main.config, "LOG_FILE", "test.log")
    monkeypatch.setattr(main.config, "WATCH_TELEMETRY_FILE", "")

    calls = {"sync": 0, "export": 0}

    def fake_sync(max_npm_lookups: int = 0, prune_missing: bool = False) -> dict[str, object]:
        calls["sync"] += 1
        assert max_npm_lookups == 0
        return {}

    def fake_export(
        github_output_path: str | None,
        npm_output_path: str | None,
        max_npm_lookups: int = 0,
    ) -> dict[str, object]:
        calls["export"] += 1
        return {}

    monkeypatch.setattr(main.watchlist_exports, "sync_watch_candidates_to_notes", fake_sync)
    monkeypatch.setattr(main.watchlist_exports, "export_watch_seed_files", fake_export)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "crawl-github",
            "--export-seeds-only",
            "--sync-watch-candidates",
            "--max-npm-lookups",
            "0",
            "--skip-bases",
        ],
    )

    main.main()

    assert calls["sync"] == 1
    assert calls["export"] == 0


def test_watch_command_requires_subcommand(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(main.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(main.config, "LOG_FILE", "test.log")

    monkeypatch.setattr(sys, "argv", ["crawl-github", "watch"])

    with pytest.raises(SystemExit):
        main.main()


def test_top_level_help_shows_subcommands(
    monkeypatch: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["crawl-github", "--help"])

    with pytest.raises(SystemExit):
        main.main()

    captured = capsys.readouterr()
    assert "{crawl,watch}" in captured.out
