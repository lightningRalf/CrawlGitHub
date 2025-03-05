import json
import logging
import os
from typing import Optional

import requests

from . import config  # Import from the config module

# Configure logging
logger = logging.getLogger(__name__)


def is_cacheable_status(status_code: int) -> bool:
    """Return whether a status code is considered cacheable"""
    return status_code in {200, 203, 300, 301, 302, 307, 308, 404, 405, 410, 414, 501}

def get_cached_response(url: str) -> Optional[requests.Response]:
    """Retrieves a cached response if it exists and is valid."""
    filename = os.path.join(config.CACHE_DIR, f"{hash(url)}.json")
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                cached_data = json.load(f)
                #check that the response is cacheable:
                if not is_cacheable_status(cached_data["status_code"]):
                    return None
                # Convert headers back to a dictionary
                cached_headers = cached_data["headers"]

                response = requests.Response()
                response.status_code = cached_data["status_code"]
                response.headers = cached_headers
                response._content = cached_data["content"].encode()  # requests decodes, so we have to encode again.
                response.url = url
                response.encoding = "utf-8"

                return response
        except Exception as e:
            logger.error(f"Error reading cache file {filename}: {e}")
            return None
    return None


def cache_response(response: requests.Response) -> None:
    """Caches a successful response to disk."""
    if not is_cacheable_status(response.status_code): return

    filename = os.path.join(config.CACHE_DIR, f"{hash(response.url)}.json")
    try:
        with open(filename, "w") as f:
            data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),  # Convert CIMultiDict
                "content": response.text,  # store the decoded content
            }
            json.dump(data, f)
            logger.info(f"Cached response for {response.url} in {filename}")
    except Exception as e:
        logger.error(f"Error writing to cache file {filename}: {e}")