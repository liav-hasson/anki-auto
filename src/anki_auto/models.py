"""Structured card models used by generation and packaging."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


GLOSS_DESCRIPTION = "Notes-language translation."


def _clean_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("value must not be blank")
    return cleaned


class ExamplePair(BaseModel):
    """A target-language sentence and its origin-language translation."""

    model_config = ConfigDict(extra="forbid")

    target: str = Field(description="Target-language example sentence.")
    origin: str = Field(
        description="Origin-language translation of the target sentence."
    )

    @field_validator("target", "origin")
    @classmethod
    def require_text(cls, value: str) -> str:
        """Reject blank example text and trim surrounding whitespace."""

        return _clean_text(value)


class TranslationEntry(BaseModel):
    """A target-language term and its notes-language gloss with an optional note."""

    model_config = ConfigDict(extra="forbid")

    target: str = Field(description="Target-language word or short phrase.")
    gloss: str = Field(description=GLOSS_DESCRIPTION)
    note: str | None = Field(default=None, description="Short optional usage note.")

    @field_validator("target", "gloss")
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
    """A related target-language term with optional usage nuance."""

    model_config = ConfigDict(extra="forbid")

    target: str = Field(description="Related target-language word or phrase.")
    gloss: str = Field(description=GLOSS_DESCRIPTION)
    nuance: str | None = Field(
        default=None, description="Short notes-language nuance note."
    )

    @field_validator("target", "gloss")
    @classmethod
    def require_text(cls, value: str) -> str:
        """Reject blank related-word text and trim surrounding whitespace."""

        return _clean_text(value)

    @field_validator("nuance")
    @classmethod
    def normalize_nuance(cls, value: str | None) -> str | None:
        """Trim optional nuance text and collapse blank values to None."""

        return _clean_optional_text(value)


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class GeneratedCard(BaseModel):
    """A learning card generated from a loose input item."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(
        description="Original loose input item used to create this card."
    )
    target_core: str = Field(
        description="Target-language core word, phrase, or construction."
    )
    origin_core: str = Field(
        description="Origin-language translation of the core concept."
    )
    examples: list[ExamplePair] = Field(
        min_length=2,
        max_length=3,
        description="Main target-language examples with origin-language translations.",
    )
    word_family: list[TranslationEntry] = Field(
        default_factory=list,
        max_length=6,
        description="Useful target-language word-family entries with glosses.",
    )
    related_vocab: list[RelatedVocabEntry] = Field(
        default_factory=list,
        max_length=8,
        description=(
            "Related target-language forms and nearby words with glosses and nuance."
        ),
    )
    note_examples: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Extra target-language example sentences for the notes section.",
    )

    @field_validator("source", "target_core", "origin_core")
    @classmethod
    def require_text(cls, value: str) -> str:
        """Reject blank top-level text and trim surrounding whitespace."""

        return _clean_text(value)

    @field_validator("note_examples")
    @classmethod
    def require_text_items(cls, values: list[str]) -> list[str]:
        """Reject blank text items and trim surrounding whitespace."""

        return [_clean_text(value) for value in values]
