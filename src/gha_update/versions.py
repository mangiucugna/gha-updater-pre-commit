from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from gha_update.models import TagInfo

_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
_SEMVER_PATTERN = re.compile(
    r"^v?(?P<major>0|[1-9][0-9]*)"
    r"(?:\.(?P<minor>0|[1-9][0-9]*))?"
    r"(?:\.(?P<patch>0|[1-9][0-9]*))?"
    r"(?P<suffix>[-+].+)?$"
)


@dataclass(frozen=True)
class VersionSelection:
    new_ref: str | None
    reason: str


def is_commit_sha(value: str) -> bool:
    return _SHA_PATTERN.fullmatch(value) is not None


def parse_tag(raw_tag: str) -> TagInfo | None:
    match = _SEMVER_PATTERN.fullmatch(raw_tag)
    if match is None:
        return None

    major = int(match.group("major"))
    minor_raw = match.group("minor")
    patch_raw = match.group("patch")
    suffix = match.group("suffix") or ""

    component_count = 1
    minor = 0
    patch = 0

    if minor_raw is not None:
        component_count = 2
        minor = int(minor_raw)

    if patch_raw is not None:
        component_count = 3
        patch = int(patch_raw)

    prerelease = suffix.startswith("-")
    return TagInfo(
        raw=raw_tag,
        normalized=(major, minor, patch),
        component_count=component_count,
        prerelease=prerelease,
    )


def select_update_ref(
    *,
    current_ref: str,
    available_tags: Iterable[str],
    include_prereleases: bool,
    update_scope: str,
) -> VersionSelection:
    if is_commit_sha(current_ref):
        return VersionSelection(new_ref=None, reason="sha_pinned")

    current = parse_tag(current_ref)
    if current is None:
        return VersionSelection(new_ref=None, reason="current_ref_not_semver")

    eligible_tags = _collect_eligible_tags(
        current=current,
        available_tags=available_tags,
        include_prereleases=include_prereleases,
        update_scope=update_scope,
    )
    if not eligible_tags:
        return VersionSelection(new_ref=None, reason="no_candidate_tags")

    canonical_latest = _pick_highest(eligible_tags)
    same_granularity_newer = [
        tag for tag in eligible_tags if tag.component_count == current.component_count and _is_newer(tag, current)
    ]
    candidate = _pick_highest(same_granularity_newer) if same_granularity_newer else canonical_latest

    if not _is_newer(candidate, current):
        return VersionSelection(new_ref=None, reason="already_latest")

    return VersionSelection(new_ref=candidate.raw, reason="update_available")


def select_latest_ref(
    *,
    available_tags: Iterable[str],
    include_prereleases: bool,
) -> VersionSelection:
    parsed_tags = _collect_tags_without_scope(
        available_tags=available_tags,
        include_prereleases=include_prereleases,
    )
    if not parsed_tags:
        return VersionSelection(new_ref=None, reason="no_candidate_tags")

    latest = _pick_highest(parsed_tags)
    return VersionSelection(new_ref=latest.raw, reason="lenient_latest")


def _collect_eligible_tags(
    *,
    current: TagInfo,
    available_tags: Iterable[str],
    include_prereleases: bool,
    update_scope: str,
) -> list[TagInfo]:
    eligible: list[TagInfo] = []

    for parsed in _collect_tags_without_scope(
        available_tags=available_tags,
        include_prereleases=include_prereleases,
    ):
        if update_scope == "minor_patch" and parsed.normalized[0] != current.normalized[0]:
            continue
        eligible.append(parsed)

    return eligible


def _collect_tags_without_scope(
    *,
    available_tags: Iterable[str],
    include_prereleases: bool,
) -> list[TagInfo]:
    collected: list[TagInfo] = []
    for raw_tag in available_tags:
        parsed = parse_tag(raw_tag)
        if parsed is None:
            continue
        if not include_prereleases and parsed.prerelease:
            continue
        collected.append(parsed)
    return collected


def _pick_highest(tags: list[TagInfo]) -> TagInfo:
    return max(tags, key=_version_sort_key)


def _is_newer(candidate: TagInfo, current: TagInfo) -> bool:
    return _version_sort_key(candidate) > _version_sort_key(current)


def _version_sort_key(tag: TagInfo) -> tuple[tuple[int, int, int], int, str]:
    # Stable tags win over prerelease tags for the same numeric version.
    stability_rank = 0 if tag.prerelease else 1
    return tag.normalized, stability_rank, tag.raw
