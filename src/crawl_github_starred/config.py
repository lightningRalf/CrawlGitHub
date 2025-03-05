import os

WORKING_DIRECTORY = (
    "C:\\Users\\mjpa\\Documents\\Obsidian\\20-29_Input\\23_Schriftliches\\23.03_Code"
)
STARRED_REPOS_FILE = "23.03.01_CrawlGitHubURLs.md"
CACHE_DIR = os.path.join(WORKING_DIRECTORY, ".cache")
README_TEMPLATE = '<iframe width="100%" height="800" src="{}" ></iframe>'
LOG_FILE = "github_fetch.log"

GITHUB_PAT = os.environ.get("GITHUB_PAT")
if not GITHUB_PAT:
    raise ValueError("GITHUB_PAT environment variable not found.")

os.makedirs(CACHE_DIR, exist_ok=True)