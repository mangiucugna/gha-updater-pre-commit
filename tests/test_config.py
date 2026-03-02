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


def test_load_config_rejects_invalid_toml(git_repo: Path) -> None:
    (git_repo / "pyproject.toml").write_text("[tool.gha_update\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="Failed to read pyproject.toml"):
        load_config(git_repo)


def test_load_config_rejects_non_table_tool_section(git_repo: Path) -> None:
    (git_repo / "pyproject.toml").write_text(
        """
[tool]
gha_update = "invalid"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="\\[tool\\.gha_update\\] must be a table"):
        load_config(git_repo)


def test_load_config_handles_missing_tool_table(git_repo: Path) -> None:
    (git_repo / "pyproject.toml").write_text(
        """
[project]
name = "demo"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_config(git_repo)
    assert config == Config()


def test_load_config_uses_default_timeout_when_omitted(git_repo: Path) -> None:
    (git_repo / "pyproject.toml").write_text(
        """
[tool.gha_update]
strict_mode = true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_config(git_repo)
    assert config.timeout_seconds == 10.0


@pytest.mark.parametrize(
    ("key", "value", "error_message"),
    [
        ("strict_mode", '"yes"', "must be a boolean"),
        ("ttl_hours", "true", "must be an integer"),
        ("ttl_hours", "0", "must be >= 1"),
        ("max_tag_pages", "0", "must be >= 1"),
        ("timeout_seconds", '"soon"', "must be a number"),
        ("timeout_seconds", "0", "must be >= 0.1"),
        ("update_scope", "1", "must be a string"),
        ("update_scope", '"patch"', "must be 'major' or 'minor_patch'"),
        ("allow", '"actions/checkout"', "must be a list of owner/repo strings"),
        ("allow", "[123]", "must contain only strings"),
        ("allow", '["bad value"]', "contains invalid owner/repo value"),
    ],
)
def test_load_config_rejects_invalid_field_values(
    git_repo: Path,
    key: str,
    value: str,
    error_message: str,
) -> None:
    (git_repo / "pyproject.toml").write_text(
        f"""
[tool.gha_update]
{key} = {value}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match=error_message):
        load_config(git_repo)
