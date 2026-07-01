"""Shared test factories for generated cards."""

from __future__ import annotations

from typing import Any

from anki_auto.models import GeneratedCard


def card_kwargs(**overrides: Any) -> dict[str, Any]:
    """Build keyword arguments for a representative generated card."""

    values: dict[str, Any] = {
        "source": "sleep",
        "front_core_es": "dormir",
        "back_core_fr": "dormir",
        "examples": [
            {
                "fr": "Je dors huit heures.",
                "es": "Duermo ocho horas.",
            },
            {
                "fr": "Elle dort mal ce soir.",
                "es": "Ella duerme mal esta noche.",
            },
        ],
        "word_family": [
            {"fr": "un sommeil", "en": "sleep", "note": None},
            {"fr": "dormi", "en": "slept", "note": "past participle"},
        ],
        "related_vocab": [
            {"fr": "se réveiller", "en": "to wake up", "nuance": "opposite action"},
            {"fr": "une chambre", "en": "a bedroom", "nuance": "place for sleep"},
        ],
        "key_collocations": [
            {"fr": "dormir bien", "en": "to sleep well", "note": None},
        ],
        "register_notes": [
            "common irregular present forms vary by subject."
        ],
        "usage_forms": [
            {"fr": "je dors", "en": "I sleep", "note": "present tense"},
            {"fr": "tu dors", "en": "you sleep", "note": "present tense"},
            {"fr": "il dort", "en": "he sleeps", "note": "present tense"},
        ],
        "note_examples": ["Le bébé dort déjà.", "Elle a bien dormi."],
        "tags": ["French", " verb "],
    }
    values.update(overrides)
    return values


def generated_card(**overrides: Any) -> GeneratedCard:
    """Build a representative generated card."""

    return GeneratedCard(**card_kwargs(**overrides))


def empty_note_section_kwargs() -> dict[str, list[Any]]:
    """Build overrides for a card with no note sections."""

    return {
        "word_family": [],
        "related_vocab": [],
        "key_collocations": [],
        "register_notes": [],
        "usage_forms": [],
        "note_examples": [],
    }
