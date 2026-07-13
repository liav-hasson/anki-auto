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
    output_path = resolve_output_path(
        settings.output_path, overwrite=settings.overwrite_output
    )

    if not confirm_run(settings, len(items), output_path=output_path):
        logging_utils.warning("Aborted by user.")
        return RunResult()

    client = OpenAI(api_key=settings.openai_api_key)
    cards = generate_cards(items, settings, client=client)

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


def confirm_run(
    settings: Settings,
    item_count: int,
    *,
    output_path: Path | None = None,
) -> bool:
    """Show the resolved run summary and gate paid generation on confirmation.

    Returns ``True`` when generation should proceed and ``False`` when the user
    declines interactively. Raises :class:`ConfirmationUnavailableError` when
    confirmation is required but no interactive terminal is available.
    """

    _print_run_summary(settings, item_count, output_path=output_path)

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
    output_path: Path | None = None,
) -> None:
    """Print the resolved run configuration before paid generation begins."""

    resolved_output_path = output_path if output_path is not None else settings.output_path
    if settings.generate_audio:
        audio_line = (
            f"audio model:     {settings.audio_model} (voice: {settings.audio_voice})"
        )
    else:
        audio_line = "audio:           disabled"
    for line in (
        "About to generate cards with the following settings:",
        f"  origin language: {settings.origin_language}",
        f"  target language: {settings.target_language}",
        f"  notes language:  {settings.notes_language}",
        f"  CEFR level:      {settings.cefr_level}",
        f"  text model:      {settings.text_model}",
        f"  {audio_line}",
        f"  deck name:       {settings.deck_name}",
        f"  input path:      {settings.input_path}",
        f"  output path:     {resolved_output_path}",
        f"  overwrite output:{' on' if settings.overwrite_output else ' off'}",
        f"  minimal cards:   {'on' if settings.minimal_cards else 'off'}",
        f"  items:           {item_count}",
    ):
        logging_utils.info(line)


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
    items: list[str], settings: Settings, *, client: OpenAI
) -> list[GeneratedCard]:
    """Generate cards for all input items concurrently, preserving input order."""

    generator = OpenAICardGenerator(
        prompt_config=settings.prompt_config(),
        minimal_cards=settings.minimal_cards,
        model=settings.text_model,
        api_key=settings.openai_api_key,
        client=client,
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
