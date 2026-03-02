from __future__ import annotations

import logging
from pathlib import Path

from gha_update.discover import discover_workflow_files
from gha_update.logging_utils import configure_logging, log_skip
from gha_update.parse_uses import ParsedUses, parse_uses_value
from gha_update.versions import select_latest_ref, select_update_ref
from gha_update.yaml_edit import iter_uses_nodes, load_workflow_yaml


def test_discover_workflow_files_returns_empty_when_missing(tmp_path: Path) -> None:
    assert discover_workflow_files(tmp_path) == []


def test_load_workflow_yaml_returns_empty_map_for_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.yml"
    path.write_text("", encoding="utf-8")

    data = load_workflow_yaml(path)

    assert isinstance(data, dict)


def test_iter_uses_nodes_traverses_nested_yaml(tmp_path: Path) -> None:
    path = tmp_path / "workflow.yml"
    path.write_text(
        """
jobs:
  test:
    steps:
      - uses: actions/checkout@v4
""".strip()
        + "\n",
        encoding="utf-8",
    )

    data = load_workflow_yaml(path)
    found = list(iter_uses_nodes(data))

    assert len(found) == 1
    assert found[0][2] == "actions/checkout@v4"


def test_log_skip_logs_when_verbose(caplog) -> None:
    logger = configure_logging(verbose=True)

    with caplog.at_level(logging.INFO):
        log_skip(logger, action="actions/checkout@v4", reason="demo", verbose=True)

    assert "Skipped actions/checkout@v4 (demo)" in caplog.text


def test_parse_uses_value_covers_malformed_cases() -> None:
    assert parse_uses_value("actions") == (None, "malformed_uses")
    assert parse_uses_value("actions/checkout@") == (None, "malformed_uses")
    assert parse_uses_value("actions@v1") == (None, "malformed_uses")
    assert parse_uses_value("owner!bad/repo@v1") == (None, "malformed_uses")
    assert parse_uses_value("owner/repo!bad@v1") == (None, "malformed_uses")
    assert parse_uses_value("owner/repo//path@v1") == (None, "malformed_uses")


def test_parsed_uses_helpers() -> None:
    parsed = ParsedUses(owner="actions", repo="checkout", subpath="path", ref="v4")

    assert parsed.repo_key == "actions/checkout"
    assert parsed.with_ref("v5") == "actions/checkout/path@v5"


def test_versions_no_candidates_paths() -> None:
    selection = select_update_ref(
        current_ref="v1",
        available_tags=["not-a-tag"],
        include_prereleases=False,
        update_scope="major",
    )
    assert selection.reason == "no_candidate_tags"

    latest = select_latest_ref(
        available_tags=["also-not-semver"],
        include_prereleases=False,
    )
    assert latest.reason == "no_candidate_tags"
