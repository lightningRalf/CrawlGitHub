# Crawl GitHub Starred Repositories

Fetches starred repositories for a configured GitHub user (defaults to `lightningralf`), collects repo metadata, and generates per-repo Markdown files with embedded README content and historical tracking data.

## Features

- Repository discovery for starred repos
- Metadata collection (stars, watchers, forks, contributors, latest release)
- Per-repo Markdown notes with embedded README
- Historical tracking across runs
- Cached API responses in `.cache`
- Retry logic with `stamina`
- Console + file logging (`github_fetch.log`)

## Prerequisites

- Python 3.11+
- uv (https://github.com/astral-sh/uv)
- GitHub Personal Access Token (`GITHUB_PAT`)

## Installation

```sh
uv sync
```

## Configuration

1) Set your token:

```powershell
$env:GITHUB_PAT = "your_github_personal_access_token"
```

2) Set the output directory in `src/crawl_github_starred/config.py` (search for `working_directory`).

## Usage

Run the crawler from the project root:

```sh
uv run crawl-github
```

Or use the PowerShell wrapper (forwards args):

```powershell
.\run_crawl_github.ps1
```

Optional flags:
- `--skip-existing`
- `--resume-from 1450`
- `--max-repos 25`

## Quick Test

```sh
uv run crawl-github --resume-from 1450 --max-repos 10 --skip-existing
```

## Testing

```sh
uv run python tests/test_logging.py
uv run python tests/test_stamina_logging.py
```

## Project Structure

```
CrawlGitHub/
src/
  crawl_github_starred/
    __init__.py
    cache.py
    config.py
    github_api.py
    main.py
    repo_info.py
    starred_repos_file.py
tests/
  test_logging.py
  test_stamina_logging.py
docs/
  sunshine_output/
pyproject.toml
uv.lock
README.md
```
