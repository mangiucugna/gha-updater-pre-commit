from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from gha_update.cache import CacheError, TagCache
from gha_update.config import Config
from gha_update.discover import discover_workflow_files
from gha_update.github_api import GitHubAPIError, GitHubClient
from gha_update.logging_utils import log_skip, log_update, log_warning
from gha_update.models import ActionRef, Decision, EngineResult
from gha_update.parse_uses import parse_uses_value
from gha_update.versions import VersionSelection, select_latest_ref, select_update_ref
from gha_update.yaml_edit import (
    iter_uses_nodes,
    load_workflow_yaml,
    write_workflow_yaml,
)


class EngineError(Exception):
    """Raised when the update engine cannot continue."""


class TagFetcher(Protocol):
    def fetch_tags(self, owner: str, repo: str) -> list[str]: ...


@dataclass(frozen=True)
class EngineOptions:
    refresh: bool = False
    check: bool = False
    verbose: bool = False


def run_engine(
    *,
    repo_root: Path,
    config: Config,
    options: EngineOptions,
    logger: logging.Logger,
    tag_fetcher: TagFetcher | None = None,
) -> EngineResult:
    workflow_files = discover_workflow_files(repo_root)
    decisions: list[Decision] = []
    changed_files: set[Path] = set()

    updates_found = 0
    unchanged_count = 0
    skipped_count = 0
    error_count = 0

    fetcher = tag_fetcher or GitHubClient(
        timeout_seconds=config.timeout_seconds,
        max_tag_pages=config.max_tag_pages,
    )

    try:
        cache = TagCache.from_repo_root(repo_root=repo_root, ttl_hours=config.ttl_hours)
    except CacheError as exc:
        raise EngineError(str(exc)) from exc

    tags_by_repo: dict[str, tuple[str, ...] | None] = {}

    for workflow_path in workflow_files:
        try:
            document = load_workflow_yaml(workflow_path)
        except Exception as exc:  # pragma: no cover - defensive for parser internals
            raise EngineError(f"Failed to parse workflow file {workflow_path}: {exc}") from exc

        file_changed = False
        for node, key, uses_value in iter_uses_nodes(document):
            action, skip_reason = parse_uses_value(uses_value)
            if action is None:
                reason = skip_reason or "unknown_skip"
                skipped_count += 1
                _record_parse_skip(
                    decisions=decisions,
                    workflow_path=workflow_path,
                    action=uses_value,
                    reason=reason,
                    logger=logger,
                    verbose=options.verbose,
                )
                continue

            action_ref = ActionRef(
                file_path=workflow_path,
                node=node,
                key=key,
                raw_uses=uses_value,
                owner=action.owner,
                repo=action.repo,
                subpath=action.subpath,
                ref=action.ref,
            )

            allow_decision = _passes_allow_deny_filters(action_ref=action_ref, config=config)
            if allow_decision is not None:
                skipped_count += 1
                decisions.append(allow_decision)
                log_skip(
                    logger,
                    action=action_ref.raw_uses,
                    reason=allow_decision.reason,
                    verbose=options.verbose,
                )
                continue

            tags = _get_tags_for_repo(
                action_ref=action_ref,
                options=options,
                logger=logger,
                fetcher=fetcher,
                cache=cache,
                tags_by_repo=tags_by_repo,
            )
            if tags is None:
                error_count += 1
                _record_fetch_error(
                    decisions=decisions,
                    workflow_path=workflow_path,
                    action_ref=action_ref,
                )
                continue

            selection = select_update_ref(
                current_ref=action_ref.ref,
                available_tags=tags,
                include_prereleases=config.include_prereleases,
                update_scope=config.update_scope,
            )
            if selection.new_ref is None and selection.reason == "current_ref_not_semver" and not config.strict_mode:
                selection = select_latest_ref(
                    available_tags=tags,
                    include_prereleases=config.include_prereleases,
                )

            if selection.new_ref is None:
                _record_non_update_decision(
                    decisions=decisions,
                    workflow_path=workflow_path,
                    action_ref=action_ref,
                    selection=selection,
                    logger=logger,
                    verbose=options.verbose,
                )
                if selection.reason == "already_latest":
                    unchanged_count += 1
                else:
                    skipped_count += 1
                continue

            updates_found += 1
            decisions.append(
                Decision(
                    status="updated",
                    reason="update_available",
                    file_path=workflow_path,
                    action=action_ref.raw_uses,
                    current_ref=action_ref.ref,
                    new_ref=selection.new_ref,
                )
            )

            if not options.check:
                action_ref.node[action_ref.key] = action_ref.with_ref(selection.new_ref)
                file_changed = True
                changed_files.add(workflow_path)

            log_update(
                logger,
                action=action_ref.raw_uses,
                old_ref=action_ref.ref,
                new_ref=selection.new_ref,
                file_path=_format_path(workflow_path, repo_root),
            )

        if file_changed:
            write_workflow_yaml(workflow_path, document)

    if cache.dirty:
        cache.save()

    return EngineResult(
        scanned_files=len(workflow_files),
        updates_found=updates_found,
        unchanged_count=unchanged_count,
        skipped_count=skipped_count,
        error_count=error_count,
        changed_files=tuple(sorted(changed_files)),
        decisions=tuple(decisions),
    )


def _passes_allow_deny_filters(action_ref: ActionRef, config: Config) -> Decision | None:
    if action_ref.repo_key in config.deny:
        return Decision(
            status="skipped",
            reason="denylisted",
            file_path=action_ref.file_path,
            action=action_ref.raw_uses,
            current_ref=action_ref.ref,
        )

    if config.allow and action_ref.repo_key not in config.allow:
        return Decision(
            status="skipped",
            reason="not_allowlisted",
            file_path=action_ref.file_path,
            action=action_ref.raw_uses,
            current_ref=action_ref.ref,
        )

    return None


def _get_tags_for_repo(
    *,
    action_ref: ActionRef,
    options: EngineOptions,
    logger: logging.Logger,
    fetcher: TagFetcher,
    cache: TagCache,
    tags_by_repo: dict[str, tuple[str, ...] | None],
) -> tuple[str, ...] | None:
    repo_key = action_ref.repo_key
    if repo_key in tags_by_repo:
        return tags_by_repo[repo_key]

    if not options.refresh:
        cached = cache.get(repo_key)
        if cached is not None:
            tags_by_repo[repo_key] = cached
            return cached

    try:
        fetched_tags = tuple(fetcher.fetch_tags(action_ref.owner, action_ref.repo))
    except GitHubAPIError as exc:
        log_warning(logger, f"Failed to fetch tags for {repo_key}: {exc}")
        tags_by_repo[repo_key] = None
        return None

    cache.set(repo_key, list(fetched_tags))
    tags_by_repo[repo_key] = fetched_tags
    return fetched_tags


def _record_parse_skip(
    *,
    decisions: list[Decision],
    workflow_path: Path,
    action: str,
    reason: str,
    logger: logging.Logger,
    verbose: bool,
) -> None:
    decisions.append(
        Decision(
            status="skipped",
            reason=reason,
            file_path=workflow_path,
            action=action,
            current_ref="",
        )
    )
    log_skip(logger, action=action, reason=reason, verbose=verbose)


def _record_fetch_error(
    *,
    decisions: list[Decision],
    workflow_path: Path,
    action_ref: ActionRef,
) -> None:
    decisions.append(
        Decision(
            status="error",
            reason="failed_to_fetch_tags",
            file_path=workflow_path,
            action=action_ref.raw_uses,
            current_ref=action_ref.ref,
        )
    )


def _record_non_update_decision(
    *,
    decisions: list[Decision],
    workflow_path: Path,
    action_ref: ActionRef,
    selection: VersionSelection,
    logger: logging.Logger,
    verbose: bool,
) -> None:
    status = "unchanged" if selection.reason == "already_latest" else "skipped"
    decisions.append(
        Decision(
            status=status,
            reason=selection.reason,
            file_path=workflow_path,
            action=action_ref.raw_uses,
            current_ref=action_ref.ref,
        )
    )
    log_skip(
        logger,
        action=action_ref.raw_uses,
        reason=selection.reason,
        verbose=verbose,
    )


def _format_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)
