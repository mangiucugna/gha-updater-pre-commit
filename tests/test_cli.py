from __future__ import annotations

from pathlib import Path

from gha_update.cli import main
from gha_update.models import EngineResult


def test_cli_returns_exit_2_for_invalid_config(git_repo: Path, monkeypatch) -> None:
    (git_repo / "pyproject.toml").write_text(
        """
[tool.gha_update]
unknown = true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(git_repo)
    exit_code = main([])

    assert exit_code == 2


def test_cli_returns_exit_1_in_check_mode_when_updates_exist(git_repo: Path, monkeypatch) -> None:
    monkeypatch.chdir(git_repo)

    def fake_run_engine(**_kwargs):
        return EngineResult(
            scanned_files=1,
            updates_found=2,
            unchanged_count=0,
            skipped_count=0,
            error_count=0,
            changed_files=(),
            decisions=(),
        )

    monkeypatch.setattr("gha_update.cli.run_engine", fake_run_engine)

    exit_code = main(["--check"])
    assert exit_code == 1
