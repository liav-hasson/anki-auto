"""Minimal level-tagged stderr logging helpers for the CLI."""

from __future__ import annotations

import sys


def info(message: str) -> None:
    """Print an informational message to stderr with an ``[INFO]`` prefix."""

    print(f"[INFO] {message}", file=sys.stderr)


def warning(message: str) -> None:
    """Print a warning message to stderr with a ``[WARNING]`` prefix."""

    print(f"[WARNING] {message}", file=sys.stderr)


def error(message: str) -> None:
    """Print an error message to stderr with an ``[ERROR]`` prefix."""

    print(f"[ERROR] {message}", file=sys.stderr)
