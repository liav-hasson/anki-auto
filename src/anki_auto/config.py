"""Typed application settings loaded from environment and `.env`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from . import logging_utils


CEFRLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]

_DEFAULTED_WARN_FIELDS: dict[str, str] = {
    "text_model": "ANKI_TEXT_MODEL",
    "audio_model": "ANKI_AUDIO_MODEL",
    "audio_voice": "ANKI_AUDIO_VOICE",
    "deck_name": "ANKI_DECK_NAME",
    "input_path": "ANKI_INPUT_PATH",
    "output_path": "ANKI_OUTPUT_PATH",
}


@dataclass(frozen=True)
class PromptConfig:
    """Minimal language view consumed by the prompt builders."""

    origin_language: str
    target_language: str
    notes_language: str
    level: str


class Settings(BaseSettings):
    """Runtime configuration for anki-auto, sourced from env and `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ANKI_",
        env_ignore_empty=True,
        extra="ignore",
    )

    openai_api_key: str = Field(validation_alias="OPENAI_API_KEY")
    origin_language: str
    target_language: str
    notes_language: str
    cefr_level: CEFRLevel

    text_model: str = "gpt-4.1-mini"
    audio_model: str = "gpt-4o-mini-tts"
    audio_voice: str = "alloy"
    deck_name: str = "Anki Auto Deck"
    input_path: Path = Path("items.txt")
    output_path: Path = Path("deck.apkg")

    generate_audio: bool = True
    minimal_cards: bool = False
    assume_yes: bool = False
    overwrite_output: bool = False

    concurrency: int = 5

    @field_validator("concurrency")
    @classmethod
    def require_positive_concurrency(cls, value: int) -> int:
        """Reject a concurrency below one parallel request."""

        if value < 1:
            raise ValueError("concurrency must be at least 1")
        return value

    @field_validator("cefr_level", mode="before")
    @classmethod
    def normalize_cefr_level(cls, value: object) -> object:
        """Accept case- and whitespace-insensitive CEFR levels (e.g. `c2`)."""

        if isinstance(value, str):
            return value.strip().upper()
        return value

    @field_validator("origin_language", "target_language", "notes_language")
    @classmethod
    def require_language(cls, value: str) -> str:
        """Reject blank language names and trim surrounding whitespace."""

        cleaned = value.strip()
        if not cleaned:
            raise ValueError("language must not be blank")
        return cleaned

    @model_validator(mode="after")
    def enforce_language_collision(self) -> Settings:
        """Require the target language to differ from origin and notes languages."""

        target = self.target_language.strip().casefold()
        origin = self.origin_language.strip().casefold()
        notes = self.notes_language.strip().casefold()
        if target == origin:
            raise ValueError("target_language must differ from origin_language")
        if target == notes:
            raise ValueError("target_language must differ from notes_language")
        return self

    def prompt_config(self) -> PromptConfig:
        """Return the language view used by the prompt builders."""

        return PromptConfig(
            origin_language=self.origin_language,
            target_language=self.target_language,
            notes_language=self.notes_language,
            level=self.cefr_level,
        )


def load_settings() -> Settings:
    """Construct settings and warn once per operational var left at its default."""

    settings = Settings()
    for field_name, env_name in _DEFAULTED_WARN_FIELDS.items():
        if field_name not in settings.model_fields_set:
            default_value = getattr(settings, field_name)
            logging_utils.warning(
                f"{env_name} not set, using default '{default_value}'"
            )
    return settings
