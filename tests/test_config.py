"""Tests for the typed Settings configuration layer."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anki_auto.config import Settings, load_settings


def _set_required_env(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> None:
    """Populate the required environment variables, with optional overrides."""

    values = {
        "OPENAI_API_KEY": "sk-test",
        "ANKI_ORIGIN_LANGUAGE": "Spanish",
        "ANKI_TARGET_LANGUAGE": "French",
        "ANKI_NOTES_LANGUAGE": "English",
        "ANKI_CEFR_LEVEL": "A2",
    }
    values.update(overrides)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_settings_load_with_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Providing all required vars yields a valid settings object with defaults."""

    _set_required_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.openai_api_key == "sk-test"
    assert settings.target_language == "French"
    assert settings.cefr_level == "A2"
    assert settings.text_model == "gpt-4.1-mini"
    assert settings.generate_audio is True
    assert settings.prompt_config().level == "A2"


def test_target_equals_origin_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """The collision rule rejects a target matching the origin language."""

    _set_required_env(monkeypatch, ANKI_TARGET_LANGUAGE="  spanish  ")

    with pytest.raises(ValidationError, match="origin_language"):
        Settings(_env_file=None)


def test_target_equals_notes_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """The collision rule rejects a target matching the notes language."""

    _set_required_env(monkeypatch, ANKI_TARGET_LANGUAGE="ENGLISH")

    with pytest.raises(ValidationError, match="notes_language"):
        Settings(_env_file=None)


def test_origin_equals_notes_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Origin matching notes is permitted; only target must be distinct."""

    _set_required_env(
        monkeypatch,
        ANKI_ORIGIN_LANGUAGE="English",
        ANKI_NOTES_LANGUAGE="English",
    )

    settings = Settings(_env_file=None)

    assert settings.origin_language == "English"
    assert settings.notes_language == "English"


def test_invalid_cefr_level_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """An out-of-range CEFR level fails validation."""

    _set_required_env(monkeypatch, ANKI_CEFR_LEVEL="Z9")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_concurrency_parses_from_env_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """A numeric ANKI_CONCURRENCY string parses into an integer."""

    _set_required_env(monkeypatch, ANKI_CONCURRENCY="8")

    settings = Settings(_env_file=None)

    assert settings.concurrency == 8


def test_concurrency_defaults_to_five(monkeypatch: pytest.MonkeyPatch) -> None:
    """Concurrency silently defaults to five parallel requests."""

    _set_required_env(monkeypatch)

    settings = Settings(_env_file=None)

    assert settings.concurrency == 5


@pytest.mark.parametrize("value", ["0", "-1"])
def test_concurrency_below_one_raises(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """A concurrency below one is rejected with a clear message."""

    _set_required_env(monkeypatch, ANKI_CONCURRENCY=value)

    with pytest.raises(ValidationError, match="concurrency must be at least 1"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("c2", "C2"), (" b1 ", "B1"), ("A2", "A2")],
)
def test_cefr_level_is_normalized(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: str
) -> None:
    """Lowercase and padded CEFR levels are normalized before validation."""

    _set_required_env(monkeypatch, ANKI_CEFR_LEVEL=raw)

    settings = Settings(_env_file=None)

    assert settings.cefr_level == expected


def test_cefr_level_still_rejects_invalid_after_normalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normalization does not rescue genuinely invalid CEFR levels."""

    _set_required_env(monkeypatch, ANKI_CEFR_LEVEL=" d67 ")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)



def test_blank_language_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank language name is rejected."""

    _set_required_env(monkeypatch, ANKI_TARGET_LANGUAGE="   ")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_missing_required_var_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing required variable fails fast at construction."""

    _set_required_env(monkeypatch)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_load_settings_warns_for_defaulted_operational_var(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A missing operational var warns; missing boolean toggles stay silent."""

    monkeypatch.chdir(tmp_path)
    _set_required_env(monkeypatch)

    settings = load_settings()

    captured = capsys.readouterr()
    assert "ANKI_TEXT_MODEL not set, using default 'gpt-4.1-mini'" in captured.err
    assert "ANKI_GENERATE_AUDIO" not in captured.err
    assert "ANKI_DRY_RUN" not in captured.err
    assert settings.text_model == "gpt-4.1-mini"


def test_load_settings_does_not_warn_for_provided_var(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A provided operational var suppresses its default warning."""

    monkeypatch.chdir(tmp_path)
    _set_required_env(monkeypatch)
    monkeypatch.setenv("ANKI_TEXT_MODEL", "gpt-4o")

    load_settings()

    captured = capsys.readouterr()
    assert "ANKI_TEXT_MODEL" not in captured.err
