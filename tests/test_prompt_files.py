"""Tests for bounded optional prompt-file loading."""

from pathlib import Path

import pytest

from anki_auto.prompt_files import (
    MAX_PROMPT_FILE_BYTES,
    PromptFileContent,
    read_optional_prompt_file,
)


def test_read_optional_prompt_file_preserves_active_line_order(
    tmp_path: Path,
) -> None:
    path = tmp_path / "customization.txt"
    path.write_text(
        "  Add pronunciation.  \n\n# ignored\n  # also ignored\nKeep notes short.\n",
        encoding="utf-8",
    )

    content = read_optional_prompt_file(
        path,
        setting_name="ANKI_CUSTOMIZATION_PATH",
    )

    assert content == PromptFileContent(
        path=path,
        lines=("Add pronunciation.", "Keep notes short."),
        found=True,
    )


def test_read_optional_prompt_file_preserves_duplicate_lines(tmp_path: Path) -> None:
    path = tmp_path / "blacklist.txt"
    path.write_text("chien\nchien\n", encoding="utf-8")

    content = read_optional_prompt_file(
        path,
        setting_name="ANKI_BLACKLIST_PATH",
    )

    assert content.lines == ("chien", "chien")


def test_read_optional_prompt_file_marks_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "missing.txt"

    content = read_optional_prompt_file(
        path,
        setting_name="ANKI_CUSTOMIZATION_PATH",
    )

    assert content == PromptFileContent(path=path, lines=(), found=False)


def test_read_optional_prompt_file_rejects_oversized_content(tmp_path: Path) -> None:
    path = tmp_path / "blacklist.txt"
    path.write_bytes(b"x" * (MAX_PROMPT_FILE_BYTES + 1))

    with pytest.raises(ValueError, match="ANKI_BLACKLIST_PATH.*8,192 bytes"):
        read_optional_prompt_file(path, setting_name="ANKI_BLACKLIST_PATH")


def test_read_optional_prompt_file_rejects_non_utf8_content(tmp_path: Path) -> None:
    path = tmp_path / "customization.txt"
    path.write_bytes(b"\xff\xfe")

    with pytest.raises(ValueError, match="ANKI_CUSTOMIZATION_PATH.*UTF-8"):
        read_optional_prompt_file(path, setting_name="ANKI_CUSTOMIZATION_PATH")


def test_read_optional_prompt_file_reports_unreadable_path(tmp_path: Path) -> None:
    path = tmp_path / "customization.txt"
    path.mkdir()

    with pytest.raises(ValueError, match="ANKI_CUSTOMIZATION_PATH.*could not be read"):
        read_optional_prompt_file(path, setting_name="ANKI_CUSTOMIZATION_PATH")
