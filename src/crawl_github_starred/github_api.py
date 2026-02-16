import logging
import time
from typing import Optional

import requests
import stamina

from . import cache
from . import config

logger = logging.getLogger(__name__)


def get_github_headers() -> dict:
    """Return baseline headers for GitHub API requests."""
    return {
        "Authorization": f"token {config.GITHUB_PAT}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def split_owner_repo(github_url: str) -> tuple[str, str]:
    """Extract owner/repo from a GitHub repository URL."""
    cleaned = github_url.rstrip("/")
    parts = cleaned.split("/")
    if len(parts) < 5:
        raise ValueError(f"Invalid GitHub URL: {github_url}")
    return parts[-2], parts[-1]


def get_readme_api_url(github_url: str) -> str:
    owner, repo = split_owner_repo(github_url)
    return f"https://api.github.com/repos/{owner}/{repo}/readme"


def is_github_rate_limit(exc: Exception) -> bool:
    """Check if an exception is a GitHub API rate limit error."""
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response.status_code == 403:
        headers = exc.response.headers
        return "X-RateLimit-Remaining" in headers and "X-RateLimit-Reset" in headers
    return False


def handle_rate_limit(response: requests.Response) -> None:
    """Sleep until GitHub rate limit reset when needed."""
    reset_timestamp = int(response.headers.get("X-RateLimit-Reset", 0))
    current_time = int(time.time())
    wait_time = max(0, reset_timestamp - current_time)
    if wait_time > 0:
        logger.warning(f"Rate limit exceeded. Waiting for {wait_time} seconds.")
        time.sleep(wait_time)


def _sleep_if_configured() -> None:
    if config.REQUEST_DELAY_SECONDS > 0:
        time.sleep(config.REQUEST_DELAY_SECONDS)


@stamina.retry(
    on=lambda e: isinstance(e, requests.exceptions.RequestException)
    and (is_github_rate_limit(e) or not isinstance(e, requests.exceptions.HTTPError)),
    attempts=10,
    wait_initial=1.0,
    wait_max=60.0,
    wait_jitter=1.0,
)
def fetch_github_data(url: str, headers: dict, use_cache: bool = True) -> Optional[requests.Response]:
    """Fetch JSON data from GitHub with conditional caching + retry."""
    cached_response = None
    if use_cache:
        cached_response = cache.get_cached_response(url)
        if cached_response:
            if "Last-Modified" in cached_response.headers:
                headers["If-Modified-Since"] = cached_response.headers["Last-Modified"]
            elif "ETag" in cached_response.headers:
                headers["If-None-Match"] = cached_response.headers["ETag"]

    try:
        _sleep_if_configured()
        response = requests.get(url, headers=headers)

        if response.status_code == 403:
            if "X-RateLimit-Remaining" in response.headers and "X-RateLimit-Reset" in response.headers:
                handle_rate_limit(response)
                response.raise_for_status()
            logger.warning(f"403 Forbidden (not rate limit) for {url}. Skipping.")
            return None

        if response.status_code == 304:
            logger.info(f"Content not modified (304): {url}")
            if not cached_response:
                logger.warning("Received 304 but no cached response available.")
                return None
            return cached_response

        if response.status_code != 200:
            logger.error(f"Request failed: {url} - {response.status_code} - {response.text}")
            response.raise_for_status()

        if use_cache:
            cache.cache_response(response)
        return response

    except requests.exceptions.RequestException as e:
        if not isinstance(e, requests.exceptions.HTTPError) or e.response.status_code != 403:
            raise
        logger.warning(f"Access forbidden for {url}. Skipping.")
        return None


@stamina.retry(
    on=lambda e: isinstance(e, requests.exceptions.RequestException)
    and (is_github_rate_limit(e) or not isinstance(e, requests.exceptions.HTTPError)),
    attempts=6,
    wait_initial=1.0,
    wait_max=60.0,
    wait_jitter=1.0,
)
def fetch_github_text(url: str, headers: dict) -> Optional[str]:
    """Fetch text content from GitHub with rate-limit-aware retries."""
    try:
        _sleep_if_configured()
        response = requests.get(url, headers=headers)

        if response.status_code == 403:
            if "X-RateLimit-Remaining" in response.headers and "X-RateLimit-Reset" in response.headers:
                handle_rate_limit(response)
                response.raise_for_status()
            logger.warning(f"403 Forbidden (not rate limit) for {url}. Skipping.")
            return None

        if response.status_code == 404:
            return None

        if response.status_code != 200:
            logger.error(f"Request failed: {url} - {response.status_code} - {response.text[:500]}")
            response.raise_for_status()

        return response.text

    except requests.exceptions.RequestException as e:
        if not isinstance(e, requests.exceptions.HTTPError) or e.response.status_code != 403:
            raise
        logger.warning(f"Access forbidden for {url}. Skipping.")
        return None


def fetch_readme_markdown(github_url: str, headers: dict) -> Optional[str]:
    """Fetch repository README content as markdown text."""
    readme_url = get_readme_api_url(github_url)
    readme_headers = headers.copy()
    readme_headers["Accept"] = "application/vnd.github.raw+json"
    return fetch_github_text(readme_url, readme_headers)


def fetch_starred_repos(api_url: str, headers: dict) -> list[str]:
    """Fetch starred repository URLs, handling pagination."""
    return [
        repo["html_url"]
        for repo in _fetch_paginated(api_url, headers)
        if isinstance(repo, dict) and repo.get("html_url")
    ]


def _fetch_paginated(api_url: str, headers: dict) -> list[dict]:
    items: list[dict] = []
    page = 1
    while True:
        paginated_url = f"{api_url}?page={page}&per_page=100"
        response = fetch_github_data(paginated_url, headers.copy())
        if response is None:
            break

        payload = response.json()
        if not isinstance(payload, list) or not payload:
            break

        items.extend(payload)
        logger.info(f"Fetched page {page} with {len(payload)} items.")
        page += 1
    return items


def get_readme_url(github_url: str, default_branch: str) -> str:
    """Construct README URL for web view."""
    return github_url + f"/blob/{default_branch}/README.md"
