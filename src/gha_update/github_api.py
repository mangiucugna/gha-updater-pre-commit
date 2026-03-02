from __future__ import annotations

import json
import os
from urllib import error, parse, request


class GitHubAPIError(Exception):
    """Raised when GitHub API calls fail."""


class GitHubClient:
    def __init__(
        self,
        *,
        timeout_seconds: float,
        max_tag_pages: int,
        api_base_url: str = "https://api.github.com",
        token_env: str = "GITHUB_TOKEN",
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_tag_pages = max_tag_pages
        self.api_base_url = api_base_url.rstrip("/")
        self.token_env = token_env

    def fetch_tags(self, owner: str, repo: str) -> list[str]:
        tags: list[str] = []
        for page in range(1, self.max_tag_pages + 1):
            url = self._build_tags_url(owner=owner, repo=repo, page=page)
            response = self._get_json(url)
            if not isinstance(response, list):
                raise GitHubAPIError(f"Unexpected response type for {owner}/{repo} tags endpoint")

            page_tags = [
                item["name"]
                for item in response
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            ]
            tags.extend(page_tags)

            if len(response) < 100:
                break

        return tags

    def _build_tags_url(self, *, owner: str, repo: str, page: int) -> str:
        safe_owner = parse.quote(owner)
        safe_repo = parse.quote(repo)
        return f"{self.api_base_url}/repos/{safe_owner}/{safe_repo}/tags?per_page=100&page={page}"

    def _get_json(self, url: str) -> object:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "gha-updater-pre-commit",
        }

        token = os.getenv(self.token_env)
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = request.Request(url=url, headers=headers, method="GET")

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload)
        except error.HTTPError as exc:
            raise GitHubAPIError(f"GitHub API HTTP error {exc.code} for {url}") from exc
        except error.URLError as exc:
            raise GitHubAPIError(f"GitHub API network error for {url}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise GitHubAPIError(f"GitHub API returned invalid JSON for {url}") from exc
