"""Tests for CLI helper behavior."""

from pathlib import Path

import pytest

from anki_auto.cli import (
    DEFAULT_NOTE_MODEL_NAME,
    package_cards_with_audio,
    read_input_items,
    require_openai_api_key,
)
from tests.factories import generated_card


def test_read_input_items_ignores_blank_lines_and_comments(tmp_path: Path) -> None:
    """Input files should support comments and blank spacing."""

    input_path = tmp_path / "items.txt"
    input_path.write_text("dog\n\n# skip me\ntrain station\n", encoding="utf-8")

    assert read_input_items(input_path) == ["dog", "train station"]


def test_default_note_model_name_is_v2() -> None:
    """Default imports should avoid reusing the original Anki model template."""

    assert DEFAULT_NOTE_MODEL_NAME == "Anki Auto French Spanish Notes v2"


def test_require_openai_api_key_fails_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The CLI should fail before network calls when credentials are missing."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        require_openai_api_key()


def test_package_cards_with_audio_generates_one_file_per_example(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Audio packaging should create one media file for each main French sentence."""

    class FakeAudioGenerator:  # pylint: disable=too-few-public-methods
        """Small fake text-to-speech generator that writes the input text."""

        def __init__(self, model: str, voice: str) -> None:
            """Store constructor arguments to match the real generator API."""

            self.model = model
            self.voice = voice

        def generate(self, text: str, output_path: Path) -> Path:
            """Write fake audio content and return its path."""

            output_path.write_text(text, encoding="utf-8")
            return output_path

    monkeypatch.setattr("anki_auto.cli.OpenAIAudioGenerator", FakeAudioGenerator)

    packaged_cards = package_cards_with_audio(
        cards=[
            generated_card(
                examples=[
                    {"fr": "Le chien court.", "es": "El perro corre."},
                    {"fr": "Le chien dort.", "es": "El perro duerme."},
                ],
            )
        ],
        no_audio=False,
        audio_model="tts-test",
        voice="voice-test",
    )

    assert len(packaged_cards) == 1
    assert len(packaged_cards[0].audio_paths) == 2
    assert packaged_cards[0].audio_paths[0].name.startswith("anki-auto-sleep-1-")
    assert (
        packaged_cards[0].audio_paths[0].read_text(encoding="utf-8")
        == "Le chien court."
    )
    assert packaged_cards[0].audio_paths[1].name.startswith("anki-auto-sleep-2-")
    assert (
        packaged_cards[0].audio_paths[1].read_text(encoding="utf-8")
        == "Le chien dort."
    )
