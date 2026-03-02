from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, MutableMapping


@dataclass(frozen=True)
class TagInfo:
    raw: str
    normalized: tuple[int, int, int]
    component_count: int
    prerelease: bool


@dataclass
class ActionRef:
    file_path: Path
    node: MutableMapping[str, Any]
    key: str
    raw_uses: str
    owner: str
    repo: str
    subpath: str | None
    ref: str

    @property
    def repo_key(self) -> str:
        return f"{self.owner}/{self.repo}".lower()

    def with_ref(self, new_ref: str) -> str:
        base = f"{self.owner}/{self.repo}"
        if self.subpath:
            base = f"{base}/{self.subpath}"
        return f"{base}@{new_ref}"


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str
    file_path: Path
    action: str
    current_ref: str
    new_ref: str | None = None


@dataclass(frozen=True)
class CacheEntry:
    fetched_at: float
    tags: tuple[str, ...]


@dataclass(frozen=True)
class EngineResult:
    scanned_files: int
    updates_found: int
    unchanged_count: int
    skipped_count: int
    error_count: int
    changed_files: tuple[Path, ...]
    decisions: tuple[Decision, ...]

    @property
    def has_updates(self) -> bool:
        return self.updates_found > 0
