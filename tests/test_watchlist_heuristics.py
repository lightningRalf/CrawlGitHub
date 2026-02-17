from crawl_github_starred import watchlist_exports


def test_contains_term_uses_word_boundaries() -> None:
    assert watchlist_exports._contains_term("pi extension toolkit", "pi extension") is True
    assert watchlist_exports._contains_term("api extension toolkit", "pi extension") is False
    assert watchlist_exports._contains_term("acme/pi-extension-kit", "pi-extension") is True


def test_classify_repo_candidate_avoids_api_substring_false_positive() -> None:
    tags, reasons = watchlist_exports._classify_repo_candidate(
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
    tags, reasons = watchlist_exports._classify_repo_candidate(
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
    tags, reasons = watchlist_exports._classify_repo_candidate(
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
    tags, reasons = watchlist_exports._classify_repo_candidate(
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
    tags, reasons = watchlist_exports._classify_repo_candidate(
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
    tags, reasons = watchlist_exports._classify_repo_candidate(
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
    assert watchlist_exports._normalize_package_token("npm:@badlogic/pi") == "@badlogic/pi"
    assert watchlist_exports._normalize_package_token("@badlogic/pi@1.2.3") == "@badlogic/pi"
    assert watchlist_exports._normalize_package_token("react@18") == "react"
    assert watchlist_exports._normalize_package_token("-D") is None
    assert watchlist_exports._normalize_package_token("https://registry.npmjs.org/foo") is None


def test_merge_repo_candidate_deduplicates_tags_and_reasons() -> None:
    store: dict[str, dict[str, object]] = {}

    watchlist_exports._merge_repo_candidate(
        store,
        {
            "id": "github:acme/rocket",
            "tags": ["pi/extension", "source/github-starred"],
            "whyWatch": "topic:pi-extension",
        },
    )
    watchlist_exports._merge_repo_candidate(
        store,
        {
            "id": "github:acme/rocket",
            "tags": ["pi/skill", "source/github-starred"],
            "whyWatch": "signal:pi-coding-agent",
        },
    )
    watchlist_exports._merge_repo_candidate(
        store,
        {
            "id": "github:acme/rocket",
            "tags": ["pi/skill"],
            "whyWatch": "signal:pi-coding-agent",
        },
    )

    merged = store["github:acme/rocket"]
    assert merged["tags"] == ["pi/extension", "pi/skill", "source/github-starred"]
    assert merged["whyWatch"] == "topic:pi-extension; signal:pi-coding-agent"


def test_merge_npm_candidate_deduplicates_from_repos_and_why_fragments() -> None:
    store: dict[str, dict[str, object]] = {}

    watchlist_exports._merge_npm_candidate(
        store,
        {
            "id": "npm:@badlogic/pi",
            "tags": ["pi/extension", "source/npm"],
            "fromRepos": ["acme/rocket"],
            "fromRepoIds": ["github:acme/rocket"],
            "whyWatch": "derived-from:acme/rocket",
        },
    )
    watchlist_exports._merge_npm_candidate(
        store,
        {
            "id": "npm:@badlogic/pi",
            "tags": ["pi/theme", "source/npm"],
            "fromRepos": ["acme/rocket", "acme/theme"],
            "fromRepoIds": ["github:acme/rocket", "github:acme/theme"],
            "whyWatch": "derived-from:acme/theme",
        },
    )
    watchlist_exports._merge_npm_candidate(
        store,
        {
            "id": "npm:@badlogic/pi",
            "tags": ["pi/theme"],
            "fromRepos": ["acme/theme"],
            "fromRepoIds": ["github:acme/theme"],
            "whyWatch": "derived-from:acme/theme",
        },
    )

    merged = store["npm:@badlogic/pi"]
    assert merged["tags"] == ["pi/extension", "pi/theme", "source/npm"]
    assert merged["fromRepos"] == ["acme/rocket", "acme/theme"]
    assert merged["fromRepoIds"] == ["github:acme/rocket", "github:acme/theme"]

    why_watch = str(merged["whyWatch"])
    assert why_watch.count("derived-from:acme/rocket") == 1
    assert why_watch.count("derived-from:acme/theme") == 1


def test_signal_sources_and_confidence_are_derived_from_reason_fragments() -> None:
    reasons = [
        "topic:pi-extension",
        "readme-path:extensions/*.{ts,js}",
        "phrase:pi coding agent",
    ]

    sources = watchlist_exports._signal_sources_from_reasons(reasons)
    assert sources == ["topic", "phrase", "path"]

    confidence = watchlist_exports._watch_confidence(
        tags=["pi/extension", "source/github-starred"],
        reasons=reasons,
    )
    assert confidence == "high"


def test_populate_signal_metadata_builds_structured_fields() -> None:
    candidate = {
        "tags": ["pi/extension", "source/npm"],
        "whyWatch": "derived-from:acme/rocket; npm-keyword:pi-extension",
    }

    watchlist_exports._populate_signal_metadata(candidate)

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

    confidence_counts = watchlist_exports._confidence_counts(candidates)
    source_counts = watchlist_exports._signal_source_counts(candidates)

    assert confidence_counts == {"medium": 2}
    assert source_counts == {"topic": 1, "derived": 1, "npm-keyword": 1}
