"""Bounded HTTP extraction and stable SWAPI resource identity."""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://swapi.dev/api/"


class DataQualityError(ValueError):
    """Input violates a declared data-quality contract."""


def canonical_url(value: str, resource: str | None = None) -> str:
    """Normalise HTTP/HTTPS and slash variations without accepting other hosts."""
    if not isinstance(value, str):
        raise DataQualityError("Resource URL must be text")
    parsed = urlparse(value)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname != "swapi.dev"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 80, 443)
    ):
        raise DataQualityError("Only public swapi.dev API URLs are accepted")
    pattern = rf"/api/{resource or '[a-z]+'}/[0-9]+/?"
    if not re.fullmatch(pattern, parsed.path) or parsed.query or parsed.fragment:
        raise DataQualityError(f"Invalid {resource or 'resource'} URL")
    return urlunparse(("https", "swapi.dev", parsed.path.rstrip("/") + "/", "", "", ""))


class SwapiClient:
    """GET-only client; redirects are rejected and certificate verification stays on."""

    def __init__(self, session: requests.Session | None = None, ca_bundle: str | None = None):
        self.session = session or requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        if ca_bundle:
            self.session.verify = ca_bundle

    def get(self, url: str) -> dict:
        parsed = urlparse(url)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname != "swapi.dev"
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 80, 443)
            or not re.fullmatch(r"/api/[a-z]+/(?:[0-9]+/)?", parsed.path)
            or (parsed.query and not re.fullmatch(r"page=[1-9][0-9]*", parsed.query))
            or parsed.fragment
        ):
            raise DataQualityError("Unexpected API URL")
        target = urlunparse(parsed._replace(scheme="https", netloc="swapi.dev"))
        response = self.session.get(target, timeout=(5, 30), allow_redirects=False)
        if 300 <= response.status_code < 400:
            raise DataQualityError("Unexpected API redirect")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise DataQualityError("Expected a JSON object")
        return payload

    def fetch_all(self, resource: str) -> list[dict]:
        if resource not in {"people", "starships"}:
            raise DataQualityError("Unsupported resource")
        url, seen, rows, expected = BASE_URL + resource + "/", set(), [], None
        while url:
            # Canonical page identity prevents cycles even when the scheme changes.
            identity = urlparse(url)._replace(scheme="https").geturl()
            if identity in seen or len(seen) >= 100:
                raise DataQualityError("Pagination cycle or page limit exceeded")
            seen.add(identity)
            page = self.get(url)
            count = page.get("count")
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise DataQualityError("Invalid API count")
            if expected is None:
                expected = count
            if count != expected or not isinstance(page.get("results"), list):
                raise DataQualityError("API count changed or results are malformed")
            rows.extend(page["results"])
            url = page.get("next")
            if url is not None and not isinstance(url, str):
                raise DataQualityError("Invalid pagination link")
        urls = [canonical_url(row["url"], resource) for row in rows]
        if len(rows) != expected or len(set(urls)) != expected:
            raise DataQualityError("Incomplete or duplicate API results")
        return rows

    def close(self) -> None:
        self.session.close()
