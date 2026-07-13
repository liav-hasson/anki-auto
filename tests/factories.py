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
            {"target": "un sommeil", "gloss": "sleep", "note": None},
            {"target": "dormi", "gloss": "slept", "note": "past participle"},
        ],
        "related_vocab": [
            {"target": "se réveiller", "gloss": "to wake up", "nuance": "opposite action"},
            {"target": "une chambre", "gloss": "a bedroom", "nuance": "place for sleep"},
        ],
        "note_examples": ["Le bébé dort déjà.", "Elle a bien dormi."],
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
        "note_examples": [],
    }
