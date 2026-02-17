from typing import Any

from crawl_github_starred import github_api


class _FakeResponse:
    def __init__(self, status_code: int, headers: dict[str, str] | None = None, text: str = "") -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_fetch_readme_markdown_with_metadata_handles_not_modified(monkeypatch: Any) -> None:
    captured_headers: dict[str, str] = {}

    def fake_get(url: str, headers: dict[str, str]) -> _FakeResponse:
        captured_headers.update(headers)
        return _FakeResponse(
            status_code=304,
            headers={"ETag": '"abc"', "Last-Modified": "Tue, 16 Feb 2026 10:00:00 GMT"},
        )

    monkeypatch.setattr(github_api.config, "REQUEST_DELAY_SECONDS", 0)
    monkeypatch.setattr(github_api.requests, "get", fake_get)

    result = github_api.fetch_readme_markdown_with_metadata(
        "https://github.com/acme/rocket",
        github_api.get_github_headers(),
        if_none_match='"old"',
        if_modified_since="Mon, 15 Feb 2026 10:00:00 GMT",
    )

    assert captured_headers.get("If-None-Match") == '"old"'
    assert captured_headers.get("If-Modified-Since") == "Mon, 15 Feb 2026 10:00:00 GMT"
    assert result.status == "not_modified"
    assert result.content is None
    assert result.etag == '"abc"'


def test_fetch_readme_markdown_with_metadata_handles_ok(monkeypatch: Any) -> None:
    def fake_get(url: str, headers: dict[str, str]) -> _FakeResponse:
        return _FakeResponse(
            status_code=200,
            headers={"ETag": '"new"'},
            text="# README\n",
        )

    monkeypatch.setattr(github_api.config, "REQUEST_DELAY_SECONDS", 0)
    monkeypatch.setattr(github_api.requests, "get", fake_get)

    result = github_api.fetch_readme_markdown_with_metadata(
        "https://github.com/acme/rocket",
        github_api.get_github_headers(),
    )

    assert result.status == "ok"
    assert result.content == "# README\n"
    assert result.etag == '"new"'
