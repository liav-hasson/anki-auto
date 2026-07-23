"""Command-line orchestration for anki-auto."""

from __future__ import annotations

import sys
import tempfile
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import (
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    OpenAIError,
)
from pydantic import ValidationError

from . import logging_utils
from .anki import PackagedCard, stable_audio_filename, write_apkg
from .audio import OpenAIAudioGenerator
from .config import Settings, load_settings
from .models import GeneratedCard
from .openai_cards import OpenAICardGenerator
from .options import AudioOptions, PackagingOptions
from .prompt_files import (
    PromptFileContent,
    PromptFiles,
    read_optional_prompt_file,
)


DEFAULT_NOTE_MODEL_NAME = "Anki Auto Notes v2"


class ConfirmationUnavailableError(Exception):
    """Raised when confirmation is required but stdin is not interactive."""


@dataclass(frozen=True)
class RunResult:
    """Summary of a completed CLI run."""

    card_count: int = 0
    output_path: Path | None = None


def main(argv: list[str] | None = None) -> int:
    """Run the settings-driven entrypoint and return a process exit code."""

    del argv  # kept for API stability; the entrypoint takes no arguments
    exit_code = 0

    try:
        settings = load_settings()
        result = _run(settings)
    except ConfirmationUnavailableError:
        exit_code = 1
    except KeyboardInterrupt:
        logging_utils.warning("Cancelled.")
        exit_code = 130
    except ValidationError as error:
        for detail in error.errors():
            logging_utils.error(_format_validation_error(detail))
        exit_code = 1
    except FileNotFoundError as error:
        logging_utils.error(
            f"input file '{error.filename}' not found. "
            "Create it or set ANKI_INPUT_PATH."
        )
        exit_code = 1
    except OpenAIError as error:
        logging_utils.error(_format_openai_error(error))
        exit_code = 1
    except (OSError, ValueError) as error:
        logging_utils.error(str(error))
        exit_code = 1
    else:
        if result.output_path is not None:
            logging_utils.info(f"Wrote {result.card_count} cards to {result.output_path}")

    return exit_code


def _run(settings: Settings) -> RunResult:
    """Execute the happy-path workflow after settings have loaded."""

    items = read_input_items(settings.input_path)
    prompt_files = load_prompt_files(settings)
    output_path = resolve_output_path(
        settings.output_path, overwrite=settings.overwrite_output
    )

    if not confirm_run(
        settings,
        len(items),
        prompt_files=prompt_files,
        output_path=output_path,
    ):
        logging_utils.warning("Aborted by user.")
        return RunResult()

    client = OpenAI(api_key=settings.openai_api_key)
    cards = generate_cards(
        items,
        settings,
        client=client,
        prompt_files=prompt_files,
    )

    with tempfile.TemporaryDirectory(prefix="anki-auto-media-") as media_dir:
        packaged_cards = package_cards_with_audio(
            cards=cards,
            generate_audio=settings.generate_audio,
            audio=AudioOptions(
                model=settings.audio_model,
                voice=settings.audio_voice,
                api_key=settings.openai_api_key,
                client=client,
            ),
            media_dir=Path(media_dir),
            concurrency=settings.concurrency,
        )
        write_apkg(
            cards=packaged_cards,
            output_path=output_path,
            options=PackagingOptions(
                deck_name=settings.deck_name,
                model_name=DEFAULT_NOTE_MODEL_NAME,
                target_language=settings.target_language,
                cefr_level=settings.cefr_level,
                minimal_cards=settings.minimal_cards,
            ),
        )
    return RunResult(card_count=len(cards), output_path=output_path)


def load_prompt_files(settings: Settings) -> PromptFiles:
    """Load both optional prompt files and warn when either is unavailable."""

    prompt_files = PromptFiles(
        customization=read_optional_prompt_file(
            settings.customization_path,
            setting_name="ANKI_CUSTOMIZATION_PATH",
        ),
        blacklist=read_optional_prompt_file(
            settings.blacklist_path,
            setting_name="ANKI_BLACKLIST_PATH",
        ),
    )
    _warn_unavailable_prompt_file(
        prompt_files.customization,
        label="Customization",
        active_content_name="instructions",
    )
    _warn_unavailable_prompt_file(
        prompt_files.blacklist,
        label="Blacklist",
        active_content_name="entries",
    )
    if settings.minimal_cards and prompt_files.customization.lines:
        logging_utils.warning(
            "Minimal-cards mode (ANKI_MINIMAL_CARDS) is on; customization file "
            f"'{prompt_files.customization.path}' will be ignored."
        )
    return prompt_files


def _warn_unavailable_prompt_file(
    content: PromptFileContent,
    *,
    label: str,
    active_content_name: str,
) -> None:
    feature = label.casefold()
    if not content.found:
        logging_utils.warning(
            f"{label} file not found; {feature} will not be used. "
            f"Expected path: {content.path}"
        )
    elif not content.lines:
        logging_utils.warning(
            f"{label} file has no active {active_content_name}; "
            f"{feature} will not be used. Path: {content.path}"
        )


def _prompt_file_status(content: PromptFileContent) -> str:
    if not content.found:
        return "not found"
    line_count = len(content.lines)
    unit = "line" if line_count == 1 else "lines"
    return f"{line_count} active {unit}"


def confirm_run(
    settings: Settings,
    item_count: int,
    *,
    prompt_files: PromptFiles,
    output_path: Path | None = None,
) -> bool:
    """Show the resolved run summary and gate paid generation on confirmation.

    Return ``True`` when generation should proceed and ``False`` when the user
    declines interactively. Raise :class:`ConfirmationUnavailableError` when
    confirmation is required but no interactive terminal is available.
    """

    _print_run_summary(
        settings,
        item_count,
        prompt_files=prompt_files,
        output_path=output_path,
    )

    if settings.assume_yes:
        logging_utils.info("Proceeding without confirmation (ANKI_ASSUME_YES).")
        return True

    if not sys.stdin.isatty():
        logging_utils.error(
            "Confirmation required but no interactive terminal is available. "
            "Set ANKI_ASSUME_YES=true to bypass the prompt."
        )
        raise ConfirmationUnavailableError

    response = input("Proceed? [y/N] ").strip().lower()
    return response in {"y", "yes"}


def _print_run_summary(
    settings: Settings,
    item_count: int,
    *,
    prompt_files: PromptFiles,
    output_path: Path | None = None,
) -> None:
    """Print the resolved run configuration before paid generation begins."""

    resolved_output_path = output_path if output_path is not None else settings.output_path
    if settings.generate_audio:
        audio_value = f"on (model: {settings.audio_model}, voice: {settings.audio_voice})"
    else:
        audio_value = "off"
    rows = [
        ("origin language", settings.origin_language),
        ("target language", settings.target_language),
        ("notes language", settings.notes_language),
        ("CEFR level", settings.cefr_level),
        ("text model", settings.text_model),
        ("audio", audio_value),
        ("deck name", settings.deck_name),
        ("input path", settings.input_path),
        ("output path", resolved_output_path),
        ("overwrite output", "on" if settings.overwrite_output else "off"),
        ("minimal cards", "on" if settings.minimal_cards else "off"),
        (
            "customization",
            f"{prompt_files.customization.path} "
            f"({_prompt_file_status(prompt_files.customization)})",
        ),
        (
            "blacklist",
            f"{prompt_files.blacklist.path} "
            f"({_prompt_file_status(prompt_files.blacklist)})",
        ),
        ("items", item_count),
    ]
    label_width = max(len(label) for label, _ in rows)
    logging_utils.info("About to generate cards with the following settings:")
    for label, value in rows:
        logging_utils.info(f"  {label + ':':<{label_width + 1}} {value}")


def resolve_output_path(path: Path, *, overwrite: bool) -> Path:
    """Return the path to write to, avoiding collisions unless overwriting.

    When ``overwrite`` is set or the path is free, ``path`` is returned as-is.
    Otherwise the first available ``<stem>_<n><suffix>`` name is returned.
    """

    if overwrite or not path.exists():
        return path
    index = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            logging_utils.info(
                f"Output '{path}' exists; writing to '{candidate}' to avoid overwriting."
            )
            return candidate
        index += 1

def _format_validation_error(detail: Mapping[str, Any]) -> str:
    """Render one pydantic error, echoing the offending value when meaningful."""

    location = ".".join(str(part) for part in detail["loc"])
    message = detail["msg"]
    if not location:
        return message
    value = detail.get("input")
    if detail.get("type") != "missing" and value not in (None, ""):
        return f"{location}: {value!r} is invalid. {message}"
    return f"{location}: {message}"


def _format_openai_error(error: OpenAIError) -> str:
    """Render a friendly, traceback-free line for an upstream OpenAI failure."""

    if isinstance(error, AuthenticationError):
        return (
            "OpenAI authentication failed. Check OPENAI_API_KEY — "
            "https://platform.openai.com/account/api-keys"
        )
    if isinstance(error, NotFoundError):
        return (
            "OpenAI model not found. Check ANKI_TEXT_MODEL / ANKI_AUDIO_MODEL — "
            "https://platform.openai.com/docs/models"
        )
    if isinstance(error, BadRequestError):
        return f"OpenAI rejected the request: {error}"
    return f"OpenAI request failed: {error}"


def read_input_items(input_path: Path) -> list[str]:
    """Read one loose input item per non-empty line."""

    lines = input_path.read_text(encoding="utf-8").splitlines()
    items = [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not items:
        raise ValueError(f"no input items found in {input_path}")
    return items


def generate_cards(
    items: list[str],
    settings: Settings,
    *,
    client: OpenAI,
    prompt_files: PromptFiles,
) -> list[GeneratedCard]:
    """Generate cards concurrently using one immutable prompt-file snapshot."""

    generator = OpenAICardGenerator(
        prompt_config=settings.prompt_config(
            customization=prompt_files.customization.lines,
            blacklist=prompt_files.blacklist.lines,
        ),
        minimal_cards=settings.minimal_cards,
        model=settings.text_model,
        api_key=settings.openai_api_key,
        client=client,
        reasoning_effort=settings.reasoning_effort,
    )
    total = len(items)
    cards: list[GeneratedCard] = []
    with ThreadPoolExecutor(max_workers=settings.concurrency) as executor:
        results = executor.map(generator.generate, items)
        try:
            for index, (item, card) in enumerate(zip(items, results), start=1):
                logging_utils.info(f"Generated card {index}/{total}: {item}")
                cards.append(card)
        except KeyboardInterrupt:
            executor.shutdown(wait=False, cancel_futures=True)
            raise
    return cards


def package_cards_with_audio(
    cards: list[GeneratedCard],
    *,
    generate_audio: bool,
    audio: AudioOptions,
    media_dir: Path,
    concurrency: int,
) -> list[PackagedCard]:
    """Attach generated audio files to cards concurrently unless disabled."""

    if not generate_audio:
        return [PackagedCard(card=card) for card in cards]

    audio_generator = OpenAIAudioGenerator(
        model=audio.model,
        voice=audio.voice,
        api_key=audio.api_key,
        client=audio.client,
    )
    jobs = [
        (
            card_index,
            example.target,
            media_dir / stable_audio_filename(card, example_index),
        )
        for card_index, card in enumerate(cards)
        for example_index, example in enumerate(card.examples, start=1)
    ]
    audio_paths: dict[int, list[Path]] = {index: [] for index in range(len(cards))}
    total = len(jobs)

    def _run(job: tuple[int, str, Path]) -> tuple[int, Path]:
        card_index, text, output_path = job
        audio_generator.generate(text, output_path)
        return card_index, output_path

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = executor.map(_run, jobs)
        try:
            for index, (card_index, output_path) in enumerate(results, start=1):
                logging_utils.info(f"Generated audio {index}/{total}: {output_path.name}")
                audio_paths[card_index].append(output_path)
        except KeyboardInterrupt:
            executor.shutdown(wait=False, cancel_futures=True)
            raise

    return [
        PackagedCard(card=card, audio_paths=tuple(audio_paths[card_index]))
        for card_index, card in enumerate(cards)
    ]


if __name__ == "__main__":
    raise SystemExit(main())
