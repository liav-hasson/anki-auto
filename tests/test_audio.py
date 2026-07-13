"""Tests for OpenAI text-to-speech audio generation."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from anki_auto.audio import OpenAIAudioGenerator


class FakeStreamingResponse:
    """Tiny context manager matching the OpenAI streaming response API."""

    def __init__(self) -> None:
        """Track context and stream calls for assertions."""

        self.entered = False
        self.exited = False
        self.streamed_path: Path | None = None

    def __enter__(self) -> "FakeStreamingResponse":
        """Return the response object from the streaming context."""

        self.entered = True
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Record that the streaming context was closed."""

        self.exited = True

    def stream_to_file(self, output_path: Path) -> None:
        """Write fake media content to the requested path."""

        self.streamed_path = output_path
        output_path.write_bytes(b"fake mp3")


class FakeSpeechResource:  # pylint: disable=too-few-public-methods
    """Small fake for ``client.audio.speech``."""

    def __init__(self, response: FakeStreamingResponse) -> None:
        """Expose the nested streaming-response API used by the generator."""

        self.calls: list[dict[str, str]] = []
        self.with_streaming_response = SimpleNamespace(create=self.create)
        self._response = response

    def create(self, **kwargs: str) -> FakeStreamingResponse:
        """Record the speech request and return the fake streaming response."""

        self.calls.append(kwargs)
        return self._response


def test_audio_generator_uses_streaming_response_api(tmp_path: Path) -> None:
    """TTS should use the OpenAI streaming-response path and write the file."""

    response = FakeStreamingResponse()
    speech = FakeSpeechResource(response)
    client = SimpleNamespace(audio=SimpleNamespace(speech=speech))
    output_path = tmp_path / "nested" / "audio.mp3"

    result = OpenAIAudioGenerator(
        model="tts-test",
        voice="voice-test",
        client=client,
    ).generate(" bonjour ", output_path)

    assert result == output_path
    assert speech.calls == [
        {"model": "tts-test", "voice": "voice-test", "input": "bonjour"}
    ]
    assert response.entered is True
    assert response.exited is True
    assert response.streamed_path == output_path
    assert output_path.read_bytes() == b"fake mp3"


def test_audio_generator_rejects_blank_text() -> None:
    """Blank TTS text is rejected before any output path is created."""

    with pytest.raises(ValueError, match="audio text must not be blank"):
        OpenAIAudioGenerator(client=object()).generate("   ", Path("audio.mp3"))
