from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    tomllib_module = importlib.import_module("tomllib")
except ModuleNotFoundError:  # pragma: no cover - py3.10 fallback
    tomllib_module = importlib.import_module("tomli")

_ALLOWED_KEYS = {
    "ttl_hours",
    "strict_mode",
    "include_prereleases",
    "update_scope",
    "allow",
    "deny",
    "max_tag_pages",
    "timeout_seconds",
}

_MISSING = object()
_REPO_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class ConfigError(Exception):
    """Raised when configuration is invalid."""


@dataclass(frozen=True)
class Config:
    ttl_hours: int = 24
    strict_mode: bool = True
    include_prereleases: bool = False
    update_scope: str = "major"
    allow: tuple[str, ...] = ()
    deny: tuple[str, ...] = ()
    max_tag_pages: int = 2
    timeout_seconds: float = 10.0


def load_config(repo_root: Path) -> Config:
    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.exists():
        return Config()

    try:
        raw = tomllib_module.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"Failed to read pyproject.toml: {exc}") from exc

    tool_table = _expect_mapping(raw.get("tool"), "[tool]")
    section = _expect_mapping(tool_table.get("gha_update"), "[tool.gha_update]")

    unknown_keys = set(section) - _ALLOWED_KEYS
    if unknown_keys:
        keys = ", ".join(sorted(unknown_keys))
        raise ConfigError(f"Unknown key(s) in [tool.gha_update]: {keys}")

    ttl_hours = _read_int(section, "ttl_hours", 24, min_value=1)
    strict_mode = _read_bool(section, "strict_mode", True)
    include_prereleases = _read_bool(section, "include_prereleases", False)
    update_scope = _read_update_scope(section, "update_scope", "major")
    allow = _read_repo_key_list(section, "allow", ())
    deny = _read_repo_key_list(section, "deny", ())
    max_tag_pages = _read_int(section, "max_tag_pages", 2, min_value=1)
    timeout_seconds = _read_number(section, "timeout_seconds", 10.0, min_value=0.1)

    return Config(
        ttl_hours=ttl_hours,
        strict_mode=strict_mode,
        include_prereleases=include_prereleases,
        update_scope=update_scope,
        allow=allow,
        deny=deny,
        max_tag_pages=max_tag_pages,
        timeout_seconds=timeout_seconds,
    )


def _expect_mapping(value: Any, context: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{context} must be a table")
    return value


def _read_bool(section: dict[str, Any], key: str, default: bool) -> bool:
    value = section.get(key, _MISSING)
    if value is _MISSING:
        return default
    if not isinstance(value, bool):
        raise ConfigError(f"[tool.gha_update].{key} must be a boolean")
    return value


def _read_int(section: dict[str, Any], key: str, default: int, min_value: int) -> int:
    value = section.get(key, _MISSING)
    if value is _MISSING:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"[tool.gha_update].{key} must be an integer")
    if value < min_value:
        raise ConfigError(f"[tool.gha_update].{key} must be >= {min_value}")
    return value


def _read_number(section: dict[str, Any], key: str, default: float, min_value: float) -> float:
    value = section.get(key, _MISSING)
    if value is _MISSING:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"[tool.gha_update].{key} must be a number")
    float_value = float(value)
    if float_value < min_value:
        raise ConfigError(f"[tool.gha_update].{key} must be >= {min_value}")
    return float_value


def _read_update_scope(section: dict[str, Any], key: str, default: str) -> str:
    value = section.get(key, _MISSING)
    if value is _MISSING:
        return default
    if not isinstance(value, str):
        raise ConfigError(f"[tool.gha_update].{key} must be a string")
    if value not in {"major", "minor_patch"}:
        raise ConfigError("[tool.gha_update].update_scope must be 'major' or 'minor_patch'")
    return value


def _read_repo_key_list(section: dict[str, Any], key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = section.get(key, _MISSING)
    if value is _MISSING:
        return default
    if not isinstance(value, list):
        raise ConfigError(f"[tool.gha_update].{key} must be a list of owner/repo strings")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ConfigError(f"[tool.gha_update].{key} must contain only strings")
        repo_key = item.strip().lower()
        if not _REPO_KEY_PATTERN.fullmatch(repo_key):
            raise ConfigError(f"[tool.gha_update].{key} contains invalid owner/repo value: {item}")
        normalized.append(repo_key)

    return tuple(normalized)
