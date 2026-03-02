from pathlib import Path


def test_hook_manifest_enforces_all_workflow_scanning() -> None:
    manifest = (Path(__file__).resolve().parents[1] / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")

    assert "id: gha-update" in manifest
    assert "always_run: true" in manifest
    assert "pass_filenames: false" in manifest
