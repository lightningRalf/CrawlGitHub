import datetime
from typing import Iterable


def _parse_no_longer_maintained_section(content: str) -> list[str]:
    if "## no longer maintained" not in content:
        return []
    section = content.split("## no longer maintained", 1)[1]
    if "## files to scrape" in section:
        section = section.split("## files to scrape", 1)[0]
    lines = [line.rstrip() for line in section.splitlines()]
    return [line for line in lines if line.strip()]


def extract_urls(content: str) -> list[str]:
    urls: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("http"):
            urls.append(line)
    return urls


def write_starred_repos_file(
    file_path: str,
    starred_repos: Iterable[str],
    newly_unmaintained: list[str],
    description: str,
) -> None:
    existing_content = ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            existing_content = f.read()
    except FileNotFoundError:
        existing_content = ""

    previous_no_longer = _parse_no_longer_maintained_section(existing_content)

    run_lines: list[str] = []
    if newly_unmaintained:
        run_heading = datetime.datetime.now().strftime("%Y-%m-%d %A")
        run_lines.append(f"### [[{run_heading}]]")
        for entry in newly_unmaintained:
            run_lines.append(f"- [[{entry}]]")
    if run_lines and previous_no_longer:
        run_lines.append("")

    lines = [
        "# Metadata",
        description,
        "",
        "# Inhalt",
        "## no longer maintained",
        *run_lines,
        *previous_no_longer,
        "",
        "## files to scrape",
        *list(starred_repos),
    ]

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
