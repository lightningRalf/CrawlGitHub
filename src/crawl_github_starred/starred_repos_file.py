import datetime
from typing import Iterable


def _unique_preserve(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _parse_no_longer_maintained_groups(content: str) -> list[tuple[str, list[str]]]:
    if "## no longer maintained" not in content:
        return []

    section = content.split("## no longer maintained", 1)[1]
    if "## files to scrape" in section:
        section = section.split("## files to scrape", 1)[0]

    groups: list[tuple[str, list[str]]] = []
    index_by_heading: dict[str, int] = {}
    current_heading: str | None = None

    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("### [[") and line.endswith("]]"):
            current_heading = line
            if current_heading not in index_by_heading:
                index_by_heading[current_heading] = len(groups)
                groups.append((current_heading, []))
            continue

        if line.startswith("- [[") and line.endswith("]]"):
            if current_heading is None:
                current_heading = "### [[Legacy]]"
                if current_heading not in index_by_heading:
                    index_by_heading[current_heading] = len(groups)
                    groups.append((current_heading, []))
            group_index = index_by_heading[current_heading]
            groups[group_index][1].append(line)

    return groups


def _dedupe_groups(groups: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
    seen_entries: set[str] = set()
    deduped: list[tuple[str, list[str]]] = []

    for heading, entries in groups:
        unique_entries: list[str] = []
        for entry in entries:
            if entry in seen_entries:
                continue
            seen_entries.add(entry)
            unique_entries.append(entry)
        if unique_entries:
            deduped.append((heading, unique_entries))

    return deduped


def extract_urls(content: str) -> list[str]:
    urls: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("http"):
            urls.append(line)
    return _unique_preserve(urls)


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

    groups = _parse_no_longer_maintained_groups(existing_content)

    if newly_unmaintained:
        today_heading = datetime.datetime.now().strftime("### [[%Y-%m-%d %A]]")
        index_by_heading = {heading: idx for idx, (heading, _) in enumerate(groups)}

        if today_heading in index_by_heading:
            idx = index_by_heading[today_heading]
            groups[idx][1].extend(f"- [[{entry}]]" for entry in newly_unmaintained)
        else:
            groups.insert(0, (today_heading, [f"- [[{entry}]]" for entry in newly_unmaintained]))

    groups = _dedupe_groups(groups)

    no_longer_lines: list[str] = []
    for heading, entries in groups:
        no_longer_lines.append(heading)
        no_longer_lines.extend(entries)
        no_longer_lines.append("")
    while no_longer_lines and not no_longer_lines[-1].strip():
        no_longer_lines.pop()

    lines = [
        "# Metadata",
        description,
        "",
        "# Inhalt",
        "## no longer maintained",
        *no_longer_lines,
        "",
        "## files to scrape",
        *_unique_preserve(list(starred_repos)),
    ]

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")
