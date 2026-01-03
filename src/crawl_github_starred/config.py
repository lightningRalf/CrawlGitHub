import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    working_directory: str
    starred_repos_file: str
    cache_dir: str
    readme_template: str
    log_file: str
    github_pat: str

    @staticmethod
    def from_env() -> "Config":
        github_pat = os.environ.get("GITHUB_PAT")
        if not github_pat:
            raise ValueError("GITHUB_PAT environment variable not found.")
        working_directory = (
            "C:\\Users\\mjpa\\Documents\\Obsidian\\20-29_Input\\23_Schriftliches\\23.03_Code"
        )
        cache_dir = os.path.join(working_directory, ".cache")
        return Config(
            working_directory=working_directory,
            starred_repos_file="23.03.01_CrawlGitHubURLs.md",
            cache_dir=cache_dir,
            readme_template='<iframe width="100%" height="800" src="{}" ></iframe>',
            log_file="github_fetch.log",
            github_pat=github_pat,
        )


CONFIG = Config.from_env()

WORKING_DIRECTORY = CONFIG.working_directory
STARRED_REPOS_FILE = CONFIG.starred_repos_file
CACHE_DIR = CONFIG.cache_dir
README_TEMPLATE = CONFIG.readme_template
LOG_FILE = CONFIG.log_file
GITHUB_PAT = CONFIG.github_pat

os.makedirs(CACHE_DIR, exist_ok=True)
