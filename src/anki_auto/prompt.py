"""Prompt construction for French card generation."""

from __future__ import annotations

from .models import card_json_schema


SYSTEM_PROMPT = """You create fresh French Anki cards from loose input items.

Return exactly one JSON object matching the provided schema.
The learner is an A1-B1 French student who is fluent in Spanish and English.
Distill messy input into the cleanest reusable French core concept; remove examples, "etc.",
context clutter, and tentative lists from the core instead of copying a long prompt verbatim.

Card content:
- front_core_es is Spanish only: a direct translation of the core concept.
- back_core_fr is the French core word, phrase, or construction.
- examples contains 2-3 short French sentences and direct Spanish translations.
- Keep French and Spanish examples natural, concise, varied, and beginner-safe.

Optional note sections:
- Use empty arrays for irrelevant sections. Do not add filler.
- word_family: useful noun, adjective, verb, or adverb forms only.
- related_vocab: usually 2-5 useful derived forms or nearby words for one lexical item,
    including past participles, noun/adjective forms, opposites, or related nouns when useful.
- key_collocations: fixed expressions or common pairings using the keyword.
- register_notes: English-only prose notes about formality, region, false friends,
    exceptions, pronunciation, orthography, or grammar traps. Do not include example sentences.
- usage_forms: French forms, conjugations, adjective forms, or trap phrases that support the
    register notes, each with a practical English translation.
- note_examples: 1-3 original French-only sentences showing meanings, collocations, or registers
    not already used in the main examples. Do not include them in register_notes.
- Structured note entries in word_family, related_vocab, key_collocations, and usage_forms must be
    expressible as French term: English translation + concise nuance.

Core concept formatting:
- Use infinitives for verbs; examples may conjugate naturally.
- Include the reflexive pronoun when relevant, such as "se souvenir".
- Do not include conjugated example variants in the core.
- Include a gender article for nouns, such as "le sommeil", "la gare", or "l'eau".
- Include masculine and feminine forms for adjectives, when exists.
- Use slash only for compact neutral lemmas or paired forms, not context lists.
- Write grammar constructions as compact templates.
- Keep broad concepts broad, such as "numbers 10-100", "days of the week", or "Greetings".

Note term formatting:
- Normalize French terms in word_family, related_vocab, key_collocations, and usage_forms
    like the core concept when applicable.
- Use infinitive/reflexive forms for verbs, gender articles for nouns, masculine/feminine
    paired forms for adjectives, and natural lemma forms for collocations.

Example style:
- Keep sentences short, natural, and useful for beginner/intermediate learners.
- Vary vocabulary, sentence patterns, moods, times, locations, connectors, names, and contexts.
- Avoid repeated vocabulary and default patterns such as always using "J'aime...".
- Casual or slang wording is welcome when it is common and beginner-safe.
- Keep notes compact: fragments and short lines are better than long paragraphs.
"""


def build_card_messages(item: str) -> list[dict[str, str]]:
    """Build chat messages for one loose input item."""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Create one French Anki card from this loose input item. "
                "Set source to the exact input text.\n\n"
                f"Input item: {item.strip()}"
            ),
        },
    ]


def build_response_format() -> dict[str, object]:
    """Build a conservative structured-output response format for OpenAI chat completions."""

    return {
        "type": "json_schema",
        "json_schema": {
            "name": "french_anki_card",
            "strict": True,
            "schema": card_json_schema(),
        },
    }
