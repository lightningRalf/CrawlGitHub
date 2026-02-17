from crawl_github_starred.watch.models import WatchCandidate
from crawl_github_starred.watch.models import as_watch_candidate
from crawl_github_starred.watch.models import candidate_reason_fragments
from crawl_github_starred.watch.models import coerce_watch_candidate_dict
from crawl_github_starred.watch.models import refresh_watch_candidate_signal_metadata


def test_repo_watch_candidate_model_roundtrip_preserves_contract_payload() -> None:
    payload = {
        "id": "github:acme/rocket",
        "type": "repo",
        "source": "github-starred",
        "title": "acme/rocket",
        "starred": True,
        "tags": ["pi/extension", "source/github-starred"],
        "whyWatch": "topic:pi-extension; signal:pi-extension",
        "signalReasons": ["topic:pi-extension", "signal:pi-extension"],
        "signalSources": ["topic", "signal"],
        "signalCount": 2,
        "confidence": "high",
        "status": "new",
        "owner": "you",
        "discoveredAt": "2026-02-17T00:00:00Z",
        "repo": "acme/rocket",
        "repoUrl": "https://github.com/acme/rocket",
        "repoNote": "23.03.111_rocket",
        "customField": "keep-me",
    }

    candidate = WatchCandidate.from_dict(payload)

    assert candidate.type == "repo"
    assert candidate.repo == "acme/rocket"
    assert candidate.repo_note == "23.03.111_rocket"

    assert candidate.to_dict() == payload


def test_npm_watch_candidate_model_roundtrip_preserves_contract_payload() -> None:
    payload = {
        "id": "npm:@badlogic/pi",
        "type": "npm",
        "source": "npm",
        "title": "@badlogic/pi",
        "starred": False,
        "tags": ["pi/extension", "source/npm"],
        "whyWatch": "derived-from:acme/rocket",
        "signalReasons": ["derived-from:acme/rocket"],
        "signalSources": ["derived"],
        "signalCount": 1,
        "confidence": "low",
        "status": "new",
        "owner": "you",
        "discoveredAt": "2026-02-17T00:00:00Z",
        "package": "@badlogic/pi",
        "fromRepos": ["acme/rocket"],
        "fromRepoIds": ["github:acme/rocket"],
        "npmLatestVersion": "1.2.3",
        "npmKeywords": ["pi-extension"],
    }

    candidate = WatchCandidate.from_dict(payload)

    assert candidate.type == "npm"
    assert candidate.package == "@badlogic/pi"
    assert candidate.from_repo_ids == ["github:acme/rocket"]

    assert candidate.to_dict() == payload


def test_coerce_watch_candidate_dict_adds_safe_defaults_for_sparse_payload() -> None:
    payload = {
        "id": "npm:@badlogic/pi",
        "type": "npm",
        "source": "npm",
        "title": "@badlogic/pi",
    }

    coerced = coerce_watch_candidate_dict(payload)

    assert coerced["id"] == payload["id"]
    assert coerced["type"] == payload["type"]
    assert coerced["source"] == payload["source"]
    assert coerced["title"] == payload["title"]

    assert coerced["status"] == "new"
    assert coerced["owner"] == "you"
    assert coerced["signalCount"] == 0
    assert "fromRepos" not in coerced
    assert "fromRepoIds" not in coerced


def test_as_watch_candidate_returns_existing_instance() -> None:
    candidate = WatchCandidate.from_dict(
        {
            "id": "github:acme/rocket",
            "type": "repo",
            "source": "github-starred",
            "title": "acme/rocket",
        }
    )

    assert as_watch_candidate(candidate) is candidate


def test_candidate_reason_fragments_falls_back_to_why_watch() -> None:
    candidate = WatchCandidate.from_dict(
        {
            "id": "npm:@badlogic/pi",
            "type": "npm",
            "source": "npm",
            "title": "@badlogic/pi",
            "whyWatch": "derived-from:acme/rocket; npm-keyword:pi-extension",
        }
    )

    assert candidate_reason_fragments(candidate) == [
        "derived-from:acme/rocket",
        "npm-keyword:pi-extension",
    ]


def test_refresh_watch_candidate_signal_metadata_populates_fields() -> None:
    candidate = WatchCandidate.from_dict(
        {
            "id": "github:acme/rocket",
            "type": "repo",
            "source": "github-starred",
            "title": "acme/rocket",
            "tags": ["pi/extension", "source/github-starred"],
            "whyWatch": "topic:pi-extension; signal:pi-extension",
            "confidence": "",
        }
    )

    refresh_watch_candidate_signal_metadata(candidate)

    assert candidate.signal_reasons == ["topic:pi-extension", "signal:pi-extension"]
    assert candidate.signal_sources == ["topic", "signal"]
    assert candidate.signal_count == 2
    assert candidate.confidence in {"medium", "high"}
