# Contributing

Thanks for contributing to `gha-updater-pre-commit`.

## Development Setup

1. Clone the repository.
2. Install the project with development dependencies:

```bash
python -m pip install -e '.[dev]'
```

3. (Optional) install pre-commit hooks:

```bash
pre-commit install
```

## Local Validation

Run the same checks expected in this repository:

```bash
pre-commit run --all-files
uv run pytest
```

If `uv run` fails due to cache permissions, rerun with:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run pytest
```

## Pull Request Guidelines

- Keep changes focused and scoped.
- Add or update tests when behavior changes.
- Update docs when user-facing behavior or configuration changes.
- Include a clear PR description with motivation, approach, and risk notes.

## Commit Expectations

- Ensure the branch is up to date before opening a PR.
- Ensure checks pass locally before requesting review.
- Avoid unrelated formatting or refactor-only changes in feature or bug-fix PRs.
