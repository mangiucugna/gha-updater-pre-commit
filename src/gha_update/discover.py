from __future__ import annotations

from pathlib import Path


def discover_workflow_files(repo_root: Path) -> list[Path]:
    workflows_dir = repo_root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return []

    workflow_files = [
        path for path in workflows_dir.iterdir() if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}
    ]
    return sorted(workflow_files)
