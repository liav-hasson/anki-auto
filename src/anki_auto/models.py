"""Structured card models used by generation and packaging."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ENGLISH_TRANSLATION_DESCRIPTION = "Practical English translation."


def _clean_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("value must not be blank")
    return cleaned


class ExamplePair(BaseModel):
    """A main French sentence and its Spanish translation."""

    model_config = ConfigDict(extra="forbid")

    fr: str = Field(description="Short French example sentence.")
    es: str = Field(description="Direct Spanish translation of the French sentence.")

    @field_validator("fr", "es")
    @classmethod
    def require_text(cls, value: str) -> str:
        """Reject blank example text and trim surrounding whitespace."""

        return _clean_text(value)


class TranslationEntry(BaseModel):
    """A French term and its English translation with an optional note."""

    model_config = ConfigDict(extra="forbid")

    fr: str = Field(description="French word or short phrase.")
    en: str = Field(description=ENGLISH_TRANSLATION_DESCRIPTION)
    note: str | None = Field(default=None, description="Short optional usage note.")

    @field_validator("fr", "en")
    @classmethod
    def require_text(cls, value: str) -> str:
        """Reject blank translation text and trim surrounding whitespace."""

        return _clean_text(value)

    @field_validator("note")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        """Trim optional note text and collapse blank values to None."""

        return _clean_optional_text(value)


class RelatedVocabEntry(BaseModel):
    """A related French term with optional usage nuance."""

    model_config = ConfigDict(extra="forbid")

    fr: str = Field(description="Related French word or phrase.")
    en: str = Field(description=ENGLISH_TRANSLATION_DESCRIPTION)
    nuance: str | None = Field(default=None, description="Short English nuance note.")

    @field_validator("fr", "en")
    @classmethod
    def require_text(cls, value: str) -> str:
        """Reject blank related-word text and trim surrounding whitespace."""

        return _clean_text(value)

    @field_validator("nuance")
    @classmethod
    def normalize_nuance(cls, value: str | None) -> str | None:
        """Trim optional nuance text and collapse blank values to None."""

        return _clean_optional_text(value)


class KeyCollocationEntry(BaseModel):
    """A useful French collocation or fixed expression."""

    model_config = ConfigDict(extra="forbid")

    fr: str = Field(description="French collocation or fixed expression.")
    en: str | None = Field(default=None, description=ENGLISH_TRANSLATION_DESCRIPTION)
    note: str | None = Field(default=None, description="Short optional usage note.")

    @field_validator("fr")
    @classmethod
    def require_text(cls, value: str) -> str:
        """Reject blank collocation text and trim surrounding whitespace."""

        return _clean_text(value)

    @field_validator("en", "note")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Trim optional text and collapse blank values to None."""

        return _clean_optional_text(value)

    @model_validator(mode="after")
    def require_translation_or_note(self) -> KeyCollocationEntry:
        """Require each collocation to carry either a translation or usage note."""

        if not self.en and not self.note:
            raise ValueError("key collocation must include en or note")
        return self


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class GeneratedCard(BaseModel):
    """A French learning card generated from a loose input item."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(
        description="Original loose input item used to create this card."
    )
    front_core_es: str = Field(
        description="Spanish-only direct translation of the core concept."
    )
    back_core_fr: str = Field(description="French core word, phrase, or construction.")
    examples: list[ExamplePair] = Field(
        min_length=2,
        max_length=3,
        description="Main French examples with Spanish translations.",
    )
    word_family: list[TranslationEntry] = Field(
        default_factory=list,
        max_length=6,
        description="Useful French word-family entries with English translations.",
    )
    related_vocab: list[RelatedVocabEntry] = Field(
        default_factory=list,
        max_length=8,
        description=(
            "Related French forms and nearby words with English translations and nuance."
        ),
    )
    key_collocations: list[KeyCollocationEntry] = Field(
        default_factory=list,
        max_length=6,
        description="Useful collocations or fixed expressions using the keyword.",
    )
    register_notes: list[str] = Field(
        default_factory=list,
        max_length=4,
        description=(
            "Short practical English-only register or usage notes; no example sentences."
        ),
    )
    usage_forms: list[TranslationEntry] = Field(
        default_factory=list,
        max_length=8,
        description=(
            "French usage forms, conjugations, or trap phrases that support register notes."
        ),
    )
    note_examples: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Extra French example sentences for the notes section.",
    )
    tags: list[str] = Field(
        default_factory=list, description="Short Anki-compatible tags."
    )

    @field_validator("source", "front_core_es", "back_core_fr")
    @classmethod
    def require_text(cls, value: str) -> str:
        """Reject blank top-level text and trim surrounding whitespace."""

        return _clean_text(value)

    @field_validator("register_notes", "note_examples")
    @classmethod
    def require_text_items(cls, values: list[str]) -> list[str]:
        """Reject blank text items and trim surrounding whitespace."""

        return [_clean_text(value) for value in values]

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        """Normalize Anki tags to stable lowercase tokens."""

        normalized = []
        for value in values:
            tag = "-".join(value.strip().lower().split())
            tag = "".join(
                character
                for character in tag
                if character.isalnum() or character in "_-:"
            )
            if tag and tag not in normalized:
                normalized.append(tag)
        return normalized


class CardBatch(BaseModel):
    """Serializable collection of generated cards."""

    model_config = ConfigDict(extra="forbid")

    cards: list[GeneratedCard]


def card_json_schema() -> dict[str, Any]:
    """Return the JSON schema used for strict OpenAI structured output."""

    text_field = {"type": "string", "minLength": 1}
    example_pair = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "fr": text_field,
            "es": text_field,
        },
        "required": ["fr", "es"],
    }
    translation_entry = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "fr": text_field,
            "en": text_field,
            "note": {"type": ["string", "null"], "minLength": 1},
        },
        "required": ["fr", "en", "note"],
    }
    related_vocab_entry = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "fr": text_field,
            "en": text_field,
            "nuance": {"type": ["string", "null"], "minLength": 1},
        },
        "required": ["fr", "en", "nuance"],
    }
    key_collocation_entry = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "fr": text_field,
            "en": {"type": ["string", "null"], "minLength": 1},
            "note": {"type": ["string", "null"], "minLength": 1},
        },
        "required": ["fr", "en", "note"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "source": text_field,
            "front_core_es": text_field,
            "back_core_fr": text_field,
            "examples": {
                "type": "array",
                "items": example_pair,
                "minItems": 2,
                "maxItems": 3,
            },
            "word_family": {
                "type": "array",
                "items": translation_entry,
                "maxItems": 6,
            },
            "related_vocab": {
                "type": "array",
                "items": related_vocab_entry,
                "maxItems": 8,
            },
            "key_collocations": {
                "type": "array",
                "items": key_collocation_entry,
                "maxItems": 6,
            },
            "register_notes": {
                "type": "array",
                "items": text_field,
                "maxItems": 4,
            },
            "usage_forms": {
                "type": "array",
                "items": translation_entry,
                "maxItems": 8,
            },
            "note_examples": {
                "type": "array",
                "items": text_field,
                "maxItems": 3,
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 8,
            },
        },
        "required": [
            "source",
            "front_core_es",
            "back_core_fr",
            "examples",
            "word_family",
            "related_vocab",
            "key_collocations",
            "register_notes",
            "usage_forms",
            "note_examples",
            "tags",
        ],
    }
