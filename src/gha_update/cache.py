from __future__ import annotations

import json
from pathlib import Path
import subprocess
import time
from typing import Any

from gha_update.models import CacheEntry


_CACHE_FILENAME = "gha-updater-cache.json"
_CACHE_VERSION = 1
_MISSING = object()


class CacheError(Exception):
    """Raised when cache initialization fails."""


class TagCache:
    def __init__(self, *, path: Path, ttl_hours: int) -> None:
        self.path = path
        self.ttl_hours = ttl_hours
        self._entries = self._load_entries(path)
        self._dirty = False

    @classmethod
    def from_repo_root(cls, repo_root: Path, ttl_hours: int) -> "TagCache":
        git_dir = resolve_git_dir(repo_root)
        cache_path = git_dir / _CACHE_FILENAME
        return cls(path=cache_path, ttl_hours=ttl_hours)

    @property
    def dirty(self) -> bool:
        return self._dirty

    def get(self, repo_key: str, *, now: float | None = None) -> tuple[str, ...] | None:
        current_time = time.time() if now is None else now
        entry = self._entries.get(repo_key, _MISSING)
        if entry is _MISSING:
            return None

        age_hours = (current_time - entry.fetched_at) / 3600
        if age_hours > self.ttl_hours:
            return None

        return entry.tags

    def set(self, repo_key: str, tags: list[str], *, now: float | None = None) -> None:
        current_time = time.time() if now is None else now
        self._entries[repo_key] = CacheEntry(fetched_at=current_time, tags=tuple(tags))
        self._dirty = True

    def save(self) -> None:
        if not self._dirty:
            return

        payload = {
            "version": _CACHE_VERSION,
            "repos": {
                repo_key: {
                    "fetched_at": entry.fetched_at,
                    "tags": list(entry.tags),
                }
                for repo_key, entry in sorted(self._entries.items())
            },
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        self._dirty = False

    def _load_entries(self, path: Path) -> dict[str, CacheEntry]:
        if not path.exists():
            return {}

        try:
            raw_payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        if not isinstance(raw_payload, dict):
            return {}

        if raw_payload.get("version") != _CACHE_VERSION:
            return {}

        repos = raw_payload.get("repos")
        if not isinstance(repos, dict):
            return {}

        entries: dict[str, CacheEntry] = {}
        for repo_key, value in repos.items():
            parsed_entry = _parse_cache_entry(value)
            if parsed_entry is not None and isinstance(repo_key, str):
                entries[repo_key] = parsed_entry

        return entries


def resolve_git_dir(repo_root: Path) -> Path:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            check=True,
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        raise CacheError("Unable to locate .git directory for cache storage") from exc

    git_dir_text = completed.stdout.strip()
    if not git_dir_text:
        raise CacheError("git rev-parse --git-dir returned an empty path")

    git_dir_path = Path(git_dir_text)
    if not git_dir_path.is_absolute():
        git_dir_path = (repo_root / git_dir_path).resolve()

    return git_dir_path


def _parse_cache_entry(raw_value: Any) -> CacheEntry | None:
    if not isinstance(raw_value, dict):
        return None

    fetched_at = raw_value.get("fetched_at", _MISSING)
    tags = raw_value.get("tags", _MISSING)

    if fetched_at is _MISSING or tags is _MISSING:
        return None
    if isinstance(fetched_at, bool) or not isinstance(fetched_at, (int, float)):
        return None
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        return None

    return CacheEntry(fetched_at=float(fetched_at), tags=tuple(tags))
