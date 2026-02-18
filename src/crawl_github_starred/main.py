import argparse
import datetime
import json
import logging
import os
import sys

from . import bases_files
from . import config
from . import github_api
from . import repo_info
from . import starred_repos_file
from .watch import export as watch_export
from .watch import sync as watch_sync
import stamina


def _resolve_watch_telemetry_path() -> str:
    configured = str(config.WATCH_TELEMETRY_FILE or "").strip()
    if not configured:
        return ""

    if os.path.isabs(configured):
        return configured

    return os.path.join(config.WORKING_DIRECTORY, configured)


def _write_watch_telemetry(event_type: str, stats: dict[str, object]) -> str | None:
    path = _resolve_watch_telemetry_path()
    if not path:
        return None

    payload = {
        "written_at": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "event": event_type,
        "working_directory": config.WORKING_DIRECTORY,
        "stats": stats,
    }

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    return path


CLI_EPILOG = "\n".join(
    [
        "Examples:",
        "  crawl-github crawl --skip-existing --max-repos 50",
        "  crawl-github watch sync --prune-watch-candidates --max-npm-lookups 0",
        "  crawl-github watch export --export-watch-seeds watch-github.jsonl --export-npm-seeds watch-npm.jsonl",
    ]
)


def _add_watch_seed_export_arguments(parser: argparse.ArgumentParser) -> None:
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


def _add_watch_sync_subcommand_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--skip-bases",
        action="store_true",
        help="Do not regenerate Obsidian .base files after sync.",
    )
    parser.add_argument(
        "--prune-watch-candidates",
        action="store_true",
        help="Archive watch candidates no longer detected during sync (sets watch_status=archived).",
    )
    _add_watch_seed_export_arguments(parser)


def _add_crawl_arguments(parser: argparse.ArgumentParser) -> None:
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch starred GitHub repos and update notes.",
        epilog=CLI_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl_parser = subparsers.add_parser(
        "crawl",
        help="Run the full crawl workflow.",
        description="Run the full crawl workflow against GitHub starred repositories.",
    )
    _add_crawl_arguments(crawl_parser)

    watch_parser = subparsers.add_parser(
        "watch",
        help="Run local-only watch workflows.",
        description="Run local-only watch workflows (no GitHub API calls).",
    )
    watch_subparsers = watch_parser.add_subparsers(dest="watch_command", required=True)

    watch_sync_parser = watch_subparsers.add_parser(
        "sync",
        help="Sync watch candidates into notes/frontmatter.",
        description="Sync watch candidates into notes/frontmatter and optionally export seed JSONL files.",
    )
    _add_watch_sync_subcommand_arguments(watch_sync_parser)

    watch_export_parser = watch_subparsers.add_parser(
        "export",
        help="Export watch seeds from local notes.",
        description="Export watch seeds from local notes without running a GitHub crawl.",
    )
    _add_watch_seed_export_arguments(watch_export_parser)

    return parser


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    return parser.parse_args(raw_argv)


def main():
    args = _parse_args()

    # Configure logging to both file and console
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(config.WORKING_DIRECTORY, config.LOG_FILE)),
            logging.StreamHandler(sys.stdout),
        ],
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
        export_stats = watch_export.export_watch_seed_files(
            github_output_path=args.export_watch_seeds,
            npm_output_path=args.export_npm_seeds,
            max_npm_lookups=max(0, args.max_npm_lookups),
        )
        logger.info(
            "Watch seed export: scanned_notes=%s, pi_candidates=%s, repo_candidates=%s, npm_candidates=%s, npm_lookups=%s, repo_confidence=%s, npm_confidence=%s, signal_sources=%s",
            export_stats.get("scanned_notes"),
            export_stats.get("pi_candidates"),
            export_stats.get("repo_candidates"),
            export_stats.get("npm_candidates"),
            export_stats.get("npm_lookups"),
            export_stats.get("repo_confidence_counts"),
            export_stats.get("npm_confidence_counts"),
            export_stats.get("signal_source_counts"),
        )
        if args.export_watch_seeds:
            logger.info("Wrote GitHub watch seed export: %s", args.export_watch_seeds)
        if args.export_npm_seeds:
            logger.info("Wrote npm watch seed export: %s", args.export_npm_seeds)

        telemetry_path = _write_watch_telemetry("watch-seed-export", export_stats)
        if telemetry_path:
            logger.info("Wrote watch telemetry: %s", telemetry_path)

    def run_watch_candidate_sync() -> None:
        sync_stats = watch_sync.sync_watch_candidates_to_notes(
            max_npm_lookups=max(0, args.max_npm_lookups),
            prune_missing=args.prune_watch_candidates,
        )
        logger.info(
            "Watch candidate sync: scanned_notes=%s, repo_candidates=%s, npm_candidates=%s, repo_notes_updated=%s, repo_notes_missing=%s, repo_notes_reactivated=%s, npm_notes_created=%s, npm_notes_updated=%s, npm_notes_reactivated=%s, archived=%s (repo=%s, npm=%s), npm_lookups=%s, repo_confidence=%s, npm_confidence=%s, signal_sources=%s",
            sync_stats.get("scanned_notes"),
            sync_stats.get("repo_candidates"),
            sync_stats.get("npm_candidates"),
            sync_stats.get("repo_notes_updated"),
            sync_stats.get("repo_notes_missing"),
            sync_stats.get("repo_notes_reactivated"),
            sync_stats.get("npm_notes_created"),
            sync_stats.get("npm_notes_updated"),
            sync_stats.get("npm_notes_reactivated"),
            sync_stats.get("watch_notes_archived_total"),
            sync_stats.get("repo_notes_archived"),
            sync_stats.get("npm_notes_archived"),
            sync_stats.get("npm_lookups"),
            sync_stats.get("repo_confidence_counts"),
            sync_stats.get("npm_confidence_counts"),
            sync_stats.get("signal_source_counts"),
        )

        telemetry_path = _write_watch_telemetry("watch-candidate-sync", sync_stats)
        if telemetry_path:
            logger.info("Wrote watch telemetry: %s", telemetry_path)

        if not args.skip_bases:
            watch_base_path = bases_files.write_watch_candidates_base()
            logger.info("Wrote base file: %s", watch_base_path)

    if args.command == "watch":
        if args.watch_command == "sync":
            run_watch_candidate_sync()
            if args.export_watch_seeds or args.export_npm_seeds:
                run_watch_seed_export()
        elif args.watch_command == "export":
            if not args.export_watch_seeds and not args.export_npm_seeds:
                logger.warning(
                    "watch export needs --export-watch-seeds and/or --export-npm-seeds."
                )
            else:
                run_watch_seed_export()

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

    logger.info("Repository information generation completed")


if __name__ == "__main__":
    main()
