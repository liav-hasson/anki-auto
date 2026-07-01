"""Command-line orchestration for anki-auto."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from .anki import PackagedCard, stable_audio_filename, write_apkg
from .audio import OpenAIAudioGenerator
from .models import CardBatch, GeneratedCard
from .openai_cards import OpenAICardGenerator


DEFAULT_DECK_NAME = "French Auto Deck"
DEFAULT_NOTE_MODEL_NAME = "Anki Auto French Spanish Notes v2"


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""

    parser = argparse.ArgumentParser(
        prog="anki-auto",
        description="Generate a fresh French Anki .apkg from one loose input item per line.",
    )
    parser.add_argument(
        "input", type=Path, help="Text file with one loose input item per line."
    )
    parser.add_argument("output", type=Path, help="Output .apkg path.")
    parser.add_argument(
        "--deck-name", default=DEFAULT_DECK_NAME, help="Name of the Anki deck."
    )
    parser.add_argument(
        "--card-model",
        default="gpt-4.1-mini",
        help="OpenAI model used for structured card generation.",
    )
    parser.add_argument(
        "--audio-model",
        default="gpt-4o-mini-tts",
        help="OpenAI text-to-speech model used for audio.",
    )
    parser.add_argument("--voice", default="alloy", help="OpenAI text-to-speech voice.")
    parser.add_argument(
        "--note-model-name",
        default=DEFAULT_NOTE_MODEL_NAME,
        help=(
            "Name of the Anki note model inside the package. "
            "Keep this stable for reproducible note model ids."
        ),
    )
    parser.add_argument(
        "--no-audio", action="store_true", help="Skip text-to-speech audio generation."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate card JSON and print it to stdout; do not build an .apkg.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""

    args = build_parser().parse_args(argv)
    load_dotenv()

    try:
        items = read_input_items(args.input)
        require_openai_api_key()
        cards = generate_cards(items, args.card_model)

        if args.dry_run:
            print(CardBatch(cards=cards).model_dump_json(indent=2))
            return 0

        packaged_cards = package_cards_with_audio(
            cards=cards,
            no_audio=args.no_audio,
            audio_model=args.audio_model,
            voice=args.voice,
        )
        write_apkg(
            cards=packaged_cards,
            output_path=args.output,
            deck_name=args.deck_name,
            model_name=args.note_model_name,
        )
    except (OSError, ValueError) as error:
        print(f"anki-auto: {error}", file=sys.stderr)
        return 1

    print(f"Wrote {len(cards)} cards to {args.output}")
    return 0


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


def require_openai_api_key() -> None:
    """Fail early when the OpenAI SDK cannot authenticate."""

    if not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required in the environment or a .env file")


def generate_cards(items: list[str], model: str) -> list[GeneratedCard]:
    """Generate cards for all input items."""

    generator = OpenAICardGenerator(model=model)
    cards = []
    for index, item in enumerate(items, start=1):
        print(f"Generating card {index}/{len(items)}: {item}", file=sys.stderr)
        cards.append(generator.generate(item))
    return cards


def package_cards_with_audio(
    cards: list[GeneratedCard],
    no_audio: bool,
    audio_model: str,
    voice: str,
) -> list[PackagedCard]:
    """Attach generated audio files to cards unless disabled."""

    if no_audio:
        return [PackagedCard(card=card) for card in cards]

    audio_generator = OpenAIAudioGenerator(model=audio_model, voice=voice)
    media_dir = Path(tempfile.mkdtemp(prefix="anki-auto-media-"))
    packaged_cards = []

    for index, card in enumerate(cards, start=1):
        audio_paths = []
        for example_index, example in enumerate(card.examples, start=1):
            audio_path = media_dir / stable_audio_filename(card, example_index)
            print(
                "Generating audio "
                f"{index}/{len(cards)} example {example_index}/{len(card.examples)}: "
                f"{audio_path.name}",
                file=sys.stderr,
            )
            audio_generator.generate(example.fr, audio_path)
            audio_paths.append(audio_path)
        packaged_cards.append(PackagedCard(card=card, audio_paths=tuple(audio_paths)))

    return packaged_cards


if __name__ == "__main__":
    raise SystemExit(main())
