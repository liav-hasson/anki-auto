"""Tests for OpenAI prompt construction."""

import pytest
from pydantic import ValidationError

from anki_auto.config import PromptConfig, Settings
from anki_auto.models import GeneratedCard
from anki_auto.prompt import (
    assemble_system_prompt,
    build_card_messages,
    build_default_behavior,
    build_glossary,
    build_intro,
)
from tests.factories import card_kwargs, empty_note_section_kwargs, generated_card


def _prompt_config(
    level: str = "A2",
    *,
    origin_language: str = "English",
    target_language: str = "Spanish",
    notes_language: str = "English",
    customization: tuple[str, ...] = (),
    blacklist: tuple[str, ...] = (),
) -> PromptConfig:
    """Build a representative prompt config for tests."""

    return PromptConfig(
        origin_language=origin_language,
        target_language=target_language,
        notes_language=notes_language,
        level=level,
        customization=customization,
        blacklist=blacklist,
    )


def _valid_item() -> dict[str, str]:
    """Build a minimal valid note item."""

    return {"term": "dormir", "translation": "to sleep", "example": "Voy a dormir."}


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
def test_default_behavior_injects_sentence_length_and_level(
    level: str, marker: str
) -> None:
    """Each level injects its sentence-length range and the exact level string."""

    prompt = build_default_behavior(_prompt_config(level), minimal_cards=False)

    assert f"roughly {marker}" in prompt
    assert f"Match {level} difficulty" in prompt
    assert f"CEFR level of the user - {level}." in prompt


def test_core_sentences_tier_guidance_targets_beginner_for_a2() -> None:
    """A2 sits in tier 1 and gets beginner-level vocabulary guidance."""

    prompt = build_default_behavior(_prompt_config("A2"), minimal_cards=False)

    assert "beginner-level vocabulary" in prompt
    assert "advanced, nuanced" not in prompt
    assert "advanced prepositions" not in prompt


def test_core_sentences_tier_guidance_targets_advanced_for_c1() -> None:
    """C1 sits in tier 3 and gets advanced vocabulary and preposition guidance."""

    prompt = build_default_behavior(_prompt_config("C1"), minimal_cards=False)

    assert "advanced, nuanced" in prompt
    assert "advanced prepositions" in prompt
    assert "beginner-level vocabulary" not in prompt


def test_core_sentences_tier_guidance_stays_middle_for_b1() -> None:
    """B1 sits in tier 2, avoiding both beginner and advanced-only phrasing."""

    prompt = build_default_behavior(_prompt_config("B1"), minimal_cards=False)

    assert "natural, idiomatic everyday vocabulary and varied grammar" in prompt
    assert "beginner-level vocabulary" not in prompt
    assert "advanced, nuanced" not in prompt
    assert "advanced prepositions" not in prompt


@pytest.mark.parametrize(
    ("origin", "notes"),
    [
        ("English", "English"),
        ("English", "english"),
        ("  English  ", "english"),
    ],
)
def test_intro_uses_singular_native_when_origin_equals_notes(
    origin: str, notes: str
) -> None:
    """Matching origin/notes languages yield the singular native-language clause."""

    cfg = _prompt_config(origin_language=origin, notes_language=notes)
    prompt = build_intro(cfg)

    assert f"whose native language is {origin}." in prompt
    assert "native languages are" not in prompt


def test_intro_uses_plural_native_when_origin_differs_from_notes() -> None:
    """Differing origin/notes languages name both in the plural native clause."""

    cfg = _prompt_config(origin_language="Japanese", notes_language="Spanish")
    prompt = build_intro(cfg)

    assert "whose native languages are Japanese and Spanish." in prompt
    assert "whose native language is" not in prompt


def test_intro_names_target_language_and_forbids_inline_formatting() -> None:
    """The intro names the target language and requires plain-text output."""

    prompt = build_intro(_prompt_config())

    assert "high-quality Spanish Anki flashcards" in prompt
    assert "return plain text only" in prompt


def test_glossary_defines_note_item_in_target_language() -> None:
    """The glossary defines note item and example sentence in the target."""

    prompt = build_glossary(_prompt_config())

    assert "Terms used below:" in prompt
    assert "note item: a Spanish word or chunk" in prompt
    assert "example sentence: a Spanish sentence of a note item" in prompt


def test_default_behavior_states_language_mapping_when_not_minimal() -> None:
    """The notes rules map notes language and target language explicitly."""

    prompt = build_default_behavior(_prompt_config(), minimal_cards=False)

    assert (
        "Every gloss, nuance, and register note is written in English "
        "(may differ from native language); target terms and example sentences "
        "stay in Spanish." in prompt
    )


def test_notes_section_uses_judgment_based_core_only_guidance() -> None:
    """Notes guidance is judgment-based, core-only, and caps the default sections."""

    prompt = build_default_behavior(_prompt_config(), minimal_cards=False)

    assert (
        "Produce two note sections that deepen understanding of the core concept "
        "only." in prompt
    )
    assert (
        "3–6 per section, choosing the count per word based on how many genuinely "
        "related items actually exist, never padding to a fixed number" in prompt
    )
    assert "Do not note unrelated words or the optional vocab." in prompt
    assert (
        "Word family and Related vocab are the only sections to produce by default; "
        "never add another section unless a user instruction explicitly requests it."
        in prompt
    )
    assert "Always produce two extensive note sections" not in prompt


def test_default_behavior_omits_notes_section_when_minimal() -> None:
    """Minimal cards drop the whole notes subsection from default behavior."""

    prompt = build_default_behavior(_prompt_config(), minimal_cards=True)

    assert "3. Notes section" not in prompt
    assert "Produce two note sections that deepen understanding" not in prompt
    assert "1. Core concept cleanup" in prompt
    assert "2. Core sentences creation" in prompt


def test_assemble_orders_all_sections() -> None:
    """A full card assembles intro, glossary, defaults, instructions, blacklist."""

    cfg = _prompt_config(
        customization=("write note items for optional vocab",),
        blacklist=("cosa", "genial"),
    )
    prompt = assemble_system_prompt(cfg, minimal_cards=False)

    intro_index = prompt.index("You create high-quality Spanish Anki flashcards")
    glossary_index = prompt.index("Terms used below:")
    default_index = prompt.index("=== DEFAULT BEHAVIOR ===")
    instructions_index = prompt.index("=== USER INSTRUCTIONS ===")
    blacklist_index = prompt.index("=== BLACKLISTED VOCAB ===")

    assert (
        intro_index
        < glossary_index
        < default_index
        < instructions_index
        < blacklist_index
    )


def test_build_card_messages_uses_input_line_and_isolates_system() -> None:
    """The loose input appears only in the user turn as an input line."""

    cfg = _prompt_config()
    messages = build_card_messages("perro", cfg, minimal_cards=False)

    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == assemble_system_prompt(cfg, minimal_cards=False)
    assert "perro" not in messages[0]["content"]
    assert messages[1] == {"role": "user", "content": "Input line: perro"}


def test_generated_card_rejects_blank_nested_strings() -> None:
    """Generated cards should reject blank content inside nested sections."""

    with pytest.raises(ValidationError):
        GeneratedCard(
            **card_kwargs(
                examples=[
                    {"target": "El perro corre.", "origin": "The dog runs."},
                    {"target": " ", "origin": "The dog sleeps."},
                ],
            )
        )


def test_generated_card_allows_empty_note_sections() -> None:
    """Irrelevant note sections can be empty and omitted by the renderer."""

    card = generated_card(**empty_note_section_kwargs())

    assert card.word_family == []
    assert card.related_vocab == []
    assert card.custom_sections == []


def test_generated_card_rejects_note_item_missing_example() -> None:
    """Every note item must carry a non-blank example sentence."""

    with pytest.raises(ValidationError):
        GeneratedCard(
            **card_kwargs(
                word_family=[
                    {"term": "dormi", "translation": "slept", "example": " "}
                ]
            )
        )


def test_note_item_trims_blank_nuance_to_none() -> None:
    """A blank nuance collapses to None while text is trimmed."""

    card = generated_card(
        word_family=[
            {
                "term": "dormi",
                "translation": "slept",
                "nuance": "  ",
                "example": "Il a dormi.",
            },
            {
                "term": "sommeil",
                "translation": "sleep",
                "nuance": "  masc.  ",
                "example": "Le sommeil est bon.",
            },
        ]
    )

    assert card.word_family[0].nuance is None
    assert card.word_family[1].nuance == "masc."


def test_generated_card_accepts_bounded_custom_sections() -> None:
    """A custom section keeps its title and structured note items."""

    card = generated_card(
        custom_sections=[
            {
                "title": "Common mistakes",
                "items": [
                    {
                        "term": "dormirse",
                        "translation": "to fall asleep",
                        "example": "Me dormí en el sofá.",
                    }
                ],
            }
        ]
    )

    section = card.custom_sections[0]
    assert section.title == "Common mistakes"
    assert section.items[0].term == "dormirse"
    assert section.items[0].example == "Me dormí en el sofá."


@pytest.mark.parametrize(
    "custom_sections",
    [
        [{"title": " ", "items": [_valid_item()]}],
        [{"title": "Valid title", "items": []}],
        [
            {
                "title": "Valid title",
                "items": [{"term": " ", "translation": "x", "example": "y"}],
            }
        ],
        [{"title": f"Section {index}", "items": [_valid_item()]} for index in range(7)],
        [{"title": "Too many", "items": [_valid_item() for _ in range(9)]}],
    ],
)
def test_generated_card_rejects_invalid_custom_sections(
    custom_sections: list[dict[str, object]],
) -> None:
    """Blank titles, empty/oversized item lists, and too many sections are rejected."""

    with pytest.raises(ValidationError):
        GeneratedCard(**card_kwargs(custom_sections=custom_sections))


def test_settings_prompt_config_carries_immutable_prompt_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Settings.prompt_config forwards customization and blacklist lines."""

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("ANKI_ORIGIN_LANGUAGE", "English")
    monkeypatch.setenv("ANKI_TARGET_LANGUAGE", "Spanish")
    monkeypatch.setenv("ANKI_NOTES_LANGUAGE", "English")
    monkeypatch.setenv("ANKI_CEFR_LEVEL", "B1")
    settings = Settings(_env_file=None)

    cfg = settings.prompt_config(
        customization=("Add pronunciation.",),
        blacklist=("cosa",),
    )

    assert cfg.customization == ("Add pronunciation.",)
    assert cfg.blacklist == ("cosa",)
    assert cfg.level == "B1"


def test_assemble_omits_overlays_when_absent() -> None:
    """No customization or blacklist means no overlay sections."""

    prompt = assemble_system_prompt(_prompt_config(), minimal_cards=False)

    assert "=== USER INSTRUCTIONS ===" not in prompt
    assert "=== BLACKLISTED VOCAB ===" not in prompt


def test_user_instructions_preserve_order_and_bullet_each_line() -> None:
    """Each customization line is bulleted in its supplied order."""

    cfg = _prompt_config(
        customization=("Add pronunciation.", "Keep explanations short."),
    )
    prompt = assemble_system_prompt(cfg, minimal_cards=False)

    assert "=== USER INSTRUCTIONS ===" in prompt
    assert "take precedence over the default behavior above" in prompt
    assert "- Add pronunciation.\n- Keep explanations short." in prompt
    assert prompt.index("=== DEFAULT BEHAVIOR ===") < prompt.index(
        "=== USER INSTRUCTIONS ==="
    )


def test_customization_is_dropped_in_minimal_mode_but_kept_otherwise() -> None:
    """Customization is ignored for minimal cards and applied otherwise."""

    cfg = _prompt_config(customization=("Add pronunciation.",))

    minimal = assemble_system_prompt(cfg, minimal_cards=True)
    full = assemble_system_prompt(cfg, minimal_cards=False)

    assert "=== USER INSTRUCTIONS ===" not in minimal
    assert "Add pronunciation." not in minimal
    assert "=== USER INSTRUCTIONS ===" in full


def test_blacklist_lists_each_entry_as_a_best_effort_bullet() -> None:
    """Blacklisted vocab is listed as best-effort bullets."""

    cfg = _prompt_config(blacklist=("cosa", "genial"))
    prompt = assemble_system_prompt(cfg, minimal_cards=False)

    assert "=== BLACKLISTED VOCAB ===" in prompt
    assert "on a best-effort basis:\n- cosa\n- genial" in prompt


def test_blacklist_is_kept_in_minimal_mode() -> None:
    """The blacklist still constrains sentences even for minimal cards."""

    cfg = _prompt_config(blacklist=("cosa",))

    minimal = assemble_system_prompt(cfg, minimal_cards=True)

    assert "=== BLACKLISTED VOCAB ===" in minimal
    assert "- cosa" in minimal
