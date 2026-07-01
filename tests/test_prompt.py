"""Tests for OpenAI prompt construction."""

import pytest
from pydantic import ValidationError

from anki_auto.models import GeneratedCard, card_json_schema
from anki_auto.prompt import SYSTEM_PROMPT, build_card_messages, build_response_format
from tests.factories import card_kwargs, empty_note_section_kwargs, generated_card


def test_prompt_mentions_french_and_variation() -> None:
    """The prompt should encode the requested language and variation behavior."""

    messages = build_card_messages("dog")

    assert "French" in SYSTEM_PROMPT
    assert "Spanish only" in SYSTEM_PROMPT
    assert "Vary vocabulary" in SYSTEM_PROMPT
    assert "Infinitives".lower() in SYSTEM_PROMPT.lower()
    assert "cleanest reusable French core concept" in SYSTEM_PROMPT
    assert "past participles" in SYSTEM_PROMPT
    assert "Do not add filler" in SYSTEM_PROMPT
    assert "English-only prose notes" in SYSTEM_PROMPT
    assert "usage_forms" in SYSTEM_PROMPT
    assert "Capital" not in SYSTEM_PROMPT
    assert "French term: English translation" in SYSTEM_PROMPT
    assert messages[1]["content"].endswith("Input item: dog")


def test_prompt_omits_renderer_formatting_instructions() -> None:
    """The prompt should not describe renderer-only formatting behavior."""

    forbidden_terms = [
        "[[",
        "]]",
        "wrap",
        "bracket",
        "presentation",
        "underline",
        "markup",
        "tags",
    ]

    prompt = SYSTEM_PROMPT.lower()
    for term in forbidden_terms:
        assert term not in prompt


def test_response_format_uses_generated_card_schema() -> None:
    """Structured output should use the card JSON schema."""

    response_format = build_response_format()
    schema = response_format["json_schema"]["schema"]

    assert response_format["type"] == "json_schema"
    assert schema == card_json_schema()
    assert "front_core_es" in schema["properties"]
    assert "related_vocab" in schema["properties"]
    assert "key_collocations" in schema["properties"]
    assert "register_notes" in schema["properties"]
    assert "usage_forms" in schema["properties"]
    assert "note_examples" in schema["properties"]
    assert schema["properties"]["examples"]["minItems"] == 2
    assert schema["properties"]["examples"]["maxItems"] == 3
    assert schema["properties"]["related_vocab"]["maxItems"] == 8
    assert schema["properties"]["usage_forms"]["maxItems"] == 8
    assert "minItems" not in schema["properties"]["word_family"]


def test_generated_card_normalizes_tags() -> None:
    """Tags should become stable Anki-friendly values."""

    card = generated_card(tags=[" French ", "Noun", "noun", "two words"])

    assert card.tags == ["french", "noun", "two-words"]


def test_generated_card_rejects_blank_nested_strings() -> None:
    """Generated cards should reject blank content inside nested sections."""

    with pytest.raises(ValidationError):
        GeneratedCard(
            **card_kwargs(
                examples=[
                    {"fr": "Le chien court.", "es": "El perro corre."},
                    {"fr": " ", "es": "El perro duerme."},
                ],
                tags=[],
            )
        )


def test_generated_card_allows_empty_note_sections() -> None:
    """Irrelevant note sections can be empty and omitted by the renderer."""

    card = generated_card(**empty_note_section_kwargs())

    assert card.word_family == []
    assert card.related_vocab == []
    assert card.key_collocations == []
    assert card.register_notes == []
    assert card.usage_forms == []
    assert card.note_examples == []


def test_generated_card_rejects_blank_note_items() -> None:
    """Generated cards should reject blank content inside optional notes."""

    with pytest.raises(ValidationError):
        GeneratedCard(**card_kwargs(register_notes=[" "]))

    with pytest.raises(ValidationError):
        GeneratedCard(
            **card_kwargs(
                key_collocations=[{"fr": "avoir besoin de", "en": " ", "note": None}]
            )
        )
