"""OpenAI client wrapper for structured card generation."""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from .config import PromptConfig
from .models import GeneratedCard
from .prompt import build_card_messages


@dataclass(frozen=True)
class OpenAICardGenerator:
    """Generate Anki cards with OpenAI structured output."""

    prompt_config: PromptConfig
    minimal_cards: bool = False
    model: str = "gpt-4.1-mini"
    api_key: str | None = None
    client: OpenAI | None = None

    def generate(self, item: str) -> GeneratedCard:
        """Generate and validate one card from a loose input item."""

        cleaned_item = item.strip()
        if not cleaned_item:
            raise ValueError("input item must not be blank")

        client = self.client or OpenAI(api_key=self.api_key)
        card = self._request_card(client, cleaned_item)
        if card.source != cleaned_item:
            card = card.model_copy(update={"source": cleaned_item})
        return card

    def _request_card(self, client: OpenAI, item: str) -> GeneratedCard:
        messages = build_card_messages(
            item,
            self.prompt_config,
            minimal_cards=self.minimal_cards,
        )
        completion = client.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=GeneratedCard,
        )
        card = completion.choices[0].message.parsed
        if card is None:
            raise ValueError("OpenAI refused to return a structured card")
        return card
