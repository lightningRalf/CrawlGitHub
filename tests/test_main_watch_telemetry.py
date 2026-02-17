import json
from pathlib import Path
from typing import Any

from crawl_github_starred import main


def test_write_watch_telemetry_is_noop_when_disabled(monkeypatch: Any) -> None:
    monkeypatch.setattr(main.config, "WATCH_TELEMETRY_FILE", "")

    written = main._write_watch_telemetry("watch-candidate-sync", {"repo_candidates": 1})
    assert written is None


def test_write_watch_telemetry_writes_json_payload(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(main.config, "WORKING_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(main.config, "WATCH_TELEMETRY_FILE", "telemetry/watch-latest.json")

    written = main._write_watch_telemetry(
        "watch-seed-export",
        {
            "repo_candidates": 2,
            "npm_candidates": 3,
            "repo_confidence_counts": {"medium": 2},
        },
    )

    assert written is not None
    written_path = Path(str(written))
    assert written_path.exists()

    payload = json.loads(written_path.read_text(encoding="utf-8"))
    assert payload["event"] == "watch-seed-export"
    assert payload["working_directory"] == str(tmp_path)
    assert payload["stats"]["repo_candidates"] == 2
    assert payload["stats"]["npm_candidates"] == 3
    assert payload["stats"]["repo_confidence_counts"] == {"medium": 2}
    assert payload["written_at"].endswith("Z")
