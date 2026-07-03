"""Tests for the level-tagged logging helpers."""

from __future__ import annotations

import pytest

from anki_auto import logging_utils


def test_info_prefixes_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """``info`` writes an ``[INFO]``-prefixed line to stderr."""

    logging_utils.info("hello")

    captured = capsys.readouterr()
    assert captured.err == "[INFO] hello\n"
    assert captured.out == ""


def test_warning_prefixes_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """``warning`` writes a ``[WARNING]``-prefixed line to stderr."""

    logging_utils.warning("careful")

    captured = capsys.readouterr()
    assert captured.err == "[WARNING] careful\n"
    assert captured.out == ""


def test_error_prefixes_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """``error`` writes an ``[ERROR]``-prefixed line to stderr."""

    logging_utils.error("boom")

    captured = capsys.readouterr()
    assert captured.err == "[ERROR] boom\n"
    assert captured.out == ""
