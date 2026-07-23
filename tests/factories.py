"""Shared test factories for generated cards."""

from __future__ import annotations

from typing import Any

from anki_auto.models import GeneratedCard


def card_kwargs(**overrides: Any) -> dict[str, Any]:
    """Build keyword arguments for a representative generated card."""

    values: dict[str, Any] = {
        "source": "sleep",
        "target_core": "dormir",
        "origin_core": "dormir",
        "examples": [
            {
                "target": "Je dors huit heures.",
                "origin": "Duermo ocho horas.",
            },
            {
                "target": "Elle dort mal ce soir.",
                "origin": "Ella duerme mal esta noche.",
            },
        ],
        "word_family": [
            {
                "term": "un sommeil",
                "translation": "sleep",
                "nuance": None,
                "example": "Le sommeil est important.",
            },
            {
                "term": "dormi",
                "translation": "slept",
                "nuance": "past participle",
                "example": "Il a dormi longtemps.",
            },
        ],
        "related_vocab": [
            {
                "term": "se réveiller",
                "translation": "to wake up",
                "nuance": "opposite action",
                "example": "Je me réveille tôt.",
            },
            {
                "term": "une chambre",
                "translation": "a bedroom",
                "nuance": "place for sleep",
                "example": "Ma chambre est calme.",
            },
        ],
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
        "custom_sections": [],
    }
