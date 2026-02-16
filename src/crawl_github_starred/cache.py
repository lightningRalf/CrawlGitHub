import hashlib
import json
import logging
import os
import time
from typing import Optional, Any

import requests

from . import config  # Import from the config module

# Configure logging
logger = logging.getLogger(__name__)


def is_cacheable_status(status_code: int) -> bool:
    """Return whether a status code is considered cacheable"""
    return status_code in {200, 203, 300, 301, 302, 307, 308, 404, 405, 410, 414, 501}

def _cache_filename(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return os.path.join(config.CACHE_DIR, f"{digest}.json")


def _extract_cache_headers(headers: dict) -> dict:
    cached = {}
    if "ETag" in headers:
        cached["ETag"] = headers["ETag"]
    if "Last-Modified" in headers:
        cached["Last-Modified"] = headers["Last-Modified"]
    return cached


def _minimal_payload(url: str, payload: Any) -> Any:
    if payload is None:
        return None
    if "/users/" in url and "/starred" in url and isinstance(payload, list):
        return [
            {"html_url": item.get("html_url")}
            for item in payload
            if isinstance(item, dict) and item.get("html_url")
        ]
    if "/repos/" in url and "/contributors" in url and isinstance(payload, list):
        return {"count": len(payload)}
    if "/repos/" in url and "/releases" in url and isinstance(payload, list):
        if payload and isinstance(payload[0], dict):
            tag = payload[0].get("tag_name")
            return [{"tag_name": tag}] if tag else []
        return []
    if "/repos/" in url and isinstance(payload, dict):
        keys = [
            "id",
            "name",
            "full_name",
            "html_url",
            "description",
            "language",
            "topics",
            "archived",
            "stargazers_count",
            "subscribers_count",
            "forks_count",
            "default_branch",
            "contributors_url",
            "releases_url",
            "pushed_at",
            "updated_at",
        ]
        minimal = {key: payload.get(key) for key in keys}
        owner = payload.get("owner") if isinstance(payload.get("owner"), dict) else None
        license_info = payload.get("license") if isinstance(payload.get("license"), dict) else None
        minimal["owner_login"] = owner.get("login") if owner else None
        minimal["license_spdx_id"] = license_info.get("spdx_id") if license_info else None
        return minimal
    return payload


def _build_response(url: str, status_code: int, headers: dict, json_data: Any) -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.headers = headers
    response._content = json.dumps(json_data).encode("utf-8")
    response.url = url
    response.encoding = "utf-8"
    return response


def _write_cache_entry(filename: str, status_code: int, headers: dict, json_data: Any) -> None:
    with open(filename, "w") as f:
        data = {
            "status_code": status_code,
            "headers": headers,
            "json_data": json_data,
            "cached_at": time.time(),
        }
        json.dump(data, f)


def get_cached_response(url: str) -> Optional[requests.Response]:
    """Retrieves a cached response if it exists and is valid."""
    filename = _cache_filename(url)
    if not os.path.exists(filename):
        return None
    try:
        with open(filename, "r") as f:
            cached_data = json.load(f)
        status_code = cached_data.get("status_code")
        if not isinstance(status_code, int) or not is_cacheable_status(status_code):
            return None
        cached_headers = cached_data.get("headers", {})
        json_data = cached_data.get("json_data")
        if json_data is None and "content" in cached_data:
            try:
                legacy_payload = json.loads(cached_data.get("content") or "null")
                json_data = _minimal_payload(url, legacy_payload)
                _write_cache_entry(
                    filename,
                    status_code,
                    _extract_cache_headers(cached_headers),
                    json_data,
                )
                cached_headers = _extract_cache_headers(cached_headers)
            except Exception:
                json_data = None
        if json_data is None:
            return None
        return _build_response(url, status_code, cached_headers, json_data)
    except Exception as e:
        logger.error(f"Error reading cache file {filename}: {e}")
        return None


def cache_response(response: requests.Response) -> None:
    """Caches a successful response to disk."""
    if not is_cacheable_status(response.status_code):
        return

    filename = _cache_filename(response.url)
    try:
        try:
            payload = response.json()
        except ValueError:
            payload = None
        minimal_payload = _minimal_payload(response.url, payload)
        cached_headers = _extract_cache_headers(dict(response.headers))
        _write_cache_entry(filename, response.status_code, cached_headers, minimal_payload)
        logger.info(f"Cached response for {response.url} in {filename}")
    except Exception as e:
        logger.error(f"Error writing to cache file {filename}: {e}")
