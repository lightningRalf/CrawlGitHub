import datetime

from crawl_github_starred import repo_info


def test_dedupe_overview_rows_keeps_latest_row_per_date() -> None:
    body = (
        "## Overview\n\n"
        "| Date       | Watchers | Forks | Stars | Contributors | Latest Release |\n"
        "|------------|----------|-------|-------|--------------|----------------|\n"
        "| 2026-02-14 | 1 | 1 | 1 | 1 | v1 |\n"
        "| 2026-02-13 | 2 | 2 | 2 | 2 | v0 |\n"
        "| 2026-02-14 | 3 | 3 | 3 | 3 | v2 |\n"
    )

    deduped_body, changed, latest_row = repo_info._dedupe_overview_rows(body)

    assert changed is True
    assert [line for line in deduped_body.splitlines() if line.startswith("| 2026-")] == [
        "| 2026-02-13 | 2 | 2 | 2 | 2 | v0 |",
        "| 2026-02-14 | 3 | 3 | 3 | 3 | v2 |",
    ]
    assert latest_row == {
        "date": "2026-02-14",
        "watchers": "3",
        "forks": "3",
        "stars": "3",
        "contributors": "3",
        "latest_release": "v2",
    }


def test_render_frontmatter_respects_defined_order() -> None:
    rendered = repo_info._render_frontmatter(
        {
            "custom_field": "keep-me",
            "repo": "acme/rocket",
            "source": "github-star",
            "next_action": "evaluate",
            "type": "checkbox",
            "schema_version": 2,
        }
    )

    keys = [
        line.split(":", 1)[0]
        for line in rendered.splitlines()
        if line and not line.startswith("---")
    ]

    assert keys == [
        "type",
        "schema_version",
        "source",
        "repo",
        "next_action",
        "custom_field",
    ]


def test_upsert_frontmatter_preserves_manual_fields_and_schema_version() -> None:
    updated = repo_info._upsert_frontmatter(
        frontmatter={
            "schema_version": "1",
            "review_status": "done",
            "why_starred": "possible pi extension",
            "next_action": "build a spike",
        },
        repo_data={
            "full_name": "acme/rocket",
            "name": "rocket",
            "owner": {"login": "acme"},
            "topics": ["pi-extension", "tooling"],
            "language": "Python",
            "license": {"spdx_id": "MIT"},
            "stargazers_count": 42,
            "subscribers_count": 7,
            "forks_count": 3,
        },
        github_url="https://github.com/acme/rocket",
        repo_description="Rocket repo",
        maintained=True,
        readme_note_relative_path="23.03_READMEs/acme__rocket__abc123.md",
        readme_sha256="sha256",
        readme_source_pushed_at="2026-02-16T00:00:00Z",
        metrics={
            "stars": 42,
            "watchers": 7,
            "forks": 3,
            "contributors": 4,
            "latest_release": "v1.2.3",
        },
        today="2026-02-16",
    )

    assert updated["schema_version"] == repo_info.FRONTMATTER_SCHEMA_VERSION
    assert updated["review_status"] == "done"
    assert updated["why_starred"] == "possible pi extension"
    assert updated["next_action"] == "build a spike"
    assert updated["source"] == "github-star"
    assert updated["repo"] == "acme/rocket"


def test_should_sync_readme_if_pushed_and_stale_fallback() -> None:
    now_utc = datetime.datetime(2026, 2, 16, 12, 0, tzinfo=datetime.timezone.utc)

    assert repo_info._should_sync_readme(
        mode="if-pushed",
        readme_exists=True,
        previous_source_pushed_at="2026-02-10T00:00:00Z",
        current_source_pushed_at="2026-02-12T00:00:00Z",
        readme_synced_at="2026-02-15T00:00:00Z",
        stale_fallback_days=30,
        now_utc=now_utc,
    ) is True

    assert repo_info._should_sync_readme(
        mode="if-pushed",
        readme_exists=True,
        previous_source_pushed_at="2026-02-10T00:00:00Z",
        current_source_pushed_at="2026-02-10T00:00:00Z",
        readme_synced_at="2026-02-15T00:00:00Z",
        stale_fallback_days=30,
        now_utc=now_utc,
    ) is False

    assert repo_info._should_sync_readme(
        mode="if-pushed",
        readme_exists=True,
        previous_source_pushed_at="2026-02-10T00:00:00Z",
        current_source_pushed_at="2026-02-10T00:00:00Z",
        readme_synced_at="2025-12-01T00:00:00Z",
        stale_fallback_days=30,
        now_utc=now_utc,
    ) is True

    # A recent conditional check (304) should postpone stale refresh attempts.
    assert repo_info._should_sync_readme(
        mode="if-pushed",
        readme_exists=True,
        previous_source_pushed_at="2026-02-10T00:00:00Z",
        current_source_pushed_at="2026-02-10T00:00:00Z",
        readme_synced_at="2025-12-01T00:00:00Z",
        readme_last_attempt_at="2026-02-15T00:00:00Z",
        stale_fallback_days=30,
        now_utc=now_utc,
    ) is False


def test_should_sync_readme_stale_fallback_can_be_disabled() -> None:
    now_utc = datetime.datetime(2026, 2, 16, 12, 0, tzinfo=datetime.timezone.utc)

    assert repo_info._should_sync_readme(
        mode="if-pushed",
        readme_exists=True,
        previous_source_pushed_at="",
        current_source_pushed_at="",
        readme_synced_at="invalid",
        stale_fallback_days=0,
        now_utc=now_utc,
    ) is False


def test_stale_days_with_repo_jitter_is_deterministic_and_bounded() -> None:
    base_stale_days = 30
    jitter_span_days = 7

    value_a = repo_info._stale_days_with_repo_jitter(
        stale_fallback_days=base_stale_days,
        repo_identity="acme/rocket",
        jitter_span_days=jitter_span_days,
    )
    value_b = repo_info._stale_days_with_repo_jitter(
        stale_fallback_days=base_stale_days,
        repo_identity="acme/rocket",
        jitter_span_days=jitter_span_days,
    )

    assert value_a == value_b
    assert base_stale_days <= value_a < (base_stale_days + jitter_span_days)

    assert repo_info._stale_days_with_repo_jitter(
        stale_fallback_days=base_stale_days,
        repo_identity="acme/rocket",
        jitter_span_days=0,
    ) == base_stale_days

    assert repo_info._stale_days_with_repo_jitter(
        stale_fallback_days=0,
        repo_identity="acme/rocket",
        jitter_span_days=7,
    ) == 0


def test_readme_sync_reason_classification() -> None:
    now_utc = datetime.datetime(2026, 2, 16, 12, 0, tzinfo=datetime.timezone.utc)

    assert repo_info._readme_sync_reason(
        mode="if-pushed",
        readme_exists=False,
        previous_source_pushed_at="",
        current_source_pushed_at="",
        now_utc=now_utc,
    ) == "missing"

    assert repo_info._readme_sync_reason(
        mode="if-pushed",
        readme_exists=True,
        previous_source_pushed_at="2026-02-10T00:00:00Z",
        current_source_pushed_at="2026-02-12T00:00:00Z",
        now_utc=now_utc,
    ) == "pushed"

    assert repo_info._readme_sync_reason(
        mode="if-pushed",
        readme_exists=True,
        previous_source_pushed_at="2026-02-10T00:00:00Z",
        current_source_pushed_at="2026-02-10T00:00:00Z",
        readme_last_attempt_at="2026-01-01T00:00:00Z",
        stale_fallback_days=30,
        now_utc=now_utc,
    ) == "stale"


def test_readme_retry_cooldown_for_not_found() -> None:
    now_utc = datetime.datetime(2026, 2, 16, 12, 0, tzinfo=datetime.timezone.utc)

    assert repo_info._is_readme_retry_cooldown_active(
        readme_last_status="not_found",
        readme_last_attempt_at="2026-02-01T00:00:00Z",
        now_utc=now_utc,
    ) is True

    assert repo_info._is_readme_retry_cooldown_active(
        readme_last_status="not_found",
        readme_last_attempt_at="2026-01-10T00:00:00Z",
        now_utc=now_utc,
    ) is False

    assert repo_info._is_readme_retry_cooldown_active(
        readme_last_status="error",
        readme_last_attempt_at="2026-02-15T00:00:00Z",
        now_utc=now_utc,
    ) is True
