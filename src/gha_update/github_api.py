from __future__ import annotations

import json
import os
from typing import cast
from urllib import error, parse, request


class GitHubAPIError(Exception):
    """Raised when GitHub API calls fail."""


_DEFAULT_API_BASE_URL = "https://api.github.com"
_DEFAULT_TOKEN_ENV_NAME = "_".join(("GITHUB", "TOKEN"))


class GitHubClient:
    def __init__(
        self,
        *,
        timeout_seconds: float,
        max_tag_pages: int,
        api_base_url: str = _DEFAULT_API_BASE_URL,
        token_env: str | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_tag_pages = max_tag_pages
        self.api_base_url = api_base_url.rstrip("/")
        self.token_env = token_env or _DEFAULT_TOKEN_ENV_NAME
        self._validate_https_url(self.api_base_url)

    def fetch_tags(self, owner: str, repo: str) -> list[str]:
        tags: list[str] = []
        for page in range(1, self.max_tag_pages + 1):
            url = self._build_tags_url(owner=owner, repo=repo, page=page)
            response = self._get_json(url)
            if not isinstance(response, list):
                raise GitHubAPIError(f"Unexpected response type for {owner}/{repo} tags endpoint")

            page_tags: list[str] = []
            for item in response:
                tag_name = _extract_tag_name(item)
                if tag_name is not None:
                    page_tags.append(tag_name)

            tags.extend(page_tags)

            if len(response) < 100:
                break

        return tags

    def _build_tags_url(self, *, owner: str, repo: str, page: int) -> str:
        safe_owner = parse.quote(owner)
        safe_repo = parse.quote(repo)
        return f"{self.api_base_url}/repos/{safe_owner}/{safe_repo}/tags?per_page=100&page={page}"

    def _get_json(self, url: str) -> object:
        self._validate_https_url(url)

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "gha-updater-pre-commit",
        }

        token = os.getenv(self.token_env)
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = request.Request(url=url, headers=headers, method="GET")  # noqa: S310

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:  # noqa: S310
                payload = response.read().decode("utf-8")
                return json.loads(payload)
        except error.HTTPError as exc:
            raise GitHubAPIError(f"GitHub API HTTP error {exc.code} for {url}") from exc
        except error.URLError as exc:
            raise GitHubAPIError(f"GitHub API network error for {url}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise GitHubAPIError(f"GitHub API returned invalid JSON for {url}") from exc

    def _validate_https_url(self, url: str) -> None:
        parsed = parse.urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise GitHubAPIError(f"Only https GitHub API URLs are allowed: {url}")


def _extract_tag_name(item: object) -> str | None:
    if not isinstance(item, dict):
        return None

    typed_item = cast(dict[str, object], item)
    raw_name = typed_item.get("name")
    if not isinstance(raw_name, str):
        return None

    return raw_name
