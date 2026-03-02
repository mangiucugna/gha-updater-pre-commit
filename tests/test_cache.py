from __future__ import annotations

import json
from pathlib import Path

from gha_update.cache import TagCache, _parse_cache_entry, resolve_cache_path


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


def test_resolve_cache_path_uses_repo_root_from_subdirectory(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    nested = tmp_path / "nested" / "path"
    nested.mkdir(parents=True)

    resolved = resolve_cache_path(nested)
    expected = tmp_path / ".cache" / "gha-updater-pre-commit" / "tags.json"

    assert resolved == expected


def test_resolve_cache_path_uses_repo_root_when_git_is_pointer_file(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("gitdir: /tmp/worktree\n", encoding="utf-8")
    nested = tmp_path / "nested" / "path"
    nested.mkdir(parents=True)

    resolved = resolve_cache_path(nested)
    expected = tmp_path / ".cache" / "gha-updater-pre-commit" / "tags.json"

    assert resolved == expected


def test_resolve_cache_path_falls_back_to_current_path_when_no_git_root(tmp_path: Path) -> None:
    nested = tmp_path / "no" / "git" / "here"
    nested.mkdir(parents=True)

    resolved = resolve_cache_path(nested)
    expected = nested / ".cache" / "gha-updater-pre-commit" / "tags.json"
    assert resolved == expected
