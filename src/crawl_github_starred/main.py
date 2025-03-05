import logging
import os

from . import config  # Import the config module
from . import github_api
from . import repo_info
import stamina


def main():
    """Main function to fetch starred repos and generate info."""
    logging.basicConfig(
        filename=os.path.join(config.WORKING_DIRECTORY, config.LOG_FILE),
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Activate structlog-based instrumentation.
    stamina.instrumentation.set_on_retry_hooks(
        [stamina.instrumentation.StructlogOnRetryHook]
    )

    # Fetch and save starred repository URLs
    api_url = "https://api.github.com/users/lightningralf/starred"
    headers = github_api.get_github_headers()
    starred_repos = github_api.fetch_starred_repos(api_url, headers)

    with open(
        os.path.join(config.WORKING_DIRECTORY, config.STARRED_REPOS_FILE), "w"
    ) as f:
        for repo_url in starred_repos:
            f.write(repo_url + "\n")
    print(f"Starred repository URLs saved to {config.STARRED_REPOS_FILE}")

    # Generate repository information
    with open(
        os.path.join(config.WORKING_DIRECTORY, config.STARRED_REPOS_FILE), "r"
    ) as f:
        urls = [url.strip() for url in f.readlines() if url.strip()]
    repo_info.generate_repo_info(urls)


if __name__ == "__main__":
    main()