import os
import re
import datetime
import logging

from . import config
from . import github_api

logger = logging.getLogger(__name__)


def generate_repo_info(urls: list[str]) -> None:
    """Generates repository information and saves/appends to markdown files."""
    headers = github_api.get_github_headers()

    for i, github_url in enumerate(urls, start=2):
        api_url = github_url.replace("https://github.com", "https://api.github.com/repos")
        response = github_api.fetch_github_data(api_url, headers.copy())  # Fetch repo data

        if not response:
            continue

        repo_data = response.json()

        # Extract information
        repo_name = repo_data["name"]
        repo_description = repo_data["description"] or "No description found"
        stars = repo_data["stargazers_count"]
        watching = repo_data["subscribers_count"]
        forks = repo_data["forks_count"]
        default_branch = repo_data["default_branch"]
        contributors_url = repo_data["contributors_url"]
        releases_url = repo_data["releases_url"].replace("{/id}", "")

        # Get contributors count
        contributors_response = github_api.fetch_github_data(contributors_url, headers.copy())
        contributors = (
            len(contributors_response.json()) if contributors_response else "Error"
        )

        # Get latest release
        releases_response = github_api.fetch_github_data(releases_url, headers.copy())
        latest_release = (
            releases_response.json()[0]["tag_name"]
            if releases_response and releases_response.json()
            else "No release found"
        )

        # Find existing markdown file or create a new one
        existing_files = [
            file
            for file in os.listdir(config.WORKING_DIRECTORY)
            if re.search(rf"23.03\.\d{{2,3}}_{repo_name}\.md", file)
        ]

        if existing_files:
            markdown_file = existing_files[0]
        else:
            existing_numbers = [
                int(re.search(r"23.03\.(\d{2,3})_", file).group(1))
                for file in os.listdir(config.WORKING_DIRECTORY)
                if re.search(r"23.03\.\d{2,3}_", file)
            ]
            next_number = max(existing_numbers, default=1) + 1
            markdown_file = f"23.03.{next_number:03}_{repo_name}.md"

        markdown_file_path = os.path.join(config.WORKING_DIRECTORY, markdown_file)

        # Open the markdown file in append mode
        with open(markdown_file_path, "a", encoding="utf-8") as f:
            if os.stat(markdown_file_path).st_size == 0:
                f.write(f"## [{repo_description}]({github_url})\n")
                readme_url = github_api.get_readme_url(
                    github_url, default_branch
                )  # Use the function
                f.write(f"\n## README\n\n")
                f.write(config.README_TEMPLATE.format(readme_url))
                f.write(f"\n## Overview\n\n")
                f.write(
                    "| Date       | Watchers | Forks | Stars | Contributors | Latest Release |\n"
                )
                f.write(
                    "|------------|----------|-------|-------|--------------|----------------|\n"
                )
            f.write(
                f"| {datetime.datetime.now().strftime('%Y-%m-%d')} | {watching} | {forks}  | {stars} | {contributors} | {latest_release} |\n"
            )
        logger.info(f"Data has been added to {markdown_file} for {repo_name}.")