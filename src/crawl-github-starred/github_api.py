import requests
import time
import logging
import stamina
from typing import Optional

from . import config  # Import from the config module
from . import cache

# Configure logging within the module
logger = logging.getLogger(__name__)


def get_github_headers() -> dict:
    """Returns headers for GitHub API requests."""
    return {"Authorization": f"token {config.GITHUB_PAT}"}


def is_github_rate_limit(exc: Exception) -> bool:
    """Checks if an exception is a GitHub API rate limit error."""
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response.status_code == 403:
        headers = exc.response.headers
        return "X-RateLimit-Remaining" in headers and "X-RateLimit-Reset" in headers
    return False


def handle_rate_limit(response: requests.Response) -> None:
    """Handles GitHub API rate limits."""
    reset_timestamp = int(response.headers.get("X-RateLimit-Reset", 0))
    current_time = int(time.time())
    wait_time = max(0, reset_timestamp - current_time)
    if wait_time > 0:
        logger.warning(f"Rate limit exceeded. Waiting for {wait_time} seconds.")
        time.sleep(wait_time)

@stamina.retry(
    on=lambda e: isinstance(e, requests.exceptions.RequestException)
    or is_github_rate_limit(e),
    attempts=10,
    wait_initial=1.0,
    wait_max=60.0,
    wait_jitter=1.0,
)
def fetch_github_data(url: str, headers: dict, use_cache: bool = True) -> Optional[requests.Response]:
    """Fetches data from GitHub, handling rate limits, and conditional requests."""

    if use_cache:
        cached_response = cache.get_cached_response(url)
        if cached_response:
            if "Last-Modified" in cached_response.headers:
                headers["If-Modified-Since"] = cached_response.headers["Last-Modified"]
            elif "ETag" in cached_response.headers:
                headers["If-None-Match"] = cached_response.headers["ETag"]

    response = requests.get(url, headers=headers)

    if response.status_code == 403:
        if "X-RateLimit-Remaining" in response.headers and "X-RateLimit-Reset" in response.headers:
            handle_rate_limit(response)  # Wait, then retry (stamina will retry)
            response.raise_for_status()  # Let stamina retry.
        else:
            logger.error(f"403 Forbidden (not rate limit): {url}")
            response.raise_for_status()  # Don't retry other 403 errors

    elif response.status_code == 304:  # Not Modified
        logger.info(f"Content not modified (304): {url}")
        if not cached_response:
            raise ValueError("Received 304 but no cached response available.")
        return cached_response

    elif response.status_code != 200:
        logger.error(f"Request failed: {url} - {response.status_code} - {response.text}")
        response.raise_for_status()

    # Cache successful and cacheable responses.
    if use_cache:
        cache.cache_response(response)

    return response


def fetch_starred_repos(api_url: str, headers: dict) -> list[str]:
    """Fetches starred repositories, handling pagination."""
    starred_repos = []
    page = 1
    while True:
        paginated_url = f"{api_url}?page={page}&per_page=100"
        response = fetch_github_data(paginated_url, headers.copy())  # Use a copy
        if response is None or not response.json():
            break
        starred_repos.extend([repo["html_url"] for repo in response.json()])
        logger.info(f"Fetched page {page} with {len(response.json())} items.")
        page += 1
    return starred_repos


def get_readme_url(github_url: str, default_branch: str) -> str:
    """Constructs the raw README URL."""
    return (
        github_url.replace("github.com", "raw.githubusercontent.com")
        + f"/{default_branch}/README.md"
    )