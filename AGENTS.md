# Project AGENTS

## Repository-specific rules

- Consumer configuration is read from `pyproject.toml` under `[tool.gha_update]`.
- Do not introduce a separate `.gha-updater.toml` file.
- The published pre-commit hook must remain `id: gha-update`.
- Hook behavior must scan all workflow files on each run via `always_run: true` and `pass_filenames: false`.
- Update semantics must respect ref pinning precision without widening: `vX` updates only to `vY` aliases (`Y>X`), `vX.Y` only to `vX.Z` aliases (`Z>Y`), and `vX.Y.Z` can update to any newer stable semver tag.
- Default behavior should remain strict skip-and-log for ambiguous refs, with non-fatal handling for per-repo network/API failures.
- For local-path pre-commit testing, `rev` must be a commit SHA (not `HEAD`) because pre-commit requires immutable refs.
- Keep project pre-commit coverage aligned with `.pre-commit-config.yaml`: core file hygiene hooks, Ruff (`ruff-check --fix` and `ruff-format`), and `uv run python -m pytest`.
- Cache storage must resolve `.git` from the current directory or any parent so CLI invocation from subdirectories behaves the same as repo-root runs.
- Keep the documented developer install path working: `python -m pip install -e '.[dev]'` must continue to install the lint/test toolchain.
- Keep README SEO improvements organic and user-readable; avoid explicit keyword lists or keyword-stuffing sections.
