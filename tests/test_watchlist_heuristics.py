from pathlib import Path
from typing import Any

from crawl_github_starred.watch import candidates as watch_candidates
from crawl_github_starred.watch import npm as watch_npm
from crawl_github_starred.watch import signals as watch_signals
from crawl_github_starred.watch.models import WatchCandidate


def test_contains_term_uses_word_boundaries() -> None:
    assert watch_signals._contains_term("pi extension toolkit", "pi extension") is True
    assert watch_signals._contains_term("api extension toolkit", "pi extension") is False
    assert watch_signals._contains_term("acme/pi-extension-kit", "pi-extension") is True


def test_classify_repo_candidate_avoids_api_substring_false_positive() -> None:
    tags, reasons = watch_signals._classify_repo_candidate(
        frontmatter={
            "repo": "acme/api-toolbox",
            "repo_name": "api-toolbox",
            "repo_description": "API extension helpers",
            "topics": "tooling,api",
        },
        body="# API extension docs",
        readme_text="Install API extension support",
    )

    assert tags == []
    assert reasons == []


def test_classify_repo_candidate_keeps_recall_for_explicit_pi_marker() -> None:
    tags, reasons = watch_signals._classify_repo_candidate(
        frontmatter={
            "repo": "acme/pi-extension-kit",
            "repo_name": "pi-extension-kit",
            "repo_description": "Toolkit",
            "topics": "tooling",
        },
        body="# Docs",
        readme_text="",
    )

    assert "pi/extension" in tags
    assert any(reason in reasons for reason in ["signal:pi-extension", "phrase:pi extension"])


def test_classify_repo_candidate_does_not_use_weak_readme_phrase_alone() -> None:
    tags, reasons = watch_signals._classify_repo_candidate(
        frontmatter={
            "repo": "acme/unknown",
            "repo_name": "unknown",
            "repo_description": "Generic toolkit",
            "topics": "tooling",
        },
        body="# Docs",
        readme_text="Build a Raspberry Pi extension with this toolkit",
    )

    assert tags == []
    assert reasons == []


def test_classify_repo_candidate_keeps_recall_for_strong_readme_phrase() -> None:
    tags, reasons = watch_signals._classify_repo_candidate(
        frontmatter={
            "repo": "acme/unknown",
            "repo_name": "unknown",
            "repo_description": "Generic toolkit",
            "topics": "tooling",
        },
        body="# Docs",
        readme_text="This plugin runs inside the Pi coding agent runtime",
    )

    assert "pi/extension" in tags
    assert "phrase:pi coding agent" in reasons


def test_classify_repo_candidate_anchor_is_conservative() -> None:
    tags, reasons = watch_signals._classify_repo_candidate(
        frontmatter={
            "repo": "acme/raspberry-pi-tools",
            "repo_name": "raspberry-pi-tools",
            "repo_description": "Utilities for Raspberry Pi",
            "topics": "raspberry-pi,hardware",
        },
        body="# Raspberry Pi tools",
        readme_text="",
    )

    assert tags == []
    assert reasons == []


def test_classify_repo_candidate_anchor_keeps_core_pi_repo_recall() -> None:
    tags, reasons = watch_signals._classify_repo_candidate(
        frontmatter={
            "repo": "badlogic/pi",
            "repo_name": "pi",
            "repo_description": "Core runtime repository",
            "topics": "",
        },
        body="# Pi",
        readme_text="",
    )

    assert "pi/extension" in tags
    assert "repo:badlogic/pi" in reasons or "repo-name:pi" in reasons


def test_normalize_package_token_handles_versions_and_invalid_tokens() -> None:
    assert watch_npm._normalize_package_token("npm:@badlogic/pi") == "@badlogic/pi"
    assert watch_npm._normalize_package_token("@badlogic/pi@1.2.3") == "@badlogic/pi"
    assert watch_npm._normalize_package_token("react@18") == "react"
    assert watch_npm._normalize_package_token("-D") is None
    assert watch_npm._normalize_package_token("https://registry.npmjs.org/foo") is None


def test_merge_repo_candidate_deduplicates_tags_and_reasons() -> None:
    store: dict[str, WatchCandidate] = {}

    watch_candidates._merge_repo_candidate(
        store,
        {
            "id": "github:acme/rocket",
            "tags": ["pi/extension", "source/github-starred"],
            "whyWatch": "topic:pi-extension",
        },
    )
    watch_candidates._merge_repo_candidate(
        store,
        {
            "id": "github:acme/rocket",
            "tags": ["pi/skill", "source/github-starred"],
            "whyWatch": "signal:pi-coding-agent",
        },
    )
    watch_candidates._merge_repo_candidate(
        store,
        {
            "id": "github:acme/rocket",
            "tags": ["pi/skill"],
            "whyWatch": "signal:pi-coding-agent",
        },
    )

    merged = store["github:acme/rocket"].to_dict()
    assert merged["tags"] == ["pi/extension", "pi/skill", "source/github-starred"]
    assert merged["whyWatch"] == "topic:pi-extension; signal:pi-coding-agent"


def test_merge_repo_candidate_accepts_typed_models() -> None:
    store: dict[str, WatchCandidate] = {}

    watch_candidates._merge_repo_candidate(
        store,
        WatchCandidate.from_dict(
            {
                "id": "github:acme/typed",
                "type": "repo",
                "source": "github-starred",
                "title": "acme/typed",
                "tags": ["pi/extension", "source/github-starred"],
                "whyWatch": "topic:pi-extension",
            }
        ),
    )

    watch_candidates._merge_repo_candidate(
        store,
        {
            "id": "github:acme/typed",
            "tags": ["pi/skill"],
            "whyWatch": "signal:pi-coding-agent",
        },
    )

    merged = store["github:acme/typed"].to_dict()
    assert merged["tags"] == ["pi/extension", "pi/skill", "source/github-starred"]
    assert merged["whyWatch"] == "topic:pi-extension; signal:pi-coding-agent"


def test_merge_npm_candidate_deduplicates_from_repos_and_why_fragments() -> None:
    store: dict[str, WatchCandidate] = {}

    watch_candidates._merge_npm_candidate(
        store,
        WatchCandidate.from_dict(
            {
                "id": "npm:@badlogic/pi",
                "type": "npm",
                "source": "npm",
                "title": "@badlogic/pi",
                "tags": ["pi/extension", "source/npm"],
                "fromRepos": ["acme/rocket"],
                "fromRepoIds": ["github:acme/rocket"],
                "whyWatch": "derived-from:acme/rocket",
            }
        ),
    )
    watch_candidates._merge_npm_candidate(
        store,
        {
            "id": "npm:@badlogic/pi",
            "tags": ["pi/theme", "source/npm"],
            "fromRepos": ["acme/rocket", "acme/theme"],
            "fromRepoIds": ["github:acme/rocket", "github:acme/theme"],
            "whyWatch": "derived-from:acme/theme",
        },
    )
    watch_candidates._merge_npm_candidate(
        store,
        {
            "id": "npm:@badlogic/pi",
            "tags": ["pi/theme"],
            "fromRepos": ["acme/theme"],
            "fromRepoIds": ["github:acme/theme"],
            "whyWatch": "derived-from:acme/theme",
        },
    )

    merged = store["npm:@badlogic/pi"].to_dict()
    assert merged["tags"] == ["pi/extension", "pi/theme", "source/npm"]
    assert merged["fromRepos"] == ["acme/rocket", "acme/theme"]
    assert merged["fromRepoIds"] == ["github:acme/rocket", "github:acme/theme"]

    why_watch = str(merged["whyWatch"])
    assert why_watch.count("derived-from:acme/rocket") == 1
    assert why_watch.count("derived-from:acme/theme") == 1


def test_merge_repo_candidate_merges_explicit_signal_sources() -> None:
    store: dict[str, WatchCandidate] = {}

    watch_candidates._merge_repo_candidate(
        store,
        {
            "id": "github:acme/rocket",
            "tags": ["pi/extension", "source/github-starred"],
            "signalReasons": ["topic:pi-extension"],
            "signalSources": ["topic"],
            "whyWatch": "topic:pi-extension",
        },
    )
    watch_candidates._merge_repo_candidate(
        store,
        {
            "id": "github:acme/rocket",
            "tags": ["pi/skill", "source/github-starred"],
            "signalReasons": ["signal:pi-coding-agent"],
            "signalSources": ["path"],
            "whyWatch": "signal:pi-coding-agent",
        },
    )

    merged = store["github:acme/rocket"].to_dict()
    assert merged["signalSources"] == ["topic", "path"]
    assert merged["signalCount"] == 2


def test_merge_npm_candidate_merges_explicit_signal_sources() -> None:
    store: dict[str, WatchCandidate] = {}

    watch_candidates._merge_npm_candidate(
        store,
        {
            "id": "npm:@badlogic/pi",
            "tags": ["pi/extension", "source/npm"],
            "fromRepos": ["acme/rocket"],
            "fromRepoIds": ["github:acme/rocket"],
            "signalReasons": ["derived-from:acme/rocket"],
            "signalSources": ["derived"],
            "whyWatch": "derived-from:acme/rocket",
        },
    )
    watch_candidates._merge_npm_candidate(
        store,
        {
            "id": "npm:@badlogic/pi",
            "tags": ["pi/theme", "source/npm"],
            "fromRepos": ["acme/theme"],
            "fromRepoIds": ["github:acme/theme"],
            "signalReasons": ["derived-from:acme/theme"],
            "signalSources": ["npm-keyword"],
            "whyWatch": "derived-from:acme/theme",
        },
    )

    merged = store["npm:@badlogic/pi"].to_dict()
    assert merged["signalSources"] == ["derived", "npm-keyword"]
    assert merged["signalCount"] == 2


def test_signal_sources_and_confidence_are_derived_from_reason_fragments() -> None:
    reasons = [
        "topic:pi-extension",
        "readme-path:extensions/*.{ts,js}",
        "phrase:pi coding agent",
    ]

    sources = watch_signals._signal_sources_from_reasons(reasons)
    assert sources == ["topic", "phrase", "path"]

    confidence = watch_signals._watch_confidence(
        tags=["pi/extension", "source/github-starred"],
        reasons=reasons,
    )
    assert confidence == "high"


def test_populate_signal_metadata_builds_structured_fields() -> None:
    candidate = {
        "tags": ["pi/extension", "source/npm"],
        "whyWatch": "derived-from:acme/rocket; npm-keyword:pi-extension",
    }

    watch_signals._populate_signal_metadata(candidate)

    assert candidate["signalReasons"] == [
        "derived-from:acme/rocket",
        "npm-keyword:pi-extension",
    ]
    assert candidate["signalSources"] == ["derived", "npm-keyword"]
    assert candidate["signalCount"] == 2
    assert candidate["confidence"] in {"medium", "high"}


def test_confidence_and_source_distribution_helpers() -> None:
    candidates = [
        {
            "tags": ["pi/extension", "source/github-starred"],
            "signalReasons": ["topic:pi-extension"],
        },
        {
            "tags": ["pi/extension", "source/npm"],
            "signalReasons": ["derived-from:acme/rocket", "npm-keyword:pi-extension"],
        },
    ]

    confidence_counts = watch_signals._confidence_counts(candidates)
    source_counts = watch_signals._signal_source_counts(candidates)

    assert confidence_counts == {"medium": 2}
    assert source_counts == {"topic": 1, "derived": 1, "npm-keyword": 1}


def test_apply_npm_metadata_accepts_typed_candidate() -> None:
    candidate = WatchCandidate.from_dict(
        {
            "id": "npm:@badlogic/pi",
            "type": "npm",
            "source": "npm",
            "title": "@badlogic/pi",
            "package": "@badlogic/pi",
            "tags": ["source/npm"],
            "whyWatch": "derived-from:acme/rocket",
            "signalReasons": ["derived-from:acme/rocket"],
            "signalSources": ["derived"],
            "signalCount": 1,
            "confidence": "low",
            "owner": "you",
            "status": "new",
            "discoveredAt": "2026-02-17T00:00:00Z",
        }
    )

    updated = watch_npm._apply_npm_metadata(
        candidate,
        {
            "dist-tags": {"latest": "1.2.3"},
            "versions": {
                "1.2.3": {
                    "description": "Pi extension runtime",
                    "keywords": ["pi-extension", "tooling"],
                }
            },
        },
    )

    assert updated["npmLatestVersion"] == "1.2.3"
    assert updated["npmDescription"] == "Pi extension runtime"
    assert updated["npmKeywords"] == ["pi-extension", "tooling"]
    assert "pi/extension" in updated["tags"]
    assert "npm-keyword:pi-extension" in updated["signalReasons"]

    candidate_payload = candidate.to_dict()
    assert candidate_payload["npmLatestVersion"] == "1.2.3"
    assert candidate_payload["npmDescription"] == "Pi extension runtime"


def test_enrich_npm_candidates_accepts_typed_candidate_list(monkeypatch: Any) -> None:
    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return {
                "dist-tags": {"latest": "9.9.9"},
                "versions": {
                    "9.9.9": {
                        "description": "typed enrichment",
                        "keywords": ["pi-extension"],
                    }
                },
            }

    monkeypatch.setattr(watch_npm.requests, "get", lambda *_args, **_kwargs: _FakeResponse())
    monkeypatch.setattr(watch_npm.config, "REQUEST_DELAY_SECONDS", 0)

    candidates: list[WatchCandidate] = [
        WatchCandidate.from_dict(
            {
                "id": "npm:@badlogic/pi",
                "type": "npm",
                "source": "npm",
                "title": "@badlogic/pi",
                "package": "@badlogic/pi",
                "tags": ["source/npm"],
                "whyWatch": "derived-from:acme/rocket",
            }
        )
    ]

    lookups = watch_npm._enrich_npm_candidates(candidates, max_npm_lookups=1)

    assert lookups == 1
    assert isinstance(candidates[0], WatchCandidate)
    enriched_payload = candidates[0].to_dict()
    assert enriched_payload["npmLatestVersion"] == "9.9.9"
    assert enriched_payload["npmDescription"] == "typed enrichment"


def test_collect_watch_seed_candidates_uses_typed_enrichment_boundary(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(watch_candidates.watch_io.config, "WORKING_DIRECTORY", str(tmp_path))

    readme_relative_path = "23.03_READMEs/acme__typed__abc123.md"
    readme_path = tmp_path / readme_relative_path
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text(
        "# README\n\n"
        "npm install @badlogic/pi\n",
        encoding="utf-8",
    )

    repo_note_path = tmp_path / "23.03.777_typed.md"
    repo_note_path.write_text(
        "---\n"
        "type: checkbox\n"
        "source: github-star\n"
        "repo: acme/typed\n"
        "repo_name: typed\n"
        "repo_url: https://github.com/acme/typed\n"
        "topics: pi-extension\n"
        f"readme_note: {readme_relative_path}\n"
        "---\n\n"
        "# Repo\n",
        encoding="utf-8",
    )

    candidate_types: list[type[object]] = []

    def fake_enrich(
        candidates: list[WatchCandidate | dict[str, Any]],
        max_npm_lookups: int,
    ) -> int:
        candidate_types.extend(type(candidate) for candidate in candidates)
        return 0

    monkeypatch.setattr(watch_npm, "_enrich_npm_candidates", fake_enrich)

    collected = watch_candidates._collect_watch_seed_candidates(max_npm_lookups=5)

    assert candidate_types
    assert all(candidate_type is WatchCandidate for candidate_type in candidate_types)
    assert collected["repo_candidates"][0]["id"] == "github:acme/typed"
    assert collected["npm_candidates"][0]["id"] == "npm:@badlogic/pi"
