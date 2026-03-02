from pathlib import Path

import pytest

from gha_update.config import Config, ConfigError, load_config


def test_load_config_defaults_without_pyproject(git_repo: Path) -> None:
    config = load_config(git_repo)

    assert config == Config()


def test_load_config_from_tool_section(git_repo: Path) -> None:
    (git_repo / "pyproject.toml").write_text(
        """
[tool.gha_update]
ttl_hours = 48
strict_mode = false
include_prereleases = true
update_scope = "minor_patch"
allow = ["actions/checkout"]
deny = ["astral-sh/setup-uv"]
max_tag_pages = 3
timeout_seconds = 5
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_config(git_repo)

    assert config.ttl_hours == 48
    assert config.strict_mode is False
    assert config.include_prereleases is True
    assert config.update_scope == "minor_patch"
    assert config.allow == ("actions/checkout",)
    assert config.deny == ("astral-sh/setup-uv",)
    assert config.max_tag_pages == 3
    assert config.timeout_seconds == 5.0


def test_load_config_rejects_unknown_key(git_repo: Path) -> None:
    (git_repo / "pyproject.toml").write_text(
        """
[tool.gha_update]
unknown = true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(git_repo)
