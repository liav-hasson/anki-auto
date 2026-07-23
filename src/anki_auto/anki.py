"""Build directly importable Anki packages."""

from __future__ import annotations

import hashlib
import html
import os
import tempfile
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import genanki

from .models import (
    GeneratedCard,
    NoteItem,
)
from .options import PackagingOptions


FIELD_NAMES = ["FrontText", "BackText", "BackAudio"]
NOTE_EXAMPLE_STYLE = "color: #39ff14; font-style: italic;"
SECTION_BREAK = "<br><br>"
LINE_BREAK = "<br>"
CARD_CSS = """
.card {
    font-family: Arial;
    font-size: 20px;
    text-align: center;
}
""".strip()

NOTE_SECTION_LABELS = {
    "word_family": "Word family",
    "related_vocab": "Related vocab",
}


@dataclass(frozen=True)
class PackagedCard:
    """A generated card plus optional local audio files."""

    card: GeneratedCard
    audio_paths: tuple[Path, ...] = field(default_factory=tuple)


def slug(value: str) -> str:
    """Build a Unicode-aware slug with a hash fallback for symbol-only text."""

    normalized = unicodedata.normalize("NFKC", value.strip()).casefold()
    parts: list[str] = []
    previous_was_separator = False

    for character in normalized:
        if character.isalnum():
            parts.append(character)
            previous_was_separator = False
        elif parts and not previous_was_separator:
            parts.append("-")
            previous_was_separator = True

    slug_value = "".join(parts).strip("-")
    if slug_value:
        return slug_value

    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"tag-{digest}"


def build_card_tags(target_language: str, cefr_level: str) -> list[str]:
    """Build the two deterministic, namespaced Anki tags for every card."""

    return [f"lang::{slug(target_language)}", f"level::{slug(cefr_level)}"]



def stable_int_id(value: str) -> int:
    """Create a stable positive Anki id from text."""

    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return int(digest[:15], 16)


def stable_note_guid(card: GeneratedCard) -> str:
    """Create a stable note guid from source and card content."""

    return genanki.guid_for(
        "front-text-back-text-v2",
        card.source,
        card.origin_core,
        card.target_core,
    )


def stable_audio_filename(
    card: GeneratedCard,
    example_index: int,
    extension: str = ".mp3",
) -> str:
    """Create a stable media filename for a card example."""

    if example_index < 1 or example_index > len(card.examples):
        raise ValueError("example_index must identify an existing example")

    example = card.examples[example_index - 1]
    digest = hashlib.sha1(
        "\n".join(
            [card.source, card.target_core, str(example_index), example.target]
        ).encode("utf-8")
    ).hexdigest()[:16]
    source_slug = slug(card.source)[:40]
    prefix = source_slug or "card"
    return f"anki-auto-{prefix}-{example_index}-{digest}{extension}"


def build_model(model_name: str) -> genanki.Model:
    """Build the Anki note model used by this tool."""

    return genanki.Model(
        stable_int_id(f"anki-auto-model:{model_name}"),
        model_name,
        fields=[{"name": field_name} for field_name in FIELD_NAMES],
        templates=[
            {
                "name": "Card 1",
                "qfmt": """
{{FrontText}}
""".strip(),
                "afmt": """
{{FrontSide}}
<hr id=answer>
{{BackText}}
<div class="anki-auto-audio">{{BackAudio}}</div>
""".strip(),
            }
        ],
        css=CARD_CSS,
    )


def build_deck(deck_name: str) -> genanki.Deck:
    """Build a stable Anki deck."""

    return genanki.Deck(stable_int_id(f"anki-auto-deck:{deck_name}"), deck_name)


def build_note(
    card: GeneratedCard,
    model: genanki.Model,
    audio_filenames: list[str] | None = None,
    *,
    tags: list[str] | None = None,
    minimal_cards: bool = False,
) -> genanki.Note:
    """Convert a generated card to a genanki note."""

    audio_tags = " ".join(
        f"[sound:{audio_filename}]" for audio_filename in audio_filenames or []
    )
    return genanki.Note(
        model=model,
        fields=[
            _render_front_text(card),
            _render_back_text(card, minimal_cards=minimal_cards),
            audio_tags,
        ],
        tags=tags or [],
        guid=stable_note_guid(card),
    )


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def capitalize_sentence(value: str) -> str:
    """Capitalize visible sentence starts."""

    cleaned = value.strip()
    characters = list(cleaned)
    should_capitalize = True
    for index, character in enumerate(characters):
        if character.isalpha() and should_capitalize:
            characters[index] = character.upper()
            should_capitalize = False
        elif character in ".!?":
            should_capitalize = True
        elif character.isalpha():
            should_capitalize = False
    return "".join(characters)


def _render_front_text(card: GeneratedCard) -> str:
    lines = [_core_block(capitalize_sentence(card.origin_core))]
    lines.extend(_plain_line(example.origin) for example in card.examples)
    return SECTION_BREAK.join(lines)


def _render_back_text(card: GeneratedCard, *, minimal_cards: bool = False) -> str:
    lines = [_core_block(capitalize_sentence(card.target_core))]
    lines.extend(_plain_line(example.target) for example in card.examples)
    if not minimal_cards:
        notes = _render_notes(card)
        if notes:
            lines.append(notes)
    return SECTION_BREAK.join(lines)


def _core_block(value: str) -> str:
    return f"<b>{_escape(value)}</b>"


def _plain_line(value: str) -> str:
    return _escape(capitalize_sentence(value))


def _note_example_block(value: str) -> str:
    return (
        f'<span style="{NOTE_EXAMPLE_STYLE}">'
        f'"{_escape(capitalize_sentence(value))}"</span>'
    )


def _render_notes(card: GeneratedCard) -> str:
    sections: list[str] = []
    if card.word_family:
        sections.append(
            _render_note_section(NOTE_SECTION_LABELS["word_family"], card.word_family)
        )
    if card.related_vocab:
        sections.append(
            _render_note_section(
                NOTE_SECTION_LABELS["related_vocab"], card.related_vocab
            )
        )
    for section in card.custom_sections:
        sections.append(_render_note_section(section.title, section.items))

    if not sections:
        return ""

    first_section, *remaining_sections = sections
    rendered_notes = "<b>--- NOTES ---</b>" + LINE_BREAK + first_section
    if remaining_sections:
        rendered_notes += SECTION_BREAK + SECTION_BREAK.join(remaining_sections)
    return rendered_notes


def _render_note_section(title: str, items: Sequence[NoteItem]) -> str:
    rendered_items = LINE_BREAK.join(_render_note_item(item) for item in items)
    return _section_header(title) + LINE_BREAK + rendered_items


def _section_header(title: str) -> str:
    return f"<b>{_escape(title)}</b>"


def _render_note_item(item: NoteItem) -> str:
    term = f"<u>{_escape(capitalize_sentence(item.term))}</u>"
    detail = f"{term}: {_escape(item.translation)}"
    if item.nuance:
        detail += f" (<i>{_escape(item.nuance)}</i>)"
    return detail + LINE_BREAK + _note_example_block(item.example)


def write_apkg(
    cards: list[PackagedCard],
    output_path: Path,
    options: PackagingOptions,
) -> Path:
    """Write a fresh Anki package for generated cards."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    model = build_model(options.model_name)
    deck = build_deck(options.deck_name)
    tags = build_card_tags(options.target_language, options.cefr_level)
    media_files = []

    for packaged_card in cards:
        audio_filenames = []
        for audio_path in packaged_card.audio_paths:
            audio_filenames.append(audio_path.name)
            media_files.append(str(audio_path))
        deck.add_note(
            build_note(
                packaged_card.card,
                model,
                audio_filenames,
                tags=tags,
                minimal_cards=options.minimal_cards,
            )
        )

    package = genanki.Package(deck)
    package.media_files = media_files
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)

        package.write_to_file(str(temporary_path))
        os.replace(temporary_path, output_path)
        temporary_path = None
    except Exception:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise
    return output_path
