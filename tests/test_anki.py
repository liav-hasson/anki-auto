"""Tests for local Anki package construction helpers."""

import re
from pathlib import Path

import genanki

from anki_auto.anki import (
    PackagedCard,
    build_model,
    build_note,
    capitalize_sentence,
    stable_audio_filename,
    stable_int_id,
    stable_note_guid,
    write_apkg,
)
from tests.factories import empty_note_section_kwargs, generated_card


def test_stable_ids_and_filenames_are_reproducible() -> None:
    """Stable identifiers should not change across calls."""

    card = generated_card()
    expected_note_guid = genanki.guid_for(
        "front-text-back-text-v2",
        card.source,
        card.front_core_es,
        card.back_core_fr,
    )
    legacy_note_guid = genanki.guid_for(
        "front-text-back-text-v1",
        card.source,
        card.front_core_es,
        card.back_core_fr,
    )

    assert stable_int_id("deck") == stable_int_id("deck")
    assert stable_note_guid(card) == stable_note_guid(card)
    assert stable_note_guid(card) == expected_note_guid
    assert stable_note_guid(card) != legacy_note_guid
    assert stable_audio_filename(card, 1) == stable_audio_filename(card, 1)
    assert stable_audio_filename(card, 1).startswith("anki-auto-sleep-1-")
    assert stable_audio_filename(card, 2).startswith("anki-auto-sleep-2-")
    assert stable_audio_filename(card, 1).endswith(".mp3")


def test_build_model_uses_three_expected_fields_without_custom_css() -> None:
    """The note model should match the user's existing Spanish card workflow."""

    model = build_model("Test Model")

    assert [field["name"] for field in model.fields] == [
        "FrontText",
        "BackText",
        "BackAudio",
    ]
    assert model.css == ""
    assert "{{FrontText}}" in model.templates[0]["qfmt"]
    assert "{{BackText}}" in model.templates[0]["afmt"]
    assert "{{BackAudio}}" in model.templates[0]["afmt"]


def test_capitalize_sentence_handles_core_text() -> None:
    """Core concepts should be defensively capitalized before rendering."""

    assert capitalize_sentence("el perro") == "El perro"
    assert capitalize_sentence(" le chien") == "Le chien"
    assert capitalize_sentence("¿que tal?") == "¿Que tal?"
    assert capitalize_sentence("123") == "123"


def test_build_note_escapes_fields_and_adds_audio() -> None:
    """Note fields should be escaped and include the Anki sound tag."""

    card = generated_card(register_notes=["Use <le>, not la."])
    note = build_note(card, build_model("Test Model"), ["sleep-1.mp3", "sleep-2.mp3"])

    assert len(note.fields) == 3
    assert note.fields[0].startswith("<b>Dormir</b><br><br>")
    assert "<b>Dormir</b>" in note.fields[0]
    assert "Duermo ocho horas." in note.fields[0]
    assert "<br><br>Ella duerme mal esta noche." in note.fields[0]
    assert note.fields[1].startswith("<b>Dormir</b><br><br>")
    assert "<b>Dormir</b>" in note.fields[1]
    assert "<br><br>Je dors huit heures." in note.fields[1]
    assert '<span style="font-style: italic;">Je dors huit heures.' not in note.fields[1]
    assert "#39ff14" in note.fields[1]
    assert "<br><br><b>--- NOTES ---</b><br><b>Word family</b>" in note.fields[1]
    assert "<br><br><b>--- NOTES ---</b><br><br>" not in note.fields[1]
    assert "<b>Word family</b>" in note.fields[1]
    assert "<b>Related vocab</b>" in note.fields[1]
    assert "<b>Key collocations</b>" in note.fields[1]
    assert "<b>Register and usage notes</b>" in note.fields[1]
    assert "<b>Usage forms</b>" in note.fields[1]
    assert "<b>Examples</b>" in note.fields[1]
    assert "Use &lt;le&gt;, not la." in note.fields[1]
    assert note.fields[2] == "[sound:sleep-1.mp3] [sound:sleep-2.mp3]"
    assert note.tags == ["french", "verb"]


def test_structured_note_french_terms_are_underlined() -> None:
    """French terms in structured note sections should be underlined."""

    note = build_note(generated_card(), build_model("Test Model"))

    assert "<u>Un sommeil</u>: sleep" in note.fields[1]
    assert "<u>Se réveiller</u>: to wake up (opposite action)" in note.fields[1]
    assert "<u>Dormir bien</u>: to sleep well" in note.fields[1]


def test_usage_forms_underline_french_terms() -> None:
    """Usage forms should render with the French term underlined."""

    note = build_note(generated_card(), build_model("Test Model"))

    assert "<u>Je dors</u>: I sleep (present tense)" in note.fields[1]
    assert "<u>Tu dors</u>: you sleep (present tense)" in note.fields[1]
    assert "<u>Il dort</u>: he sleeps (present tense)" in note.fields[1]


def test_register_note_with_colon_underlines_only_before_first_colon() -> None:
    """Colon-based note rendering should only underline the leading term."""

    note = build_note(
        generated_card(register_notes=["heure: clock time: not duration."]),
        build_model("Test Model"),
    )

    assert "<u>Heure</u>: clock time: not duration." in note.fields[1]
    assert "<u>Heure: clock time</u>" not in note.fields[1]


def test_rendered_lines_start_capitalized() -> None:
    """Renderer casing should cover each standalone line shown on the card."""

    card = generated_card(
        front_core_es="dormir",
        back_core_fr="dormir",
        examples=[
            {"fr": "je dors huit heures.", "es": "duermo ocho horas."},
            {"fr": "elle dort mal ce soir.", "es": "ella duerme mal esta noche."},
        ],
        word_family=[{"fr": "un sommeil", "en": "sleep", "note": None}],
        related_vocab=[
            {"fr": "se réveiller", "en": "to wake up", "nuance": "opposite action"}
        ],
        key_collocations=[
            {"fr": "dormir bien", "en": "to sleep well", "note": None}
        ],
        register_notes=["common irregular present forms vary by subject."],
        usage_forms=[{"fr": "je dors", "en": "I sleep", "note": None}],
        note_examples=["le bébé dort déjà."],
    )

    note = build_note(card, build_model("Test Model"))
    rendered_text = "<br>".join(note.fields[:2])
    lines = []
    for raw_line in re.split(r"(?:<br>)+", rendered_text):
        line = re.sub(r"<[^>]+>", "", raw_line).strip(' \"')
        if line:
            lines.append(line)
    sentence_lines = [line for line in lines if not line.startswith("---")]

    assert sentence_lines
    assert all(line[0].isupper() for line in sentence_lines if line[0].isalpha())


def test_main_examples_are_plain_but_note_examples_are_styled() -> None:
    """Only note examples should receive neon green italic styling."""

    note = build_note(generated_card(), build_model("Test Model"))

    main_example = "Je dors huit heures."
    note_example = (
        '<span style="color: #39ff14; font-style: italic;">'
        '"Le bébé dort déjà."</span>'
    )

    assert main_example in note.fields[1]
    assert note_example in note.fields[1]
    assert '<u>"Le bébé dort déjà."</u>' not in note.fields[1]
    main_examples_html = note.fields[1].split(
        "<br><br><b>--- NOTES ---</b>", maxsplit=1
    )[0]
    assert "font-style: italic" not in main_examples_html
    assert "#39ff14" not in main_examples_html
    assert "<u>" not in main_examples_html


def test_rendered_text_uses_explicit_html_breaks() -> None:
    """Front and back text should not depend on CSS blocks for line separation."""

    note = build_note(generated_card(), build_model("Test Model"))

    assert note.fields[0].count("<br><br>") >= 2
    assert note.fields[1].count("<br><br>") >= 3
    assert '<div class="anki-auto-core">' not in note.fields[0]
    assert '<div class="anki-auto-core">' not in note.fields[1]


def test_model_does_not_claim_font_styling() -> None:
    """Custom font CSS should not be emitted because Anki may ignore it."""

    model = build_model("Test Model")

    assert "font-family" not in model.css
    assert "Arial" not in model.css


def test_empty_note_sections_are_omitted() -> None:
    """Irrelevant note sections should not render empty headers."""

    card = generated_card(**empty_note_section_kwargs())

    note = build_note(card, build_model("Test Model"))

    assert "<b>--- NOTES ---</b>" not in note.fields[1]
    assert "<b>Word family</b>" not in note.fields[1]
    assert "<b>Related vocab</b>" not in note.fields[1]
    assert "<b>Examples</b>" not in note.fields[1]


def test_write_apkg_creates_file_without_audio(tmp_path: Path) -> None:
    """The package builder should write an importable file without media."""

    output_path = tmp_path / "deck.apkg"

    write_apkg(
        cards=[PackagedCard(card=generated_card())],
        output_path=output_path,
        deck_name="French Test",
        model_name="French Basic Test",
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_write_apkg_creates_file_with_multiple_audio_files(tmp_path: Path) -> None:
    """The package builder should include multiple local media files."""

    output_path = tmp_path / "deck.apkg"
    audio_one = tmp_path / "dog-1.mp3"
    audio_two = tmp_path / "dog-2.mp3"
    audio_one.write_bytes(b"fake mp3 one")
    audio_two.write_bytes(b"fake mp3 two")

    write_apkg(
        cards=[PackagedCard(card=generated_card(), audio_paths=(audio_one, audio_two))],
        output_path=output_path,
        deck_name="French Test",
        model_name="French Basic Test",
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0
