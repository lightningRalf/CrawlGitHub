import argparse
import logging
import os
import sys

from . import config
from . import github_api
from . import repo_info
from . import starred_repos_file
import stamina


def main():
    parser = argparse.ArgumentParser(description="Fetch starred GitHub repos and update notes.")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip repos that already have a table row for today.",
    )
    parser.add_argument(
        "--max-repos",
        type=int,
        default=None,
        help="Process at most N repositories (after resume-from).",
    )
    parser.add_argument(
        "--resume-from",
        type=int,
        default=None,
        help="Resume from this 23.03.xxx file number (e.g., 1450).",
    )
    args = parser.parse_args()
    """Main function to fetch starred repos and generate info."""
    # Configure logging to both file and console
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(config.WORKING_DIRECTORY, config.LOG_FILE)),
            logging.StreamHandler(sys.stdout)  # Add console output
        ]
    )
    logger = logging.getLogger(__name__)
    logger.info("Starting GitHub starred repository fetch")   
     
    if not os.path.exists(config.WORKING_DIRECTORY):
        logger.error(f"Working directory does not exist: {config.WORKING_DIRECTORY}")
        os.makedirs(config.WORKING_DIRECTORY, exist_ok=True)
        logger.info(f"Created working directory: {config.WORKING_DIRECTORY}")
    
    logger.info(f"Working directory: {config.WORKING_DIRECTORY}")
    logger.info(f"Write permission: {os.access(config.WORKING_DIRECTORY, os.W_OK)}")
    
    # Activate structlog-based instrumentation.
    stamina.instrumentation.set_on_retry_hooks(
        [stamina.instrumentation.StructlogOnRetryHook]
    )

    # Fetch and save starred repository URLs
    api_url = "https://api.github.com/users/lightningralf/starred"
    headers = github_api.get_github_headers()
    logger.info(f"Fetching starred repositories from {api_url}")
    starred_repos = github_api.fetch_starred_repos(api_url, headers)
    logger.info(f"Found {len(starred_repos)} starred repositories")

    starred_repos_file_path = os.path.join(config.WORKING_DIRECTORY, config.STARRED_REPOS_FILE)
    description = (
        "Tracks starred GitHub repository URLs for CrawlGitHub runs and logs repositories that became unmaintained."
    )
    starred_repos_file.write_starred_repos_file(
        starred_repos_file_path,
        starred_repos,
        [],
        description,
    )
    logger.info(f"Starred repository URLs saved to {starred_repos_file_path}")

    # Generate repository information
    with open(starred_repos_file_path, "r", encoding="utf-8") as f:
        urls = starred_repos_file.extract_urls(f.read())
    
    logger.info(f"Starting to generate info for {len(urls)} repositories")
    newly_unmaintained = repo_info.generate_repo_info(
        urls,
        skip_existing=args.skip_existing,
        max_repos=args.max_repos,
        resume_from=args.resume_from,
    )
    starred_repos_file.write_starred_repos_file(
        starred_repos_file_path,
        starred_repos,
        newly_unmaintained,
        description,
    )
    logger.info("Repository information generation completed")


if __name__ == "__main__":
    main()
