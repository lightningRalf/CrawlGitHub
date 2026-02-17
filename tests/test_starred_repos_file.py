from crawl_github_starred import starred_repos_file


def test_write_starred_repos_file_dedupes_maintenance_groups_and_urls(tmp_path) -> None:
    path = tmp_path / "23.03.01_CrawlGitHubURLs.md"
    path.write_text(
        "\n".join(
            [
                "# Metadata",
                "old description",
                "",
                "# Inhalt",
                "## no longer maintained",
                "### [[2026-01-01 Wednesday]]",
                "- [[23.03.100_A.md]]",
                "- [[23.03.101_B.md]]",
                "",
                "### [[2026-01-02 Thursday]]",
                "- [[23.03.101_B.md]]",
                "- [[23.03.102_C.md]]",
                "",
                "## files to scrape",
                "https://github.com/acme/rocket",
                "https://github.com/acme/rocket",
                "https://github.com/acme/legacy",
                "",
            ]
        ),
        encoding="utf-8",
    )

    starred_repos_file.write_starred_repos_file(
        file_path=str(path),
        starred_repos=[
            "https://github.com/acme/rocket",
            "https://github.com/acme/new",
            "https://github.com/acme/new",
        ],
        newly_unmaintained=[],
        description="fresh description",
    )

    content = path.read_text(encoding="utf-8")

    assert content.count("- [[23.03.101_B.md]]") == 1
    assert "- [[23.03.100_A.md]]" in content
    assert "- [[23.03.102_C.md]]" in content

    scrape_lines = [
        line.strip()
        for line in content.split("## files to scrape", 1)[1].splitlines()
        if line.strip()
    ]
    assert scrape_lines == [
        "https://github.com/acme/rocket",
        "https://github.com/acme/new",
    ]
