"""Cohesive parameter objects for audio generation and package building."""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI


@dataclass(frozen=True)
class AudioOptions:
    """Settings needed to build a text-to-speech generator."""

    model: str
    voice: str
    api_key: str | None = None
    client: OpenAI | None = None


@dataclass(frozen=True)
class PackagingOptions:
    """Everything ``write_apkg`` needs beyond the cards, output path, and media."""

    deck_name: str
    model_name: str
    target_language: str
    cefr_level: str
    minimal_cards: bool = False
