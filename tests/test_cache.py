from __future__ import annotations

import json
from pathlib import Path

import pytest

from gha_update.cache import CacheError, TagCache, _parse_cache_entry, _resolve_git_path, resolve_git_dir


def test_tag_cache_save_noop_when_clean(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.json"
    cache = TagCache(path=cache_path, ttl_hours=24)

    cache.save()

    assert not cache_path.exists()


def test_tag_cache_load_ignores_invalid_payload_shapes(tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.json"

    cache_path.write_text("not-json", encoding="utf-8")
    cache = TagCache(path=cache_path, ttl_hours=24)
    assert cache.get("actions/checkout") is None

    cache_path.write_text(json.dumps([]), encoding="utf-8")
    cache = TagCache(path=cache_path, ttl_hours=24)
    assert cache.get("actions/checkout") is None

    cache_path.write_text(json.dumps({"version": 99, "repos": {}}), encoding="utf-8")
    cache = TagCache(path=cache_path, ttl_hours=24)
    assert cache.get("actions/checkout") is None

    cache_path.write_text(json.dumps({"version": 1, "repos": []}), encoding="utf-8")
    cache = TagCache(path=cache_path, ttl_hours=24)
    assert cache.get("actions/checkout") is None


def test_parse_cache_entry_validation() -> None:
    assert _parse_cache_entry("bad") is None
    assert _parse_cache_entry({"fetched_at": 1.0}) is None
    assert _parse_cache_entry({"tags": []}) is None
    assert _parse_cache_entry({"fetched_at": True, "tags": []}) is None
    assert _parse_cache_entry({"fetched_at": 1.0, "tags": [1]}) is None

    parsed = _parse_cache_entry({"fetched_at": 1.0, "tags": ["v1"]})
    assert parsed is not None
    assert parsed.tags == ("v1",)


def test_tag_cache_get_expires_by_ttl(tmp_path: Path) -> None:
    cache = TagCache(path=tmp_path / "cache.json", ttl_hours=1)
    cache.set("actions/checkout", ["v1"], now=0)

    assert cache.get("actions/checkout", now=3599) == ("v1",)
    assert cache.get("actions/checkout", now=3601) is None


def test_resolve_git_dir_from_directory(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()

    resolved = resolve_git_dir(tmp_path)

    assert resolved == git_dir.resolve()


def test_resolve_git_dir_from_subdirectory(tmp_path: Path) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    nested = tmp_path / "nested" / "path"
    nested.mkdir(parents=True)

    resolved = resolve_git_dir(nested)

    assert resolved == git_dir.resolve()


def test_resolve_git_dir_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(CacheError, match="Unable to locate"):
        resolve_git_dir(tmp_path)


def test_resolve_git_dir_from_pointer_file(tmp_path: Path) -> None:
    worktree_git_dir = tmp_path / "worktree-git"
    worktree_git_dir.mkdir()
    (tmp_path / ".git").write_text("gitdir: worktree-git\n", encoding="utf-8")

    resolved = resolve_git_dir(tmp_path)

    assert resolved == worktree_git_dir.resolve()


def test_resolve_git_dir_pointer_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pointer_path = tmp_path / ".git"

    pointer_path.write_text("invalid", encoding="utf-8")
    with pytest.raises(CacheError, match="Invalid .git pointer"):
        resolve_git_dir(tmp_path)

    pointer_path.write_text("gitdir:\n", encoding="utf-8")
    with pytest.raises(CacheError, match="does not contain a gitdir"):
        resolve_git_dir(tmp_path)

    pointer_path.write_text("gitdir: nested/.git", encoding="utf-8")

    original_read_text = Path.read_text

    def raising_read_text(
        self: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        if self == pointer_path:
            raise OSError("boom")
        return original_read_text(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", raising_read_text)
    with pytest.raises(CacheError, match="Unable to read"):
        resolve_git_dir(tmp_path)


def test_resolve_git_path_raises_for_non_file_non_dir(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.git"

    with pytest.raises(CacheError, match="Unable to locate"):
        _resolve_git_path(git_path=missing_path, git_owner_root=tmp_path)
