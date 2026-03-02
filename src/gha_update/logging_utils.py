from __future__ import annotations

import logging


LOGGER_NAME = "gha_update"


def configure_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="gha-update: %(message)s")
    return logging.getLogger(LOGGER_NAME)


def log_skip(logger: logging.Logger, *, action: str, reason: str, verbose: bool) -> None:
    if not verbose:
        return
    logger.info("Skipped %s (%s)", action, reason)


def log_update(
    logger: logging.Logger,
    *,
    action: str,
    old_ref: str,
    new_ref: str,
    file_path: str,
) -> None:
    logger.info("Updated %s in %s: %s -> %s", action, file_path, old_ref, new_ref)


def log_warning(logger: logging.Logger, message: str) -> None:
    logger.warning(message)
