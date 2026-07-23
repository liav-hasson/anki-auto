"""Read optional user-owned files that augment card-generation prompts.

This loader enforces a byte limit and filters blank/comment lines.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


MAX_PROMPT_FILE_BYTES = 8 * 1024


@dataclass(frozen=True)
class PromptFileContent:
    """One optional prompt file after bounded loading and line filtering."""

    path: Path
    lines: tuple[str, ...]
    found: bool


@dataclass(frozen=True)
class PromptFiles:
    """Customization and blacklist content resolved for one CLI run."""

    customization: PromptFileContent
    blacklist: PromptFileContent


def read_optional_prompt_file(
    path: Path,
    *,
    setting_name: str,
) -> PromptFileContent:
    """Read one optional UTF-8 file without consuming unbounded input."""

    try:
        with path.open("rb") as prompt_file:
            raw_content = prompt_file.read(MAX_PROMPT_FILE_BYTES + 1)
    except FileNotFoundError:
        return PromptFileContent(path=path, lines=(), found=False)
    except OSError as error:
        detail = error.strerror or str(error)
        raise ValueError(
            f"{setting_name} file '{path}' could not be read: {detail}"
        ) from error

    if len(raw_content) > MAX_PROMPT_FILE_BYTES:
        raise ValueError(
            f"{setting_name} file '{path}' exceeds the 8,192 bytes limit"
        )

    try:
        text = raw_content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError(
            f"{setting_name} file '{path}' must contain valid UTF-8 text"
        ) from error

    active_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            active_lines.append(line)

    return PromptFileContent(path=path, lines=tuple(active_lines), found=True)
