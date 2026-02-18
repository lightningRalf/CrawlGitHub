from pathlib import Path
from typing import Any

from crawl_github_starred.watch import export as watch_export
from crawl_github_starred.watch.models import WatchCandidate
from crawl_github_starred.watch.models import watch_candidate_confidence_counts
from crawl_github_starred.watch.models import watch_candidate_signal_source_counts


def test_export_watch_seed_files_uses_typed_collection_and_dict_io_boundary(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    repo_candidate = WatchCandidate.from_dict(
        {
            "id": "github:acme/typed-export",
            "type": "repo",
            "source": "github-starred",
            "title": "acme/typed-export",
            "repo": "acme/typed-export",
            "tags": ["pi/extension", "source/github-starred"],
            "whyWatch": "topic:pi-extension",
        }
    )
    npm_candidate = WatchCandidate.from_dict(
        {
            "id": "npm:@badlogic/pi-export",
            "type": "npm",
            "source": "npm",
            "title": "@badlogic/pi-export",
            "package": "@badlogic/pi-export",
            "tags": ["pi/extension", "source/npm"],
            "whyWatch": "derived-from:acme/typed-export",
            "fromRepos": ["acme/typed-export"],
            "fromRepoIds": ["github:acme/typed-export"],
        }
    )

    collect_calls: list[int] = []

    def fake_collect_models(max_npm_lookups: int = 0) -> dict[str, object]:
        collect_calls.append(max_npm_lookups)
        return {
            "scanned_notes": 4,
            "pi_candidates": 2,
            "repo_candidates": [repo_candidate],
            "npm_candidates": [npm_candidate],
            "npm_lookups": 1,
        }

    def fail_collect_dict(**_kwargs: Any) -> dict[str, object]:
        raise AssertionError("Legacy dict collector should not be used by export path.")

    writes: dict[str, list[dict[str, object]]] = {}

    def fake_write_jsonl(path: str, rows: list[dict[str, object]]) -> None:
        writes[path] = rows

    monkeypatch.setattr(
        watch_export.watch_candidates,
        "_collect_watch_seed_candidate_models",
        fake_collect_models,
    )
    monkeypatch.setattr(
        watch_export.watch_candidates,
        "_collect_watch_seed_candidates",
        fail_collect_dict,
    )
    monkeypatch.setattr(watch_export.watch_io, "_write_jsonl", fake_write_jsonl)

    github_output = str(tmp_path / "watch-github.jsonl")
    npm_output = str(tmp_path / "watch-npm.jsonl")

    stats = watch_export.export_watch_seed_files(
        github_output_path=github_output,
        npm_output_path=npm_output,
        max_npm_lookups=7,
    )

    assert collect_calls == [7]
    assert writes[github_output] == [repo_candidate.to_dict()]
    assert writes[npm_output] == [npm_candidate.to_dict()]

    assert stats["repo_candidates"] == 1
    assert stats["npm_candidates"] == 1
    assert stats["repo_confidence_counts"] == watch_candidate_confidence_counts([repo_candidate])
    assert stats["npm_confidence_counts"] == watch_candidate_confidence_counts([npm_candidate])
    assert stats["signal_source_counts"] == watch_candidate_signal_source_counts(
        [repo_candidate, npm_candidate]
    )


def test_export_watch_seed_files_accepts_dict_candidates_from_collection(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    repo_candidate = {
        "id": "github:acme/dict-export",
        "type": "repo",
        "source": "github-starred",
        "title": "acme/dict-export",
        "tags": ["pi/extension", "source/github-starred"],
        "whyWatch": "topic:pi-extension",
        "signalReasons": ["topic:pi-extension"],
    }
    npm_candidate = {
        "id": "npm:@badlogic/pi-dict-export",
        "type": "npm",
        "source": "npm",
        "title": "@badlogic/pi-dict-export",
        "package": "@badlogic/pi-dict-export",
        "tags": ["pi/extension", "source/npm"],
        "whyWatch": "derived-from:acme/dict-export",
        "signalReasons": ["derived-from:acme/dict-export"],
    }

    monkeypatch.setattr(
        watch_export.watch_candidates,
        "_collect_watch_seed_candidate_models",
        lambda **_kwargs: {
            "scanned_notes": 1,
            "pi_candidates": 1,
            "repo_candidates": [repo_candidate],
            "npm_candidates": [npm_candidate],
            "npm_lookups": 0,
        },
    )

    writes: dict[str, list[dict[str, object]]] = {}

    def fake_write_jsonl(path: str, rows: list[dict[str, object]]) -> None:
        writes[path] = rows

    monkeypatch.setattr(watch_export.watch_io, "_write_jsonl", fake_write_jsonl)

    github_output = str(tmp_path / "watch-github.jsonl")
    npm_output = str(tmp_path / "watch-npm.jsonl")

    stats = watch_export.export_watch_seed_files(
        github_output_path=github_output,
        npm_output_path=npm_output,
        max_npm_lookups=0,
    )

    assert stats["repo_candidates"] == 1
    assert stats["npm_candidates"] == 1

    assert writes[github_output][0]["id"] == "github:acme/dict-export"
    assert writes[github_output][0]["signalReasons"] == ["topic:pi-extension"]

    assert writes[npm_output][0]["id"] == "npm:@badlogic/pi-dict-export"
    assert writes[npm_output][0]["signalReasons"] == ["derived-from:acme/dict-export"]
