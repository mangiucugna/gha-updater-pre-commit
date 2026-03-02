# gha-updater-pre-commit: GitHub Actions Updater Pre-Commit Hook

`gha-update` is a Python pre-commit hook to automatically update GitHub Actions versions in workflow YAML files.

It scans `.github/workflows/*.yml` and `.yaml`, checks GitHub for newer action tags, and rewrites outdated `uses:` refs like `actions/checkout@v4` while preserving your workflow formatting.

## What This GitHub Actions Updater Does

- Scans all workflow files under `.github/workflows/` on every run.
- Finds `uses:` entries that reference GitHub actions (`owner/repo@ref` and `owner/repo/path@ref`).
- Checks GitHub for newer tags.
- Rewrites outdated refs in place.
- Exits with code `1` when updates were applied so you can review and re-stage changes.

## What It Does Not Do

- It does not update local actions (`uses: ./...`).
- It does not update Docker references (`uses: docker://...`).
- It does not rewrite SHA-pinned refs.
- It does not scan arbitrary YAML outside `.github/workflows/`.

## Installation

Add this to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/mangiucugna/gha-updater-pre-commit
    rev: v0.1
    hooks:
      - id: gha-update
```

Then install and run:

```bash
pre-commit install
pre-commit run gha-update --all-files
```

You can update hook revisions with:

```bash
pre-commit autoupdate
```

## How The Hook Runs

Hook definition:

- `id: gha-update`
- `always_run: true`
- `pass_filenames: false`

That means every commit run scans all workflow files, not just staged file arguments.

## Configuration (`pyproject.toml`)

Consumers configure behavior in their own repository `pyproject.toml`:

```toml
[tool.gha_update]
ttl_hours = 24
strict_mode = true
include_prereleases = false
update_scope = "major"
allow = []
deny = []
max_tag_pages = 2
timeout_seconds = 10
```

### Keys

- `ttl_hours` (`int`, default `24`): cache freshness window in hours.
- `strict_mode` (`bool`, default `true`): skip ambiguous refs instead of heuristic rewrites.
- `include_prereleases` (`bool`, default `false`): include prerelease tags in candidate selection.
- `update_scope` (`"major" | "minor_patch"`, default `"major"`): allow major bumps or stay in current major.
- `allow` (`list[str]`, default `[]`): allowed `owner/repo` list. Empty means update-by-default.
- `deny` (`list[str]`, default `[]`): blocked `owner/repo` list. Always takes precedence.
- `max_tag_pages` (`int`, default `2`): number of GitHub tags pages to fetch (`100` tags per page).
- `timeout_seconds` (`int | float`, default `10`): GitHub API timeout per request.

## Update Behavior

- Only semver-like tags are considered (optional `v` prefix, up to `major.minor.patch`).
- Stable tags are preferred; prereleases are ignored unless enabled.
- Pinning is respected by default:
  - `@v4` updates only on major bumps.
  - `@v4.2` updates only on minor bumps in the same major.
  - `@v4.2.1` can update to any newer stable semver tag.
- In `strict_mode = true`, ambiguous refs are skipped with log messages.
- In `strict_mode = false`, non-semver refs can be rewritten to the latest eligible semver tag.

## Commit Flow

Normal run (default write mode):

1. Hook updates workflow files.
2. Hook exits `1`.
3. You review diffs and stage changes.
4. Re-run commit.

Check mode (no writes):

```bash
gha-actions-autoupdate --check
```

- Reports pending updates.
- Exits `1` if updates are available.
- Does not modify files.

## Cache

- Cache path: `.git/gha-updater-cache.json`
- Key: `owner/repo`
- Cache writes only after successful tag fetch.
- To bypass cache:

```bash
gha-actions-autoupdate --refresh
```

## Authentication and Rate Limits

The hook uses GitHub REST API and supports optional token auth.

Set a token to improve rate limits:

```bash
export GITHUB_TOKEN=ghp_xxx
```

When API requests fail (network/rate limit/auth), the hook warns and skips affected repos.

## Troubleshooting

Run verbose mode for skip reasons:

```bash
gha-actions-autoupdate --verbose
```

Common skip reasons:

- `local_action`
- `docker_reference`
- `expression_reference`
- `malformed_uses`
- `sha_pinned`
- `current_ref_not_semver`
- `no_candidate_tags`
- `denylisted`
- `not_allowlisted`

If configuration is invalid, the hook exits `2` and prints the specific key/type issue.

## Development

Install locally:

```bash
python -m pip install -e '.[dev]'
```

Run tests:

```bash
pytest
```

Run CLI manually from a target repo root:

```bash
gha-actions-autoupdate --verbose
```

## Release and Revision Pinning

Recommended ergonomic pin:

```yaml
rev: v0.1
```

Fully reproducible pin:

```yaml
rev: v0.1.0
```

Release policy:

- Publish immutable patch tags (`v0.1.0`, `v0.1.1`, ...).
- Maintain moving minor alias tags (`v0.1`).
