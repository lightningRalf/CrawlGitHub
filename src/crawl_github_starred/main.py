import argparse
import logging
import os
import sys

from . import config
from . import bases_files
from . import github_api
from . import repo_info
from . import starred_repos_file
from . import watchlist_exports
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
    parser.add_argument(
        "--readme-sync-mode",
        type=str,
        choices=sorted(config.README_SYNC_MODES),
        default=config.README_SYNC_MODE,
        help="README sync mode: off, new, if-pushed, always.",
    )
    parser.add_argument(
        "--readme-stale-days",
        type=int,
        default=config.README_SYNC_STALE_DAYS,
        help="Stale fallback window in days for README sync when mode is if-pushed (0 disables fallback).",
    )
    parser.add_argument(
        "--readme-stale-jitter-days",
        type=int,
        default=config.README_SYNC_STALE_JITTER_DAYS,
        help="Deterministic per-repo stale jitter span (adds hash(repo) %% N days; 0 disables jitter).",
    )
    parser.add_argument(
        "--max-readme-updates",
        type=int,
        default=config.MAX_README_UPDATES_PER_RUN,
        help="Maximum README snapshot updates per run.",
    )
    parser.add_argument(
        "--skip-bases",
        action="store_true",
        help="Do not regenerate Obsidian .base files.",
    )
    parser.add_argument(
        "--sync-watch-candidates",
        action="store_true",
        help="Sync watch candidates into note frontmatter and npm candidate notes.",
    )
    parser.add_argument(
        "--export-watch-seeds",
        type=str,
        default=None,
        help="Optional JSONL path for GitHub watchlist seed export.",
    )
    parser.add_argument(
        "--export-npm-seeds",
        type=str,
        default=None,
        help="Optional JSONL path for npm watchlist seed export.",
    )
    parser.add_argument(
        "--max-npm-lookups",
        type=int,
        default=0,
        help="Optional cap for npm metadata enrichment requests (default: 0).",
    )
    parser.add_argument(
        "--export-seeds-only",
        action="store_true",
        help="Only export watch seeds from local notes (no GitHub API calls).",
    )
    args = parser.parse_args()

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

    def run_watch_seed_export() -> None:
        export_stats = watchlist_exports.export_watch_seed_files(
            github_output_path=args.export_watch_seeds,
            npm_output_path=args.export_npm_seeds,
            max_npm_lookups=max(0, args.max_npm_lookups),
        )
        logger.info(
            "Watch seed export: scanned_notes=%s, pi_candidates=%s, repo_candidates=%s, npm_candidates=%s, npm_lookups=%s",
            export_stats.get("scanned_notes"),
            export_stats.get("pi_candidates"),
            export_stats.get("repo_candidates"),
            export_stats.get("npm_candidates"),
            export_stats.get("npm_lookups"),
        )
        if args.export_watch_seeds:
            logger.info("Wrote GitHub watch seed export: %s", args.export_watch_seeds)
        if args.export_npm_seeds:
            logger.info("Wrote npm watch seed export: %s", args.export_npm_seeds)

    def run_watch_candidate_sync() -> None:
        sync_stats = watchlist_exports.sync_watch_candidates_to_notes(
            max_npm_lookups=max(0, args.max_npm_lookups),
        )
        logger.info(
            "Watch candidate sync: scanned_notes=%s, repo_candidates=%s, npm_candidates=%s, repo_notes_updated=%s, repo_notes_missing=%s, npm_notes_created=%s, npm_notes_updated=%s, npm_lookups=%s",
            sync_stats.get("scanned_notes"),
            sync_stats.get("repo_candidates"),
            sync_stats.get("npm_candidates"),
            sync_stats.get("repo_notes_updated"),
            sync_stats.get("repo_notes_missing"),
            sync_stats.get("npm_notes_created"),
            sync_stats.get("npm_notes_updated"),
            sync_stats.get("npm_lookups"),
        )

        if not args.skip_bases:
            watch_base_path = bases_files.write_watch_candidates_base()
            logger.info("Wrote base file: %s", watch_base_path)

    if args.export_seeds_only:
        did_any_seed_action = False

        if args.sync_watch_candidates:
            run_watch_candidate_sync()
            did_any_seed_action = True

        if args.export_watch_seeds or args.export_npm_seeds:
            run_watch_seed_export()
            did_any_seed_action = True

        if not did_any_seed_action:
            logger.warning(
                "--export-seeds-only was set without --sync-watch-candidates or export output paths."
            )

        logger.info("Repository information generation completed")
        return

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
        readme_sync_mode=args.readme_sync_mode,
        readme_stale_days=args.readme_stale_days,
        readme_stale_jitter_days=args.readme_stale_jitter_days,
        max_readme_updates=args.max_readme_updates,
    )
    starred_repos_file.write_starred_repos_file(
        starred_repos_file_path,
        starred_repos,
        newly_unmaintained,
        description,
    )

    if not args.skip_bases:
        repo_index_path, review_queue_path = bases_files.write_base_files()
        logger.info(f"Wrote base file: {repo_index_path}")
        logger.info(f"Wrote base file: {review_queue_path}")

    if args.sync_watch_candidates:
        run_watch_candidate_sync()

    if args.export_watch_seeds or args.export_npm_seeds:
        run_watch_seed_export()

    logger.info("Repository information generation completed")


if __name__ == "__main__":
    main()
