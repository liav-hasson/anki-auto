"""Build directly importable Anki packages."""

from __future__ import annotations

import hashlib
import html
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import genanki

from .models import (
    GeneratedCard,
    KeyCollocationEntry,
    RelatedVocabEntry,
    TranslationEntry,
)


FIELD_NAMES = ["FrontText", "BackText", "BackAudio"]
NOTE_EXAMPLE_STYLE = "color: #39ff14; font-style: italic;"
SECTION_BREAK = "<br><br>"
LINE_BREAK = "<br>"


@dataclass(frozen=True)
class PackagedCard:
    """A generated card plus optional local audio files."""

    card: GeneratedCard
    audio_paths: tuple[Path, ...] = field(default_factory=tuple)


def stable_int_id(value: str) -> int:
    """Create a stable positive Anki id from text."""

    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def stable_note_guid(card: GeneratedCard) -> str:
    """Create a stable note guid from source and card content."""

    return genanki.guid_for(
        "front-text-back-text-v2",
        card.source,
        card.front_core_es,
        card.back_core_fr,
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
            [card.source, card.back_core_fr, str(example_index), example.fr]
        ).encode("utf-8")
    ).hexdigest()[:16]
    slug = re.sub(r"[^a-z0-9]+", "-", card.source.lower()).strip("-")[:40]
    prefix = slug or "card"
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
    )


def build_deck(deck_name: str) -> genanki.Deck:
    """Build a stable Anki deck."""

    return genanki.Deck(stable_int_id(f"anki-auto-deck:{deck_name}"), deck_name)


def build_note(
    card: GeneratedCard,
    model: genanki.Model,
    audio_filenames: list[str] | None = None,
) -> genanki.Note:
    """Convert a generated card to a genanki note."""

    audio_tags = " ".join(
        f"[sound:{audio_filename}]" for audio_filename in audio_filenames or []
    )
    return genanki.Note(
        model=model,
        fields=[
            _render_front_text(card),
            _render_back_text(card),
            audio_tags,
        ],
        tags=card.tags,
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


def capitalize_first_visible(value: str) -> str:
    """Backward-compatible alias for older callers."""

    return capitalize_sentence(value)


def _render_front_text(card: GeneratedCard) -> str:
    lines = [_core_block(capitalize_sentence(card.front_core_es))]
    lines.extend(_plain_line(example.es) for example in card.examples)
    return SECTION_BREAK.join(lines)


def _render_back_text(card: GeneratedCard) -> str:
    lines = [_core_block(capitalize_sentence(card.back_core_fr))]
    lines.extend(_plain_line(example.fr) for example in card.examples)
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
    note_sections = []
    if card.word_family:
        note_sections.append(_render_note_section("Word family", card.word_family))
    if card.related_vocab:
        note_sections.append(_render_note_section("Related vocab", card.related_vocab))
    if card.key_collocations:
        note_sections.append(
            _render_note_section("Key collocations", card.key_collocations)
        )
    if card.register_notes:
        note_sections.append(
            _render_note_section("Register and usage notes", card.register_notes)
        )
    if card.usage_forms:
        note_sections.append(_render_note_section("Usage forms", card.usage_forms))
    if card.note_examples:
        rendered_examples = LINE_BREAK.join(
            _note_example_block(example) for example in card.note_examples
        )
        note_sections.append(_section_header("Examples") + LINE_BREAK + rendered_examples)

    if not note_sections:
        return ""

    first_section, *remaining_sections = note_sections
    rendered_notes = "<b>--- NOTES ---</b>" + LINE_BREAK + first_section
    if remaining_sections:
        rendered_notes += SECTION_BREAK + SECTION_BREAK.join(remaining_sections)
    return rendered_notes


def _render_note_section(
    title: str,
    items: Sequence[TranslationEntry | RelatedVocabEntry | KeyCollocationEntry | str],
) -> str:
    rendered_items = LINE_BREAK.join(_render_note_item(item) for item in items)
    return _section_header(title) + LINE_BREAK + rendered_items


def _section_header(title: str) -> str:
    return f"<b>{_escape(title)}</b>"


def _render_note_item(
    item: TranslationEntry | RelatedVocabEntry | KeyCollocationEntry | str,
) -> str:
    if isinstance(item, str):
        return _underline_before_first_colon(item)

    details = _format_note_details(item)
    visible_line = f"{item.fr}: {details}" if details else item.fr
    return _underline_before_first_colon(visible_line)


def _underline_before_first_colon(value: str) -> str:
    visible_line = capitalize_sentence(value)
    term, separator, details = visible_line.partition(":")
    if not separator:
        return _escape(visible_line)
    return f"<u>{_escape(term)}</u>{separator}{_escape(details)}"


def _format_note_details(
    item: TranslationEntry | RelatedVocabEntry | KeyCollocationEntry,
) -> str:
    details = []
    if item.en:
        details.append(item.en)
    if isinstance(item, RelatedVocabEntry) and item.nuance:
        details.append(f"({item.nuance})")
    if isinstance(item, (TranslationEntry, KeyCollocationEntry)) and item.note:
        details.append(f"({item.note})")
    return " ".join(details)


def write_apkg(
    cards: list[PackagedCard],
    output_path: Path,
    deck_name: str,
    model_name: str,
) -> Path:
    """Write a fresh Anki package for generated cards."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    model = build_model(model_name)
    deck = build_deck(deck_name)
    media_files = []

    for packaged_card in cards:
        audio_filenames = []
        for audio_path in packaged_card.audio_paths:
            audio_filenames.append(audio_path.name)
            media_files.append(str(audio_path))
        deck.add_note(build_note(packaged_card.card, model, audio_filenames))

    package = genanki.Package(deck)
    package.media_files = media_files
    package.write_to_file(str(output_path))
    return output_path
