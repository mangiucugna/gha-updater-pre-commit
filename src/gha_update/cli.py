from __future__ import annotations

import argparse
from pathlib import Path

from gha_update.config import ConfigError, load_config
from gha_update.engine import EngineError, EngineOptions, run_engine
from gha_update.logging_utils import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gha-actions-autoupdate",
        description="Update GitHub Action refs in workflow files.",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Bypass cache and fetch fresh tags from GitHub.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report pending updates without writing files.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logs for skipped decisions.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logger = configure_logging(args.verbose)
    repo_root = Path.cwd()

    try:
        config = load_config(repo_root)
    except ConfigError as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    try:
        result = run_engine(
            repo_root=repo_root,
            config=config,
            options=EngineOptions(
                refresh=args.refresh,
                check=args.check,
                verbose=args.verbose,
            ),
            logger=logger,
        )
    except EngineError as exc:
        logger.error("Runtime error: %s", exc)
        return 2

    if result.scanned_files == 0:
        logger.info("No workflow files found under .github/workflows")

    if result.has_updates:
        if args.check:
            logger.info("%s update(s) available", result.updates_found)
        else:
            logger.info("Applied %s update(s)", result.updates_found)
        return 1

    logger.info("No updates needed")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
