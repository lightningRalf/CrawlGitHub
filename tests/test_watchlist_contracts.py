from crawl_github_starred.watch import candidates as watch_candidates
from crawl_github_starred.watch.models import WatchCandidate


ALLOWED_CONFIDENCE = {"low", "medium", "high"}


def test_repo_candidate_contract_includes_signal_metadata() -> None:
    candidate_model = watch_candidates._build_repo_candidate(
        note_path="C:/tmp/23.03.123_rocket.md",
        frontmatter={
            "repo": "acme/rocket",
            "repo_name": "rocket",
            "repo_url": "https://github.com/acme/rocket",
            "last_seen_date": "2026-02-17",
        },
        tags=["pi/extension"],
        reasons=["topic:pi-extension", "signal:pi-extension"],
        fallback_discovered_at="2026-02-17T00:00:00Z",
    )

    candidate = candidate_model.to_dict()

    required = {
        "id",
        "type",
        "source",
        "title",
        "tags",
        "whyWatch",
        "signalReasons",
        "signalSources",
        "signalCount",
        "confidence",
        "discoveredAt",
        "repo",
        "repoUrl",
        "repoNote",
    }
    assert required.issubset(candidate.keys())

    assert candidate["type"] == "repo"
    assert candidate["source"] == "github-starred"
    assert candidate["signalReasons"] == ["topic:pi-extension", "signal:pi-extension"]
    assert candidate["signalSources"] == ["topic", "signal"]
    assert candidate["signalCount"] == 2
    assert candidate["confidence"] in ALLOWED_CONFIDENCE


def test_npm_candidate_contract_includes_signal_metadata() -> None:
    repo_candidate = {
        "id": "github:acme/rocket",
        "title": "acme/rocket",
        "repoUrl": "https://github.com/acme/rocket",
        "tags": ["pi/extension", "source/github-starred"],
    }

    candidate_model = watch_candidates._build_npm_candidate(
        package_name="@badlogic/pi",
        repo_candidate=repo_candidate,
        fallback_discovered_at="2026-02-17T00:00:00Z",
    )
    candidate = candidate_model.to_dict()

    required = {
        "id",
        "type",
        "source",
        "title",
        "tags",
        "whyWatch",
        "signalReasons",
        "signalSources",
        "signalCount",
        "confidence",
        "discoveredAt",
        "package",
        "fromRepos",
    }
    assert required.issubset(candidate.keys())

    assert candidate["type"] == "npm"
    assert candidate["source"] == "npm"
    assert candidate["signalReasons"] == ["derived-from:acme/rocket"]
    assert candidate["signalSources"] == ["derived"]
    assert candidate["signalCount"] == 1
    assert candidate["confidence"] in ALLOWED_CONFIDENCE


def test_repo_candidate_builder_returns_typed_model() -> None:
    payload = {
        "note_path": "C:/tmp/23.03.123_rocket.md",
        "frontmatter": {
            "repo": "acme/rocket",
            "repo_name": "rocket",
            "repo_url": "https://github.com/acme/rocket",
            "last_seen_date": "2026-02-17",
        },
        "tags": ["pi/extension"],
        "reasons": ["topic:pi-extension", "signal:pi-extension"],
        "fallback_discovered_at": "2026-02-17T00:00:00Z",
    }

    candidate_model = watch_candidates._build_repo_candidate(**payload)

    assert isinstance(candidate_model, WatchCandidate)
    assert candidate_model.to_dict()["id"] == "github:acme/rocket"


def test_npm_candidate_builder_returns_typed_model() -> None:
    repo_candidate = {
        "id": "github:acme/rocket",
        "title": "acme/rocket",
        "repoUrl": "https://github.com/acme/rocket",
        "tags": ["pi/extension", "source/github-starred"],
    }

    candidate_model = watch_candidates._build_npm_candidate(
        package_name="@badlogic/pi",
        repo_candidate=repo_candidate,
        fallback_discovered_at="2026-02-17T00:00:00Z",
    )

    assert isinstance(candidate_model, WatchCandidate)
    assert candidate_model.to_dict()["id"] == "npm:@badlogic/pi"
