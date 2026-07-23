"""Tests for local Anki package construction helpers."""

import json
import re
import zipfile
from pathlib import Path

import genanki
import pytest

from anki_auto.anki import (
    CARD_CSS,
    PackagedCard,
    build_card_tags,
    build_model,
    build_note,
    capitalize_sentence,
    slug,
    stable_audio_filename,
    stable_int_id,
    stable_note_guid,
    write_apkg,
)
from anki_auto.options import PackagingOptions
from tests.factories import empty_note_section_kwargs, generated_card


def test_stable_ids_and_filenames_are_reproducible() -> None:
    """Stable identifiers should not change across calls."""

    card = generated_card()
    expected_note_guid = genanki.guid_for(
        "front-text-back-text-v2",
        card.source,
        card.origin_core,
        card.target_core,
    )
    legacy_note_guid = genanki.guid_for(
        "front-text-back-text-v1",
        card.source,
        card.origin_core,
        card.target_core,
    )

    assert stable_int_id("deck") == stable_int_id("deck")
    assert stable_int_id("deck") < 2**63
    assert stable_note_guid(card) == stable_note_guid(card)
    assert stable_note_guid(card) == expected_note_guid
    assert stable_note_guid(card) != legacy_note_guid
    assert stable_audio_filename(card, 1) == stable_audio_filename(card, 1)
    assert stable_audio_filename(card, 1).startswith("anki-auto-sleep-1-")
    assert stable_audio_filename(card, 2).startswith("anki-auto-sleep-2-")
    assert stable_audio_filename(card, 1).endswith(".mp3")


def test_build_model_uses_expected_fields_and_card_css() -> None:
    """The note model should match the expected card fields and styling."""

    model = build_model("Test Model")

    assert [field["name"] for field in model.fields] == [
        "FrontText",
        "BackText",
        "BackAudio",
    ]
    assert model.css == CARD_CSS
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

    card = generated_card(
        word_family=[
            {"target": "un sommeil", "gloss": "sleep", "note": "Use <le>, not la."}
        ]
    )
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
    assert "<b>Examples</b>" in note.fields[1]
    assert "Use &lt;le&gt;, not la." in note.fields[1]
    assert note.fields[2] == "[sound:sleep-1.mp3] [sound:sleep-2.mp3]"
    assert note.tags == []


def test_build_card_tags_are_namespaced_and_slugged() -> None:
    """Deterministic tags are namespaced and slugged from Settings values."""

    assert build_card_tags("Brazilian Portuguese", "A2") == [
        "lang::brazilian-portuguese",
        "level::a2",
    ]
    assert build_card_tags("עברית", "A2") == ["lang::עברית", "level::a2"]


def test_slug_collapses_non_alphanumeric_runs() -> None:
    """Slugs lowercase text and collapse runs of non-alphanumerics to hyphens."""

    assert slug("  Brazilian   Portuguese!! ") == "brazilian-portuguese"
    assert slug("Français") == "français"
    assert slug("A2") == "a2"
    assert slug("!!!").startswith("tag-")


def test_write_apkg_note_carries_namespaced_tags() -> None:
    """Packaging applies the two deterministic tags to each note."""

    deck = genanki.Deck(1, "Tag Test")
    model = build_model("Test Model")
    tags = build_card_tags("Brazilian Portuguese", "A2")
    note = build_note(generated_card(), model, tags=tags)
    deck.add_note(note)

    assert note.tags == ["lang::brazilian-portuguese", "level::a2"]


def test_minimal_cards_render_skips_notes_block() -> None:
    """Minimal cards render only core and examples, dropping the notes block."""

    note = build_note(generated_card(), build_model("Test Model"), minimal_cards=True)

    assert "<b>--- NOTES ---</b>" not in note.fields[1]
    assert "<b>Word family</b>" not in note.fields[1]
    assert "<b>Dormir</b>" in note.fields[1]
    assert "Je dors huit heures." in note.fields[1]


def test_structured_note_french_terms_are_underlined() -> None:
    """French terms in structured note sections should be underlined."""

    note = build_note(generated_card(), build_model("Test Model"))

    assert "<u>Un sommeil</u>: sleep" in note.fields[1]
    assert "<u>Se réveiller</u>: to wake up (opposite action)" in note.fields[1]


def test_note_with_colon_underlines_only_before_first_colon() -> None:
    """Colon-based note rendering should only underline the leading term."""

    note = build_note(
        generated_card(
            word_family=[{"target": "heure", "gloss": "clock time: not duration."}]
        ),
        build_model("Test Model"),
    )

    assert "<u>Heure</u>: clock time: not duration." in note.fields[1]
    assert "<u>Heure: clock time</u>" not in note.fields[1]


def test_rendered_lines_start_capitalized() -> None:
    """Renderer casing should cover each standalone line shown on the card."""

    card = generated_card(
        origin_core="dormir",
        target_core="dormir",
        examples=[
            {"target": "je dors huit heures.", "origin": "duermo ocho horas."},
            {"target": "elle dort mal ce soir.", "origin": "ella duerme mal esta noche."},
        ],
        word_family=[{"target": "un sommeil", "gloss": "sleep", "note": None}],
        related_vocab=[
            {"target": "se réveiller", "gloss": "to wake up", "nuance": "opposite action"}
        ],
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


def test_model_uses_requested_card_styling() -> None:
    """Generated cards should use the requested default Anki styling."""

    model = build_model("Test Model")

    assert "font-family: Arial;" in model.css
    assert "font-size: 20px;" in model.css
    assert "text-align: center;" in model.css


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
        options=PackagingOptions(
            deck_name="French Test",
            model_name="French Basic Test",
            target_language="French",
            cefr_level="A2",
        ),
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0
    with zipfile.ZipFile(output_path) as archive:
        assert "collection.anki2" in archive.namelist()
        assert json.loads(archive.read("media")) == {}


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
        options=PackagingOptions(
            deck_name="French Test",
            model_name="French Basic Test",
            target_language="French",
            cefr_level="A2",
        ),
    )

    assert output_path.exists()
    assert output_path.stat().st_size > 0
    with zipfile.ZipFile(output_path) as archive:
        media = json.loads(archive.read("media"))
        assert set(media.values()) == {"dog-1.mp3", "dog-2.mp3"}
        assert set(media) <= set(archive.namelist())


def test_write_apkg_keeps_existing_output_when_package_write_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A failed package write should not corrupt an existing destination."""

    output_path = tmp_path / "deck.apkg"
    output_path.write_bytes(b"original package")

    def _fail_write(_package: genanki.Package, path: str) -> None:
        Path(path).write_bytes(b"partial package")
        raise RuntimeError("package failed")

    monkeypatch.setattr(genanki.Package, "write_to_file", _fail_write)

    with pytest.raises(RuntimeError, match="package failed"):
        write_apkg(
            cards=[PackagedCard(card=generated_card())],
            output_path=output_path,
            options=PackagingOptions(
                deck_name="French Test",
                model_name="French Basic Test",
                target_language="French",
                cefr_level="A2",
            ),
        )

    assert output_path.read_bytes() == b"original package"
    leftovers = [path for path in tmp_path.iterdir() if path.name.startswith(".deck.apkg")]
    assert leftovers == []


def test_custom_note_sections_render_after_built_in_sections_and_escape_html() -> None:
    card = generated_card(
        custom_note_sections=[
            {
                "title": "Common <mistakes>",
                "items": ["faire <x>: avoid & replace"],
            },
            {"title": "Pronunciation", "items": ["dormir: /dɔʁ.miʁ/"]},
        ]
    )

    note = build_note(card, build_model("Test Model"))
    back = note.fields[1]

    assert back.index("<b>Examples</b>") < back.index(
        "<b>Common &lt;mistakes&gt;</b>"
    )
    assert back.index("<b>Common &lt;mistakes&gt;</b>") < back.index(
        "<b>Pronunciation</b>"
    )
    assert "<u>Faire &lt;x&gt;</u>: avoid &amp; replace" in back


def test_custom_sections_can_create_the_only_notes_block() -> None:
    overrides = empty_note_section_kwargs()
    overrides["custom_note_sections"] = [
        {"title": "Pronunciation", "items": ["dormir: /dɔʁ.miʁ/"]}
    ]
    note = build_note(generated_card(**overrides), build_model("Test Model"))

    assert "<b>--- NOTES ---</b>" in note.fields[1]
    assert "<b>Pronunciation</b>" in note.fields[1]


def test_minimal_cards_hide_custom_note_sections() -> None:
    card = generated_card(
        custom_note_sections=[
            {"title": "Pronunciation", "items": ["dormir: /dɔʁ.miʁ/"]}
        ]
    )

    note = build_note(card, build_model("Test Model"), minimal_cards=True)

    assert "<b>--- NOTES ---</b>" not in note.fields[1]
    assert "<b>Pronunciation</b>" not in note.fields[1]
