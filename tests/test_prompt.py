"""Tests for OpenAI prompt construction."""

import pytest
from pydantic import ValidationError

from anki_auto.config import PromptConfig, Settings
from anki_auto.models import GeneratedCard
from anki_auto.prompt import (
    assemble_system_prompt,
    build_blacklist_prompt,
    build_card_messages,
    build_cefr_prompt,
    build_customization_prompt,
    build_instruction_contract_prompt,
    build_notes_prompt,
    build_system_prompt,
)
from tests.factories import card_kwargs, empty_note_section_kwargs, generated_card


def _prompt_config(level: str = "A2") -> PromptConfig:
    """Build a representative prompt config for tests."""

    return PromptConfig(
        origin_language="Spanish",
        target_language="French",
        notes_language="English",
        level=level,
    )


@pytest.mark.parametrize(
    ("level", "marker"),
    [
        ("A1", "5–9 words"),
        ("A2", "5–9 words"),
        ("B1", "6–12 words"),
        ("B2", "6–12 words"),
        ("C1", "7–15 words"),
        ("C2", "7–15 words"),
    ],
)
def test_build_cefr_prompt_selects_tier_and_injects_level(
    level: str, marker: str
) -> None:
    """Each level maps to its curated tier and injects the exact level string."""

    prompt = build_cefr_prompt(_prompt_config(level))

    assert marker in prompt
    assert f"Match {level} vocabulary and grammar" in prompt


@pytest.mark.parametrize(
    ("origin", "notes"),
    [
        ("Spanish", "Spanish"),
        ("Spanish", "spanish"),
        ("  Spanish  ", "spanish"),
    ],
)
def test_build_system_prompt_uses_singular_native_when_origin_equals_notes(
    origin: str, notes: str
) -> None:
    """Matching origin/notes languages yield the singular native-language clause."""

    cfg = PromptConfig(
        origin_language=origin,
        target_language="French",
        notes_language=notes,
        level="A2",
    )
    prompt = build_system_prompt(cfg)

    assert f"whose native language is {origin}." in prompt
    assert "native languages are" not in prompt


def test_build_system_prompt_uses_plural_native_when_origin_differs_from_notes() -> None:
    """Differing origin/notes languages name both in the plural native clause."""

    cfg = PromptConfig(
        origin_language="Japanese",
        target_language="French",
        notes_language="Spanish",
        level="A2",
    )
    prompt = build_system_prompt(cfg)

    assert "whose native languages are Japanese and Spanish." in prompt
    assert "whose native language is" not in prompt


def test_build_notes_prompt_states_explicit_language_mapping() -> None:
    """The notes piece explicitly maps note language and target language."""

    cfg = _prompt_config()
    prompt = build_notes_prompt(cfg)

    assert (
        "Every gloss, nuance, and register note is written in English; "
        "target terms and note examples stay in French." in prompt
    )


def test_assemble_system_prompt_includes_notes_mapping_when_not_minimal() -> None:
    """The explicit notes-language mapping appears in a full assembled prompt."""

    cfg = _prompt_config()
    prompt = assemble_system_prompt(cfg, minimal_cards=False)

    assert (
        "Every gloss, nuance, and register note is written in English; "
        "target terms and note examples stay in French." in prompt
    )


def test_assemble_system_prompt_omits_notes_mapping_when_minimal() -> None:
    """The explicit notes-language mapping must not leak into minimal cards."""

    cfg = _prompt_config()
    minimal = assemble_system_prompt(cfg, minimal_cards=True)

    assert "Every gloss, nuance, and register note is written in" not in minimal


def test_assemble_system_prompt_orders_all_five_pieces() -> None:
    """A normal card assembles the five pieces in the fixed order."""

    cfg = _prompt_config()
    prompt = assemble_system_prompt(cfg, minimal_cards=False)

    system_index = prompt.index("You create high-quality French Anki flashcards")
    core_index = prompt.index("distill the input item")
    cefr_index = prompt.index("Write one original sentence")
    flashcard_index = prompt.index("Build the flashcard around the core concept")
    notes_index = prompt.index("Always add notes to a card")

    assert system_index < core_index < cefr_index < flashcard_index < notes_index


def test_assemble_system_prompt_omits_notes_when_minimal() -> None:
    """The notes piece is dropped entirely when minimal cards are requested."""

    cfg = _prompt_config()
    minimal = assemble_system_prompt(cfg, minimal_cards=True)

    assert build_notes_prompt(cfg) not in minimal
    assert "Always add notes to a card" not in minimal
    assert "Build the flashcard around the core concept" in minimal


def test_build_card_messages_puts_input_only_in_user_message() -> None:
    """The loose input appears only in the user turn, not the system prompt."""

    cfg = _prompt_config()
    messages = build_card_messages("dog", cfg, minimal_cards=False)

    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == assemble_system_prompt(cfg, minimal_cards=False)
    assert "dog" not in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Input item: dog"


def test_generated_card_rejects_blank_nested_strings() -> None:
    """Generated cards should reject blank content inside nested sections."""

    with pytest.raises(ValidationError):
        GeneratedCard(
            **card_kwargs(
                examples=[
                    {"target": "Le chien court.", "origin": "El perro corre."},
                    {"target": " ", "origin": "El perro duerme."},
                ],
            )
        )


def test_generated_card_allows_empty_note_sections() -> None:
    """Irrelevant note sections can be empty and omitted by the renderer."""

    card = generated_card(**empty_note_section_kwargs())

    assert card.word_family == []
    assert card.related_vocab == []
    assert card.note_examples == []


def test_generated_card_rejects_blank_note_items() -> None:
    """Generated cards should reject blank content inside optional notes."""

    with pytest.raises(ValidationError):
        GeneratedCard(**card_kwargs(note_examples=[" "]))


def test_generated_card_accepts_bounded_custom_note_sections() -> None:
    card = generated_card(
        custom_note_sections=[
            {
                "title": "Common mistakes",
                "items": ["Do not confuse dormir with dormirse."],
            }
        ]
    )

    assert card.custom_note_sections[0].title == "Common mistakes"
    assert card.custom_note_sections[0].items == [
        "Do not confuse dormir with dormirse."
    ]


@pytest.mark.parametrize(
    "custom_sections",
    [
        [{"title": " ", "items": ["Valid item"]}],
        [{"title": "Valid title", "items": []}],
        [{"title": "Valid title", "items": [" "]}],
        [{"title": f"Section {index}", "items": ["Item"]} for index in range(7)],
        [{"title": "Too many items", "items": [str(index) for index in range(9)]}],
    ],
)
def test_generated_card_rejects_invalid_custom_note_sections(
    custom_sections: list[dict[str, object]],
) -> None:
    with pytest.raises(ValidationError):
        GeneratedCard(
            **card_kwargs(custom_note_sections=custom_sections)
        )


def test_settings_prompt_config_carries_immutable_prompt_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANKI_ORIGIN_LANGUAGE", "Spanish")
    monkeypatch.setenv("ANKI_TARGET_LANGUAGE", "French")
    monkeypatch.setenv("ANKI_NOTES_LANGUAGE", "English")
    monkeypatch.setenv("ANKI_CEFR_LEVEL", "A2")
    settings = Settings(_env_file=None)

    cfg = settings.prompt_config(
        customization=("Add pronunciation.",),
        blacklist=("chien",),
    )

    assert cfg.customization == ("Add pronunciation.",)
    assert cfg.blacklist == ("chien",)


def test_prompt_omits_unavailable_overlay_blocks() -> None:
    prompt = assemble_system_prompt(_prompt_config(), minimal_cards=False)

    assert "User customization" not in prompt
    assert "Vocabulary blacklist" not in prompt


def test_customization_preserves_order_and_follows_built_in_defaults() -> None:
    cfg = PromptConfig(
        origin_language="Spanish",
        target_language="French",
        notes_language="English",
        level="A2",
        customization=("Add pronunciation.", "Keep explanations short."),
    )

    prompt = assemble_system_prompt(cfg, minimal_cards=False)
    customization_block = build_customization_prompt(cfg)

    assert customization_block in prompt
    assert prompt.index("Always add notes to a card") < prompt.index(
        "User customization"
    )
    assert prompt.index("Add pronunciation.") < prompt.index(
        "Keep explanations short."
    )
    assert "may override built-in content and style preferences" in prompt
    assert "cannot override hard requirements" in prompt


def test_customization_is_dropped_in_minimal_mode_but_kept_otherwise() -> None:
    cfg = PromptConfig(
        origin_language="Spanish",
        target_language="French",
        notes_language="English",
        level="A2",
        customization=("Add pronunciation.",),
    )

    minimal = assemble_system_prompt(cfg, minimal_cards=True)
    full = assemble_system_prompt(cfg, minimal_cards=False)

    assert "User customization" not in minimal
    assert "Add pronunciation." not in minimal
    assert "User customization" in full


def test_blacklist_is_a_best_effort_hard_requirement_with_core_exemption() -> None:
    cfg = PromptConfig(
        origin_language="Spanish",
        target_language="French",
        notes_language="English",
        level="A2",
        blacklist=("chien", "aller au restaurant"),
    )

    prompt = assemble_system_prompt(cfg, minimal_cards=False)
    blacklist_block = build_blacklist_prompt(cfg)

    assert blacklist_block in prompt
    assert "Vocabulary blacklist (hard requirement)" in prompt
    assert "chien\naller au restaurant" in prompt
    assert "main and note examples" in prompt
    assert "requested learning concept" in prompt
    assert "best effort" in prompt


def test_instruction_contract_gives_item_request_priority_over_customization() -> None:
    cfg = PromptConfig(
        origin_language="Spanish",
        target_language="French",
        notes_language="English",
        level="A2",
        customization=("Prefer formal examples.",),
    )

    contract = build_instruction_contract_prompt(cfg, minimal_cards=True)

    assert "current input item and its explicit request" in contract
    assert "global user customization" in contract
    assert contract.index("current input item") < contract.index(
        "global user customization"
    )
    assert "Every note collection must be empty" in contract


def test_notes_prompt_reserves_custom_sections_for_explicit_requests() -> None:
    prompt = build_notes_prompt(_prompt_config())

    assert "custom_note_sections" in prompt
    assert "only for additional named sections explicitly requested" in prompt
