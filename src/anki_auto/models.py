"""Structured card models used by generation and packaging."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clean_text(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("value must not be blank")
    return cleaned


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


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


class NoteItem(BaseModel):
    """A target-language term with its translation, nuance, and example."""

    model_config = ConfigDict(extra="forbid")

    term: str = Field(description="Target-language word or short phrase.")
    translation: str = Field(description="Notes-language translation of the term.")
    nuance: str | None = Field(
        default=None, description="Short optional notes-language usage nuance."
    )
    example: str = Field(
        description="Target-language example sentence using the term."
    )

    @field_validator("term", "translation", "example")
    @classmethod
    def require_text(cls, value: str) -> str:
        """Reject blank note-item text and trim surrounding whitespace."""

        return _clean_text(value)

    @field_validator("nuance")
    @classmethod
    def normalize_nuance(cls, value: str | None) -> str | None:
        """Trim optional nuance text and collapse blank values to None."""

        return _clean_optional_text(value)


class CustomSection(BaseModel):
    """A user-requested note section with structured note items."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Notes-language heading for this custom section.")
    items: list[NoteItem] = Field(
        min_length=1,
        max_length=8,
        description="Note items belonging to this custom section.",
    )

    @field_validator("title")
    @classmethod
    def require_title(cls, value: str) -> str:
        """Reject a blank custom-section title."""

        return _clean_text(value)


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
    word_family: list[NoteItem] = Field(
        default_factory=list,
        max_length=6,
        description="Related target-language forms of the core concept.",
    )
    related_vocab: list[NoteItem] = Field(
        default_factory=list,
        max_length=8,
        description="Nearby target-language words worth learning with the concept.",
    )
    custom_sections: list[CustomSection] = Field(
        default_factory=list,
        max_length=6,
        description="Additional note sections explicitly requested by the user.",
    )

    @field_validator("source", "target_core", "origin_core")
    @classmethod
    def require_text(cls, value: str) -> str:
        """Reject blank top-level text and trim surrounding whitespace."""

        return _clean_text(value)
