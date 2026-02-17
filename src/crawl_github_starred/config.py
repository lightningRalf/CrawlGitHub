import os
from dataclasses import dataclass


README_SYNC_MODES = {"off", "new", "if-pushed", "always"}


@dataclass(frozen=True)
class Config:
    working_directory: str
    starred_repos_file: str
    cache_dir: str
    readme_template: str
    log_file: str
    request_delay_seconds: float
    github_pat: str
    readme_notes_subdir: str
    readme_sync_mode: str
    readme_sync_stale_days: int
    readme_sync_stale_jitter_days: int
    max_readme_updates_per_run: int
    repo_index_base_file: str
    review_queue_base_file: str
    watch_candidates_base_file: str
    watch_candidates_subdir: str

    @staticmethod
    def from_env() -> "Config":
        github_pat = os.environ.get("GITHUB_PAT")
        if not github_pat:
            raise ValueError("GITHUB_PAT environment variable not found.")

        working_directory = os.environ.get(
            "CRAWLGITHUB_WORKING_DIR",
            "C:\\Users\\mjpa\\Documents\\Obsidian\\20-29_Input\\23_Schriftliches\\23.03_Code",
        )

        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        default_cache_dir = os.path.join(repo_root, "tools", "cache")
        cache_dir = os.environ.get("CRAWLGITHUB_CACHE_DIR", default_cache_dir)

        request_delay_seconds = float(
            os.environ.get("CRAWLGITHUB_REQUEST_DELAY_SECONDS", "1.0")
        )

        readme_sync_mode = os.environ.get("CRAWLGITHUB_README_SYNC_MODE", "new").strip().lower()
        if readme_sync_mode not in README_SYNC_MODES:
            readme_sync_mode = "new"

        readme_sync_stale_days = int(
            os.environ.get("CRAWLGITHUB_README_SYNC_STALE_DAYS", "30")
        )
        readme_sync_stale_days = max(0, readme_sync_stale_days)

        readme_sync_stale_jitter_days = int(
            os.environ.get("CRAWLGITHUB_README_STALE_JITTER_DAYS", "7")
        )
        readme_sync_stale_jitter_days = max(0, readme_sync_stale_jitter_days)

        max_readme_updates = int(
            os.environ.get("CRAWLGITHUB_MAX_README_UPDATES_PER_RUN", "25")
        )
        max_readme_updates = max(0, max_readme_updates)

        return Config(
            working_directory=working_directory,
            starred_repos_file="23.03.01_CrawlGitHubURLs.md",
            cache_dir=cache_dir,
            readme_template='<iframe width="100%" height="800" src="{}" ></iframe>',
            log_file="github_fetch.log",
            request_delay_seconds=request_delay_seconds,
            github_pat=github_pat,
            readme_notes_subdir=os.environ.get(
                "CRAWLGITHUB_README_NOTES_SUBDIR",
                "23.03_READMEs",
            ),
            readme_sync_mode=readme_sync_mode,
            readme_sync_stale_days=readme_sync_stale_days,
            readme_sync_stale_jitter_days=readme_sync_stale_jitter_days,
            max_readme_updates_per_run=max_readme_updates,
            repo_index_base_file=os.environ.get(
                "CRAWLGITHUB_REPO_INDEX_BASE_FILE",
                "23.03.00_RepoIndex.base",
            ),
            review_queue_base_file=os.environ.get(
                "CRAWLGITHUB_REVIEW_QUEUE_BASE_FILE",
                "23.03.00_ReviewQueue.base",
            ),
            watch_candidates_base_file=os.environ.get(
                "CRAWLGITHUB_WATCH_CANDIDATES_BASE_FILE",
                "23.03.00_WatchCandidates.base",
            ),
            watch_candidates_subdir=os.environ.get(
                "CRAWLGITHUB_WATCH_CANDIDATES_SUBDIR",
                "23.03_WatchCandidates",
            ),
        )


CONFIG = Config.from_env()

WORKING_DIRECTORY = CONFIG.working_directory
STARRED_REPOS_FILE = CONFIG.starred_repos_file
CACHE_DIR = CONFIG.cache_dir
README_TEMPLATE = CONFIG.readme_template
LOG_FILE = CONFIG.log_file
REQUEST_DELAY_SECONDS = CONFIG.request_delay_seconds
GITHUB_PAT = CONFIG.github_pat
README_NOTES_SUBDIR = CONFIG.readme_notes_subdir
README_SYNC_MODE = CONFIG.readme_sync_mode
README_SYNC_STALE_DAYS = CONFIG.readme_sync_stale_days
README_SYNC_STALE_JITTER_DAYS = CONFIG.readme_sync_stale_jitter_days
MAX_README_UPDATES_PER_RUN = CONFIG.max_readme_updates_per_run
REPO_INDEX_BASE_FILE = CONFIG.repo_index_base_file
REVIEW_QUEUE_BASE_FILE = CONFIG.review_queue_base_file
WATCH_CANDIDATES_BASE_FILE = CONFIG.watch_candidates_base_file
WATCH_CANDIDATES_SUBDIR = CONFIG.watch_candidates_subdir

os.makedirs(CACHE_DIR, exist_ok=True)
