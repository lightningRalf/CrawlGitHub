# Crawl GitHub Starred Repositories

This script crawls the starred repositories of a specific GitHub user (`lightningralf` by default), fetches metadata for each repository, and generates/updates individual Markdown files in a designated working directory. Each file includes repository details, an embedded README (via iframe), and a table tracking metadata over time.

## Features

*   Fetches starred repositories for a configured GitHub user.
*   Retrieves metadata (stars, watchers, forks, contributors count, latest release tag) for each repository.
*   Generates individual Markdown files for each starred repository.
*   Embeds the repository's live README.md within the generated Markdown file using an iframe.
*   Appends updated metadata to existing files on subsequent runs, creating a historical log.
*   Caches GitHub API responses locally (`.cache` directory) to speed up runs and respect rate limits.
*   Uses `stamina` for robust, automatic retries on failed API requests.
*   Logs activity to both the console and a log file (`github_fetch.log`).

## Prerequisites

*   Python (>= 3.8 recommended)
*   [uv](https://github.com/astral-sh/uv) (Python package installer and virtual environment manager)
*   A GitHub Personal Access Token (PAT) with `public_repo` scope (or `repo` if you star private repositories you want to crawl).

## Installation & Setup with `uv`

1.  **Install `uv`:**
    Follow the official installation instructions for `uv`: [https://github.com/astral-sh/uv#installation](https://github.com/astral-sh/uv#installation)

2.  **Clone the Repository:**
    ```bash
    git clone <your-repository-url>
    cd <repository-directory>
    ```

3.  **Create Virtual Environment & Install Dependencies:**
    Use `uv` to create a virtual environment and install the required packages:
    ```bash
    # Create a virtual environment named .venv
    uv venv

    # Install dependencies (requests and stamina are the core runtime dependencies)
    uv pip install requests stamina
    ```
    *(Note: If a `requirements.txt` file is added later, you can use `uv pip install -r requirements.txt` instead.)*

## Configuration

1.  **Set GitHub PAT:**
    The script requires your GitHub Personal Access Token to be available as an environment variable named `GITHUB_PAT`.

    *   **Linux/macOS:**
        ```bash
        export GITHUB_PAT="your_github_pat_here"
        ```
    *   **Windows (Command Prompt):**
        ```bash
        set GITHUB_PAT=your_github_pat_here
        ```
    *   **Windows (PowerShell):** (my method)
        ```powershell
        $env:GITHUB_PAT = "your_github_pat_here"
        ```
    *You might want to add this to your shell's profile file (`.bashrc`, `.zshrc`, etc.) or use a tool like `direnv` for persistent setting.*

2.  **Set Working Directory:**
    **Crucially**, you *must* edit the `src/crawl_github_starred/config.py` file and change the `WORKING_DIRECTORY` variable to the path where you want the Markdown files and log file to be generated.

    ```python
    # src/crawl_github_starred/config.py
    import os

    # --- MODIFY THIS LINE ---
    WORKING_DIRECTORY = "/path/to/your/desired/output/directory"
    # -----------------------

    STARRED_REPOS_FILE = "23.03.01_CrawlGitHubURLs.md"
    CACHE_DIR = os.path.join(WORKING_DIRECTORY, ".cache")
    README_TEMPLATE = '<iframe width="100%" height="800" src="{}" ></iframe>'
    LOG_FILE = "github_fetch.log"

    # ... rest of the file ...
    ```
    Ensure this directory exists and you have write permissions.

## Running the Script with `uv`

After installation and configuration:

1.  **Activate the virtual environment (Optional but recommended for direct Python calls):**
    *   Linux/macOS: `source .venv/bin/activate`
    *   Windows: `.\.venv\Scripts\activate`

2.  **Run using `uv run`:**
    This command executes the script within the context of the `uv`-managed environment without needing manual activation. Run this from the root directory of the project:
    ```bash - (My method)
    uv run python -m src.crawl_github_starred.main
    ```

The script will start fetching starred repositories, processing them, and creating/updating files in your configured `WORKING_DIRECTORY`. Check the console and the `github_fetch.log` file for progress and potential issues.

## Testing

The `tests` directory contains basic tests for logging and the `stamina` retry mechanism. You can run them individually using `uv`:

```bash
uv run python tests/test_logging.py
uv run python tests/test_stamina_logging.py