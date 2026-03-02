from __future__ import annotations

import io
import json
from email.message import Message
from urllib import error

import pytest

from gha_update.github_api import GitHubAPIError, GitHubClient


class DummyResponse:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload.encode("utf-8")

    def __enter__(self) -> DummyResponse:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


def test_build_tags_url_encodes_owner_and_repo() -> None:
    client = GitHubClient(timeout_seconds=1, max_tag_pages=1)

    url = client._build_tags_url(owner="acme inc", repo="my repo", page=2)

    assert "acme%20inc" in url
    assert "my%20repo" in url
    assert "page=2" in url


def test_fetch_tags_collects_multiple_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GitHubClient(timeout_seconds=1, max_tag_pages=3)

    responses = [
        [{"name": f"v{i}"} for i in range(100)],
        [{"name": "v200"}],
    ]

    def fake_get_json(_url: str) -> object:
        return responses.pop(0)

    monkeypatch.setattr(client, "_get_json", fake_get_json)

    tags = client.fetch_tags("actions", "checkout")

    assert tags[0] == "v0"
    assert tags[-1] == "v200"
    assert len(tags) == 101


def test_fetch_tags_rejects_non_list_response(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GitHubClient(timeout_seconds=1, max_tag_pages=1)
    monkeypatch.setattr(client, "_get_json", lambda _url: {"name": "v1"})

    with pytest.raises(GitHubAPIError, match="Unexpected response type"):
        client.fetch_tags("actions", "checkout")


def test_fetch_tags_ignores_non_dict_items(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GitHubClient(timeout_seconds=1, max_tag_pages=1)
    monkeypatch.setattr(client, "_get_json", lambda _url: ["bad", {"name": "v1"}])

    tags = client.fetch_tags("actions", "checkout")

    assert tags == ["v1"]


def test_fetch_tags_ignores_non_string_tag_names(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GitHubClient(timeout_seconds=1, max_tag_pages=1)
    monkeypatch.setattr(client, "_get_json", lambda _url: [{"name": 123}, {"name": "v2"}])

    tags = client.fetch_tags("actions", "checkout")

    assert tags == ["v2"]


def test_get_json_success(monkeypatch: pytest.MonkeyPatch) -> None:
    token_env = "_".join(("GITHUB", "TOKEN"))
    client = GitHubClient(timeout_seconds=1, max_tag_pages=1, token_env=token_env)
    monkeypatch.setenv(token_env, "dummy-auth-value")

    captured_headers: dict[str, str] = {}

    def fake_urlopen(req, timeout: float):
        del timeout
        captured_headers.update(dict(req.headers))
        return DummyResponse(json.dumps([{"name": "v1"}]))

    monkeypatch.setattr("gha_update.github_api.request.urlopen", fake_urlopen)

    payload = client._get_json("https://api.github.com/repos/actions/checkout/tags")

    assert isinstance(payload, list)
    assert "Authorization" in captured_headers


def test_get_json_rejects_non_https_url() -> None:
    client = GitHubClient(timeout_seconds=1, max_tag_pages=1)

    with pytest.raises(GitHubAPIError, match="Only https"):
        client._get_json("http://example.com")


@pytest.mark.parametrize(
    ("raised", "message"),
    [
        (
            error.HTTPError("https://api.github.com", 403, "Forbidden", hdrs=Message(), fp=io.BytesIO()),
            "HTTP error 403",
        ),
        (error.URLError("network down"), "network error"),
    ],
)
def test_get_json_wraps_network_errors(
    monkeypatch: pytest.MonkeyPatch,
    raised: Exception,
    message: str,
) -> None:
    client = GitHubClient(timeout_seconds=1, max_tag_pages=1)

    def fake_urlopen(_req, timeout: float):
        del timeout
        raise raised

    monkeypatch.setattr("gha_update.github_api.request.urlopen", fake_urlopen)

    with pytest.raises(GitHubAPIError, match=message):
        client._get_json("https://api.github.com/repos/actions/checkout/tags")


def test_get_json_wraps_json_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GitHubClient(timeout_seconds=1, max_tag_pages=1)

    def fake_urlopen(_req, timeout: float):
        del timeout
        return DummyResponse("not-json")

    monkeypatch.setattr("gha_update.github_api.request.urlopen", fake_urlopen)

    with pytest.raises(GitHubAPIError, match="invalid JSON"):
        client._get_json("https://api.github.com/repos/actions/checkout/tags")


def test_client_rejects_non_https_base_url() -> None:
    with pytest.raises(GitHubAPIError, match="Only https"):
        GitHubClient(timeout_seconds=1, max_tag_pages=1, api_base_url="http://api.github.com")
