# Project AGENTS

## Repository-specific rules

- Consumer configuration is read from `pyproject.toml` under `[tool.gha_update]`.
- Do not introduce a separate `.gha-updater.toml` file.
- The published pre-commit hook must remain `id: gha-update`.
- Hook behavior must scan all workflow files on each run via `always_run: true` and `pass_filenames: false`.
- Update semantics should preserve current ref granularity when possible, and fall back to highest stable semver tag when same-granularity tags are unavailable.
- Default behavior should remain strict skip-and-log for ambiguous refs, with non-fatal handling for per-repo network/API failures.
