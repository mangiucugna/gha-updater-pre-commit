from __future__ import annotations

import json
from pathlib import Path

from gha_update.config import Config
from gha_update.engine import EngineOptions, run_engine
from gha_update.github_api import GitHubAPIError
from gha_update.logging_utils import configure_logging


class FakeFetcher:
    def __init__(self, tags_by_repo: dict[str, list[str]], fail_repos: set[str] | None = None) -> None:
        self.tags_by_repo = tags_by_repo
        self.fail_repos = fail_repos or set()
        self.calls: list[str] = []

    def fetch_tags(self, owner: str, repo: str) -> list[str]:
        repo_key = f"{owner}/{repo}".lower()
        self.calls.append(repo_key)
        if repo_key in self.fail_repos:
            raise GitHubAPIError("forced failure")
        return self.tags_by_repo.get(repo_key, [])


def test_engine_updates_and_preserves_comments(git_repo: Path) -> None:
    workflow_path = _write_workflow(
        git_repo,
        """
name: CI
on: [push]
jobs:
  lint:
    steps:
      - # keep this comment
        uses: actions/checkout@v4
""".strip()
        + "\n",
    )

    fetcher = FakeFetcher({"actions/checkout": ["v4", "v5", "v5.1.0"]})
    logger = configure_logging(verbose=False)

    result = run_engine(
        repo_root=git_repo,
        config=Config(),
        options=EngineOptions(),
        logger=logger,
        tag_fetcher=fetcher,
    )

    updated_text = workflow_path.read_text(encoding="utf-8")
    assert "actions/checkout@v5" in updated_text
    assert "# keep this comment" in updated_text
    assert result.updates_found == 1
    assert result.has_updates


def test_engine_check_mode_does_not_write_files(git_repo: Path) -> None:
    workflow_path = _write_workflow(
        git_repo,
        """
name: CI
jobs:
  test:
    steps:
      - uses: actions/checkout@v4
""".strip()
        + "\n",
    )

    fetcher = FakeFetcher({"actions/checkout": ["v4", "v5"]})
    logger = configure_logging(verbose=False)

    result = run_engine(
        repo_root=git_repo,
        config=Config(),
        options=EngineOptions(check=True),
        logger=logger,
        tag_fetcher=fetcher,
    )

    unchanged_text = workflow_path.read_text(encoding="utf-8")
    assert "actions/checkout@v4" in unchanged_text
    assert "actions/checkout@v5" not in unchanged_text
    assert result.updates_found == 1
    assert result.changed_files == ()


def test_engine_handles_reusable_workflow_subpath(git_repo: Path) -> None:
    workflow_path = _write_workflow(
        git_repo,
        """
name: CI
jobs:
  deploy:
    uses: acme/platform/.github/workflows/release.yml@v1
""".strip()
        + "\n",
    )

    fetcher = FakeFetcher({"acme/platform": ["v1", "v2"]})
    logger = configure_logging(verbose=False)

    run_engine(
        repo_root=git_repo,
        config=Config(),
        options=EngineOptions(),
        logger=logger,
        tag_fetcher=fetcher,
    )

    updated_text = workflow_path.read_text(encoding="utf-8")
    assert "acme/platform/.github/workflows/release.yml@v2" in updated_text


def test_engine_respects_allow_and_deny_lists(git_repo: Path) -> None:
    workflow_path = _write_workflow(
        git_repo,
        """
name: CI
jobs:
  test:
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
""".strip()
        + "\n",
    )

    config = Config(
        allow=("actions/checkout",),
        deny=("astral-sh/setup-uv",),
    )

    fetcher = FakeFetcher(
        {
            "actions/checkout": ["v4", "v5"],
            "astral-sh/setup-uv": ["v4", "v5"],
        }
    )
    logger = configure_logging(verbose=False)

    run_engine(
        repo_root=git_repo,
        config=config,
        options=EngineOptions(),
        logger=logger,
        tag_fetcher=fetcher,
    )

    updated_text = workflow_path.read_text(encoding="utf-8")
    assert "actions/checkout@v5" in updated_text
    assert "astral-sh/setup-uv@v4" in updated_text


def test_engine_respects_minor_patch_scope(git_repo: Path) -> None:
    workflow_path = _write_workflow(
        git_repo,
        """
name: CI
jobs:
  test:
    steps:
      - uses: actions/checkout@v4.1
""".strip()
        + "\n",
    )

    config = Config(update_scope="minor_patch")
    fetcher = FakeFetcher({"actions/checkout": ["v4.2", "v5", "v5.1.0"]})
    logger = configure_logging(verbose=False)

    run_engine(
        repo_root=git_repo,
        config=config,
        options=EngineOptions(),
        logger=logger,
        tag_fetcher=fetcher,
    )

    updated_text = workflow_path.read_text(encoding="utf-8")
    assert "actions/checkout@v4.2" in updated_text
    assert "actions/checkout@v5" not in updated_text


def test_engine_skips_sha_pinned_refs(git_repo: Path) -> None:
    workflow_path = _write_workflow(
        git_repo,
        """
name: CI
jobs:
  test:
    steps:
      - uses: actions/checkout@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
""".strip()
        + "\n",
    )

    fetcher = FakeFetcher({"actions/checkout": ["v4", "v5"]})
    logger = configure_logging(verbose=False)

    result = run_engine(
        repo_root=git_repo,
        config=Config(),
        options=EngineOptions(),
        logger=logger,
        tag_fetcher=fetcher,
    )

    updated_text = workflow_path.read_text(encoding="utf-8")
    assert "actions/checkout@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in updated_text
    assert result.updates_found == 0


def test_engine_lenient_mode_updates_non_semver_refs(git_repo: Path) -> None:
    workflow_path = _write_workflow(
        git_repo,
        """
name: CI
jobs:
  test:
    steps:
      - uses: actions/checkout@main
""".strip()
        + "\n",
    )

    fetcher = FakeFetcher({"actions/checkout": ["v4", "v5"]})
    logger = configure_logging(verbose=False)

    result = run_engine(
        repo_root=git_repo,
        config=Config(strict_mode=False),
        options=EngineOptions(),
        logger=logger,
        tag_fetcher=fetcher,
    )

    updated_text = workflow_path.read_text(encoding="utf-8")
    assert "actions/checkout@v5" in updated_text
    assert result.updates_found == 1


def test_engine_uses_cache_when_fresh(git_repo: Path) -> None:
    _write_workflow(
        git_repo,
        """
name: CI
jobs:
  test:
    steps:
      - uses: actions/checkout@v4
""".strip()
        + "\n",
    )

    fetcher = FakeFetcher({"actions/checkout": ["v4"]})
    logger = configure_logging(verbose=False)

    run_engine(
        repo_root=git_repo,
        config=Config(),
        options=EngineOptions(),
        logger=logger,
        tag_fetcher=fetcher,
    )
    run_engine(
        repo_root=git_repo,
        config=Config(),
        options=EngineOptions(),
        logger=logger,
        tag_fetcher=fetcher,
    )

    assert fetcher.calls.count("actions/checkout") == 1


def test_engine_refetches_when_cache_expired(git_repo: Path) -> None:
    _write_workflow(
        git_repo,
        """
name: CI
jobs:
  test:
    steps:
      - uses: actions/checkout@v4
""".strip()
        + "\n",
    )

    fetcher = FakeFetcher({"actions/checkout": ["v4"]})
    logger = configure_logging(verbose=False)

    run_engine(
        repo_root=git_repo,
        config=Config(),
        options=EngineOptions(),
        logger=logger,
        tag_fetcher=fetcher,
    )

    cache_path = git_repo / ".git" / "gha-updater-cache.json"
    cache_data = json.loads(cache_path.read_text(encoding="utf-8"))
    cache_data["repos"]["actions/checkout"]["fetched_at"] = 0
    cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

    run_engine(
        repo_root=git_repo,
        config=Config(),
        options=EngineOptions(),
        logger=logger,
        tag_fetcher=fetcher,
    )

    assert fetcher.calls.count("actions/checkout") == 2


def test_engine_refresh_bypasses_cache(git_repo: Path) -> None:
    _write_workflow(
        git_repo,
        """
name: CI
jobs:
  test:
    steps:
      - uses: actions/checkout@v4
""".strip()
        + "\n",
    )

    fetcher = FakeFetcher({"actions/checkout": ["v4"]})
    logger = configure_logging(verbose=False)

    run_engine(
        repo_root=git_repo,
        config=Config(),
        options=EngineOptions(),
        logger=logger,
        tag_fetcher=fetcher,
    )
    run_engine(
        repo_root=git_repo,
        config=Config(),
        options=EngineOptions(refresh=True),
        logger=logger,
        tag_fetcher=fetcher,
    )

    assert fetcher.calls.count("actions/checkout") == 2


def test_engine_handles_api_failure_without_crashing(git_repo: Path) -> None:
    _write_workflow(
        git_repo,
        """
name: CI
jobs:
  test:
    steps:
      - uses: actions/checkout@v4
""".strip()
        + "\n",
    )

    fetcher = FakeFetcher({}, fail_repos={"actions/checkout"})
    logger = configure_logging(verbose=False)

    result = run_engine(
        repo_root=git_repo,
        config=Config(),
        options=EngineOptions(),
        logger=logger,
        tag_fetcher=fetcher,
    )

    assert result.error_count == 1
    assert result.updates_found == 0


def _write_workflow(repo_root: Path, contents: str) -> Path:
    workflows_dir = repo_root / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    path = workflows_dir / "ci.yml"
    path.write_text(contents, encoding="utf-8")
    return path
