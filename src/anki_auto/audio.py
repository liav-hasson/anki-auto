"""OpenAI text-to-speech support for Anki media files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI


@dataclass(frozen=True)
class OpenAIAudioGenerator:
    """Generate MP3 audio for target-language card text."""

    model: str = "gpt-4o-mini-tts"
    voice: str = "alloy"
    api_key: str | None = None
    client: OpenAI | None = None

    def generate(self, text: str, output_path: Path) -> Path:
        """Generate an MP3 file for text and return its path."""

        cleaned_text = text.strip()
        if not cleaned_text:
            raise ValueError("audio text must not be blank")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        client = self.client or OpenAI(api_key=self.api_key)
        with client.audio.speech.with_streaming_response.create(
            model=self.model,
            voice=self.voice,
            input=cleaned_text,
        ) as response:
            response.stream_to_file(output_path)
        return output_path
