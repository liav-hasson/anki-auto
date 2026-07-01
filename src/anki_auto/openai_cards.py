"""OpenAI client wrapper for structured card generation."""

from __future__ import annotations

import json
from dataclasses import dataclass

from openai import OpenAI

from .models import GeneratedCard
from .prompt import build_card_messages, build_response_format


@dataclass(frozen=True)
class OpenAICardGenerator:
    """Generate French Anki cards with OpenAI structured JSON output."""

    model: str = "gpt-4.1-mini"
    client: OpenAI | None = None

    def generate(self, item: str) -> GeneratedCard:
        """Generate and validate one card from a loose input item."""

        cleaned_item = item.strip()
        if not cleaned_item:
            raise ValueError("input item must not be blank")

        client = self.client or OpenAI()
        content = self._request_card_json(client, cleaned_item)
        card = GeneratedCard.model_validate_json(content)
        if card.source != cleaned_item:
            card = card.model_copy(update={"source": cleaned_item})
        return card

    def _request_card_json(self, client: OpenAI, item: str) -> str:
        messages = build_card_messages(item)
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format=build_response_format(),
            )
        except TypeError:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
            )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI returned an empty card response")

        return _extract_json_object(content)


def _extract_json_object(content: str) -> str:
    """Return a JSON object string, tolerating accidental fenced output."""

    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1]).strip()

    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("OpenAI card response must be a JSON object")
    return json.dumps(parsed, ensure_ascii=False)
